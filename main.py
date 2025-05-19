#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
剧集缺集检查工具

该程序用于扫描媒体库中的剧集,与TMDB数据进行比较,找出缺失的集数,
并可选择性地通过MoviePilot进行订阅或下载。
"""

import os
import time
import asyncio
import aiofiles
import argparse
import logging
from typing import Dict, List, Set, Optional
from pathlib import Path
from collections import defaultdict

# 导入自定义模块
from utils.config import (
    REPORT_FILE, SKIPPED_LOG, MAX_SHOWS,
    AUTO_SUBSCRIBE, AUTO_DOWNLOAD, SUBSCRIBE_THRESHOLD,
    STORAGE_TYPE, StorageType
)
from utils.helpers import (
    log_skipped, parse_filename, CacheData,
    load_cache, save_cache, reset_cache, merge_old_cache,
    async_error_handler, MediaProcessError
)
from storage import get_storage_backend
from tmdb.api import search_tv_show, get_tmdb_structure
from media_manager.moviepilot import (
    login as mp_login,
    handle_missing_episodes,
    MoviePilotResult
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@async_error_handler("Process")
async def process_show(
    dir_name: str, 
    cache: CacheData, 
    report_file: str, 
    is_specific_show: bool = False
) -> tuple:
    """处理单个剧集并输出缺失"""
    # 检查该剧集是否已经完整,但如果是指定要检查的剧集则不跳过
    if cache.is_complete_dir(dir_name) and not is_specific_show:
        tmdb_id = cache.complete_dirs[dir_name]["tmdb_id"]
        print(f"  ✅ 剧集已完整 [TMDB ID: {tmdb_id}]，跳过检查")
        return 0, 0, False, False
    
    print(f"\n处理剧集: {dir_name}")
    
    local_seasons = defaultdict(set)
    skipped_files = []
    
    # 获取存储后端
    storage = get_storage_backend()
    
    # 获取文件并解析
    try:
        files = await storage.get_directory_structure(dir_name)
        if not files:
            print(f"  未找到任何文件")
            return 0, 0, False, False
    except Exception as e:
        print(f"  获取目录结构失败: {e}")
        return 0, 0, False, False
    
    # 解析文件名，获取季集信息
    valid_count = 0
    
    for file_info in files:
        filepath = file_info["path"]
        known_season = file_info["season"]
        
        parsed = parse_filename(filepath, known_season)
        if parsed:
            season, episode = parsed
            local_seasons[season].add(episode)
            valid_count += 1
        else:
            skipped_files.append(filepath)
    
    if skipped_files:
        for file in skipped_files:
            await log_skipped(f"{dir_name}/{file}")
    
    if not any(local_seasons.values()):
        print(f"  未找到任何有效剧集文件")
        return 0, len(skipped_files), False, False
    
    # 查询TMDB并验证年份
    try:
        tmdb_id, tmdb_name = await search_tv_show(dir_name, cache)
        if not tmdb_id:
            print(f"  TMDB 查询失败，未找到该剧")
            return valid_count, len(skipped_files), False, False
        
        # 获取TMDB剧集结构
        tmdb_structure = await get_tmdb_structure(tmdb_id)
        if not tmdb_structure:
            print(f"  TMDB 未返回季集信息")
            return valid_count, len(skipped_files), False, False
    except Exception as e:
        print(f"  查询TMDB信息失败: {e}")
        return valid_count, len(skipped_files), False, False
    
    # 检查缺失剧集
    missing = defaultdict(list)
    for season in tmdb_structure:
        all_eps = set(tmdb_structure[season])
        local_eps = local_seasons.get(season, set())
        diff = all_eps - local_eps
        if diff:
            missing[season] = sorted(list(diff))
    
    # 只处理有缺失的剧集
    if not missing:
        print(f"  ✅ 所有季/集齐全")
        # 记录完整剧集信息到缓存
        cache.mark_complete_dir(dir_name, tmdb_id)
        await save_cache(cache)
        return valid_count, len(skipped_files), False, True
    else:
        print(f"  ❌ 发现缺失剧集:")
        result_lines = []
        
        result_lines.append(f"\n【{dir_name}】 - {tmdb_name} [TMDB ID: {tmdb_id}]")
        result_lines.append(f"  已有剧集: {dict(local_seasons)}")
        result_lines.append(f"  TMDB剧集结构: {dict((s, len(e)) for s, e in tmdb_structure.items())}")
        
        # 处理缺失剧集
        mp_results = []
        
        for season in sorted(missing):
            miss_str = f"  ❌ Season {season}: 缺少集数 {missing[season]}"
            print(miss_str)
            result_lines.append(miss_str)
            
            # 使用MoviePilot处理缺失剧集
            if AUTO_SUBSCRIBE or AUTO_DOWNLOAD:
                try:
                    mp_result = await handle_missing_episodes(
                        show_name=dir_name,
                        tmdb_id=tmdb_id,
                        season=season,
                        episodes=missing[season],
                        auto_subscribe=AUTO_SUBSCRIBE,
                        auto_download=AUTO_DOWNLOAD,
                        subscribe_threshold=SUBSCRIBE_THRESHOLD
                    )
                    result_str = f"  🎬 Season {season}: {mp_result.message}"
                    print(result_str)
                    mp_results.append(result_str)
                except Exception as e:
                    error_str = f"  ❌ Season {season}: 处理出错 - {e}"
                    print(error_str)
                    mp_results.append(error_str)
        
        # 添加MoviePilot处理结果
        if mp_results:
            result_lines.append("  --MoviePilot处理结果--")
            result_lines.extend(mp_results)
        
        async with aiofiles.open(report_file, "a", encoding="utf-8") as f:
            await f.write("\n".join(result_lines) + "\n")
            
        return valid_count, len(skipped_files), True, False

@async_error_handler("Main")
async def main_async(specific_show=None):
    """主异步函数"""
    start_time = time.time()
    print("开始检查缺失剧集...")
    
    # 配置MoviePilot
    if AUTO_SUBSCRIBE or AUTO_DOWNLOAD:
        print("正在初始化MoviePilot...")
        try:
            mp_success = await mp_login()
            if mp_success:
                print("MoviePilot已准备就绪")
                print(f"自动订阅功能: {'开启' if AUTO_SUBSCRIBE else '关闭'}")
                if AUTO_SUBSCRIBE:
                    if SUBSCRIBE_THRESHOLD == 0:
                        print(f"订阅策略: 无论缺失几集都订阅")
                    else:
                        print(f"订阅策略: 缺失超过{SUBSCRIBE_THRESHOLD}集时订阅整季")
                print(f"自动下载功能: {'开启' if AUTO_DOWNLOAD else '关闭'}")
            else:
                print("MoviePilot登录失败,自动订阅和下载功能将不可用")
        except Exception as e:
            print(f"MoviePilot初始化失败: {e}")
    
    # 清除上次的文件
    if not specific_show:
        if os.path.exists(SKIPPED_LOG):
            os.unlink(SKIPPED_LOG)
        
        if os.path.exists(REPORT_FILE):
            os.unlink(REPORT_FILE)
        
        # 初始化报告文件
        async with aiofiles.open(REPORT_FILE, "w", encoding="utf-8") as f:
            await f.write(f"媒体库缺失剧集报告 (存储类型: {STORAGE_TYPE.value})\n===============================\n")
    
    # 加载统一缓存
    cache = await load_cache()
    
    # 获取完整目录数量
    complete_count = len(cache.complete_dirs)
    print(f"已加载缓存: {len(cache.tmdb_map)} 个剧集映射, {complete_count} 个完整剧集记录")
    
    # 显示缺失剧集的列表标题
    if not specific_show:
        async with aiofiles.open(REPORT_FILE, "a", encoding="utf-8") as f:
            await f.write("\n缺失剧集列表\n-----------------\n")
    
    new_complete_count = 0
    
    # 初始化存储后端
    storage = get_storage_backend()
    print(f"使用存储后端: {STORAGE_TYPE.value}")
    
    if specific_show:
        # 仅处理指定的剧集
        dirs = [specific_show]
        print(f"仅处理指定的剧集: {specific_show}")
    else:
        # 获取所有剧集目录
        try:
            dirs = await storage.list_directories()
            
            if not dirs:
                print("未找到任何剧集目录")
                return
            
            total_dirs = len(dirs)
            print(f"找到 {total_dirs} 个剧集目录")
            
            # 限制处理的剧集数量
            if MAX_SHOWS:
                dirs = dirs[:MAX_SHOWS]
                print(f"将仅处理前 {len(dirs)} 个剧集")
        except Exception as e:
            print(f"获取目录列表失败: {e}")
            return
    
    total_processed = 0
    total_skipped = 0
    total_missing = 0
    
    # 按目录处理，实时输出
    for index, dir_name in enumerate(dirs, 1):
        try:
            if len(dirs) > 1:
                print(f"\n[{index}/{len(dirs)}] 处理剧集: {dir_name}")
            else:
                print(f"\n处理剧集: {dir_name}")
            
            processed, skipped, has_missing, is_complete = await process_show(
                dir_name, 
                cache, 
                REPORT_FILE, 
                is_specific_show=bool(specific_show)
            )
            total_processed += processed
            total_skipped += skipped
            if has_missing:
                total_missing += 1
            if is_complete:
                new_complete_count += 1
            
            # 每处理10个剧集，保存一次缓存
            if index % 10 == 0 and len(dirs) > 10:
                await save_cache(cache)
                print(f"已处理 {index}/{len(dirs)} 个剧集...")
        except Exception as e:
            print(f"处理剧集 {dir_name} 时出错: {e}")
            continue
    
    elapsed = time.time() - start_time
    
    # 完成处理
    print("\n检查完成!")
    if not specific_show:
        print(f"总共处理了 {len(dirs)} 个剧集目录")
        print(f"找到 {total_missing} 个有缺失的剧集")
        print(f"新增 {new_complete_count} 个完整剧集记录")
        print(f"总共处理了 {total_processed} 个有效文件")
        print(f"总共跳过了 {total_skipped} 个无法识别的文件")
        print(f"耗时: {elapsed:.1f} 秒")
        print(f"报告已保存到: {REPORT_FILE}")
        if total_skipped:
            print(f"无法识别的文件记录于: {SKIPPED_LOG}")
    
    # 保存缓存
    await save_cache(cache)

def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='检查剧集是否缺集并订阅/下载缺失集数')
    parser.add_argument('--show', type=str, help='只处理指定的剧集名称，例如 "哥谭 (2014)"')
    parser.add_argument('--no-subscribe', action='store_true', help='禁用自动订阅功能')
    parser.add_argument('--download', action='store_true', help='启用自动下载功能')
    parser.add_argument('--subscribe-all', action='store_true', help='订阅所有缺失剧集，无论缺失几集')
    parser.add_argument('--threshold', type=int, help='设置订阅阈值，缺失超过多少集时订阅整季')
    parser.add_argument('--force-check-all', action='store_true', help='强制检查所有剧集，包括已记录为完整的剧集')
    parser.add_argument('--merge-cache', type=str, help='合并旧缓存文件(如tmdb_cache.json)到新缓存格式')
    
    # 存储类型选择
    storage_group = parser.add_argument_group('存储类型')
    storage_group.add_argument('--storage', type=str, choices=['rclone', 'alist', 'webdav', 'local'], 
                             help='选择存储类型: rclone, alist, webdav, local')
    
    # 存储配置
    rclone_group = parser.add_argument_group('Rclone配置')
    rclone_group.add_argument('--rclone-remote', type=str, help='Rclone远程路径')
    
    alist_group = parser.add_argument_group('Alist配置')
    alist_group.add_argument('--alist-url', type=str, help='Alist服务器URL')
    alist_group.add_argument('--alist-username', type=str, help='Alist用户名')
    alist_group.add_argument('--alist-password', type=str, help='Alist密码')
    alist_group.add_argument('--alist-token', type=str, help='Alist访问令牌')
    alist_group.add_argument('--alist-path', type=str, help='Alist媒体路径')
    
    webdav_group = parser.add_argument_group('WebDAV配置')
    webdav_group.add_argument('--webdav-url', type=str, help='WebDAV服务器URL')
    webdav_group.add_argument('--webdav-username', type=str, help='WebDAV用户名')
    webdav_group.add_argument('--webdav-password', type=str, help='WebDAV密码')
    webdav_group.add_argument('--webdav-path', type=str, help='WebDAV媒体路径')
    
    local_group = parser.add_argument_group('本地配置')
    local_group.add_argument('--local-path', type=str, help='本地媒体路径')
    
    args = parser.parse_args()
    
    # 应用命令行参数
    if args.no_subscribe:
        global AUTO_SUBSCRIBE
        AUTO_SUBSCRIBE = False
    if args.download:
        global AUTO_DOWNLOAD
        AUTO_DOWNLOAD = True
    if args.subscribe_all:
        global SUBSCRIBE_THRESHOLD
        SUBSCRIBE_THRESHOLD = 0
    if args.threshold is not None:
        SUBSCRIBE_THRESHOLD = args.threshold
    
    # 设置存储类型
    if args.storage:
        global STORAGE_TYPE
        if args.storage == 'rclone':
            STORAGE_TYPE = StorageType.RCLONE
        elif args.storage == 'alist':
            STORAGE_TYPE = StorageType.ALIST
        elif args.storage == 'webdav':
            STORAGE_TYPE = StorageType.WEBDAV
        elif args.storage == 'local':
            STORAGE_TYPE = StorageType.LOCAL
    
    # 应用存储配置
    if args.rclone_remote:
        import utils.config
        utils.config.RCLONE_REMOTE = args.rclone_remote
        
    if args.alist_url:
        import utils.config
        utils.config.ALIST_URL = args.alist_url
    if args.alist_username:
        import utils.config
        utils.config.ALIST_USERNAME = args.alist_username
    if args.alist_password:
        import utils.config
        utils.config.ALIST_PASSWORD = args.alist_password
    if args.alist_token:
        import utils.config
        utils.config.ALIST_TOKEN = args.alist_token
    if args.alist_path:
        import utils.config
        utils.config.ALIST_PATH = args.alist_path
        
    if args.webdav_url:
        import utils.config
        utils.config.WEBDAV_URL = args.webdav_url
    if args.webdav_username:
        import utils.config
        utils.config.WEBDAV_USERNAME = args.webdav_username
    if args.webdav_password:
        import utils.config
        utils.config.WEBDAV_PASSWORD = args.webdav_password
    if args.webdav_path:
        import utils.config
        utils.config.WEBDAV_PATH = args.webdav_path
        
    if args.local_path:
        import utils.config
        utils.config.LOCAL_PATH = args.local_path
    
    # 检查是否需要合并缓存
    if args.merge_cache:
        asyncio.run(merge_old_cache(args.merge_cache))
        return
    
    # 检查是否需要重置完整剧集缓存
    if args.force_check_all:
        asyncio.run(reset_cache())
    
    # 运行主程序
    if args.show:
        asyncio.run(main_async(specific_show=args.show))
    else:
        asyncio.run(main_async())

if __name__ == "__main__":
    main() 