#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
MoviePilot API交互模块
"""

import asyncio
import aiohttp
import json
import logging
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from contextlib import asynccontextmanager

from utils.config import (
    MOVIEPILOT_URL, 
    MOVIEPILOT_USERNAME, 
    MOVIEPILOT_PASSWORD,
    TIMEOUT
)
from utils.helpers import MediaProcessError, async_error_handler

logger = logging.getLogger(__name__)

# MoviePilot配置
access_token: Optional[str] = None

@dataclass
class MoviePilotResult:
    """MoviePilot操作结果"""
    success: bool
    message: str
    data: Optional[Dict] = None

@asynccontextmanager
async def moviepilot_session():
    """MoviePilot会话管理器，自动处理登录和令牌刷新"""
    global access_token
    
    if not access_token:
        if not await login():
            raise MediaProcessError("无法登录MoviePilot", "MoviePilot")
    
    try:
        yield
    except aiohttp.ClientResponseError as e:
        if e.status == 401:  # 令牌过期
            if await login():
                yield
            else:
                raise MediaProcessError("令牌刷新失败", "MoviePilot")
        else:
            raise MediaProcessError(f"HTTP错误: {e.status}", "MoviePilot")

@async_error_handler("MoviePilot")
async def login() -> bool:
    """
    登录MoviePilot并获取访问令牌
    
    Returns:
        登录是否成功
    """
    global access_token
    
    url = f"{MOVIEPILOT_URL}/api/v1/login/access-token"
    payload = f"username={MOVIEPILOT_USERNAME}&password={MOVIEPILOT_PASSWORD}"
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=payload, headers=headers, timeout=TIMEOUT) as response:
            if response.status == 200:
                data = await response.json()
                if 'access_token' in data:
                    token = data['token_type'] + ' ' + data['access_token']
                    access_token = token
                    logger.info("MoviePilot登录成功")
                    return True
                else:
                    logger.error(f"MoviePilot登录失败: {data}")
            else:
                logger.error(f"MoviePilot登录失败: HTTP状态码 {response.status}")
    
    return False

@async_error_handler("MoviePilot")
async def search(title: str) -> Tuple[bool, List[Dict]]:
    """
    搜索资源
    
    Args:
        title: 搜索关键词
        
    Returns:
        (success, results): 成功状态和搜索结果列表
    """
    async with moviepilot_session():
        from urllib.parse import quote
        url = f"{MOVIEPILOT_URL}/api/v1/search/title?keyword={quote(title)}"
        headers = {'Authorization': access_token}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=TIMEOUT) as response:
                data = await response.json()
                results = []
                if data.get("success", False):
                    data = data["data"]
                    for item in data:
                        meta_info = item.get("meta_info", {})
                        torrent_info = item.get("torrent_info", {})
                        
                        seeders = torrent_info.get("seeders", "0")
                        try:
                            seeders = int(seeders) if seeders else 0
                        except (ValueError, TypeError):
                            seeders = 0
                        result = {
                            "title": meta_info.get("title", ""),
                            "year": meta_info.get("year", ""),
                            "type": meta_info.get("type", ""),
                            "resource_pix": meta_info.get("resource_pix", ""),
                            "video_encode": meta_info.get("video_encode", ""),
                            "audio_encode": meta_info.get("audio_encode", ""),
                            "resource_team": meta_info.get("resource_team", ""),
                            "seeders": seeders,
                            "size": torrent_info.get("size", "0"),
                            "labels": torrent_info.get("labels", ""),
                            "description": torrent_info.get("description", ""),
                            "torrent_info": torrent_info,
                        }
                        results.append(result)
                    
                # 按做种数排序
                results.sort(key=lambda x: x["seeders"], reverse=True)
                
                logger.info("MoviePilot搜索成功!")
                return True, results

async def create_subscribe(subscribe_info: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    创建订阅
    
    Args:
        subscribe_info: 订阅信息字典，包含title, type, tmdb_id等
        
    Returns:
        (success, subscribe_id): 成功状态和订阅ID
    """
    if not access_token:
        logger.error("MoviePilot未登录，无法创建订阅")
        return False, None
    
    url = f"{MOVIEPILOT_URL}/api/v1/subscribe"
    
    # 构建请求数据
    data = {
        "name": subscribe_info['title'],
        "type": subscribe_info.get('type', '电视剧'),
        "year": str(subscribe_info.get('year', '')) if subscribe_info.get('year') else "",
        "tmdbid": subscribe_info.get('tmdb_id') or None,
        "doubanid": subscribe_info.get('douban_id') or None,
        "season": subscribe_info.get('season', 1),
        "best_version": 0
    }
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': access_token
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers=headers, timeout=TIMEOUT) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("success", False):
                        logger.info(f"MoviePilot订阅媒体成功: {subscribe_info['title']} 第{subscribe_info.get('season', 1)}季")
                        return True, data.get("data", {}).get("id")
                    else:
                        logger.error(f"MoviePilot订阅媒体失败: {data}")
                elif response.status == 401:
                    logger.error("MoviePilot令牌已过期，请重新登录")
                    # 尝试重新登录
                    if await login():
                        return await create_subscribe(subscribe_info)
                    return False, None
                else:
                    logger.error(f"MoviePilot订阅媒体失败: HTTP状态码 {response.status}")
    except aiohttp.ClientError as e:
        logger.error(f"MoviePilot订阅媒体请求出错: {str(e)}")
    except json.JSONDecodeError as e:
        logger.error(f"MoviePilot订阅媒体响应解析失败: {str(e)}")
    except Exception as e:
        logger.error(f"MoviePilot订阅媒体过程出错: {str(e)}")
    
    return False, None

async def add_download_task(param: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    添加下载任务
    
    Args:
        param: 下载参数字典
        
    Returns:
        (success, task_id): 成功状态和任务ID
    """
    if not access_token:
        logger.error("MoviePilot未登录，无法添加下载任务")
        return False, None
    
    url = f"{MOVIEPILOT_URL}/api/v1/download/add"
    headers = {
        'Content-Type': 'application/json',
        'Authorization': access_token
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=param, headers=headers, timeout=TIMEOUT) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("success", False):
                        logger.info(f"MoviePilot添加下载任务成功, ID: {data['data']['download_id']}")
                        return True, data["data"]["download_id"]
                    else:
                        logger.error(f"MoviePilot添加下载任务失败: {data}")
                elif response.status == 401:
                    logger.error("MoviePilot令牌已过期，请重新登录")
                    # 尝试重新登录
                    if await login():
                        return await add_download_task(param)
                    return False, None
                else:
                    logger.error(f"MoviePilot添加下载任务失败: HTTP状态码 {response.status}")
    except aiohttp.ClientError as e:
        logger.error(f"MoviePilot添加下载任务请求出错: {str(e)}")
    except json.JSONDecodeError as e:
        logger.error(f"MoviePilot添加下载任务响应解析失败: {str(e)}")
    except Exception as e:
        logger.error(f"MoviePilot添加下载任务过程出错: {str(e)}")
    
    return False, None

async def handle_missing_episodes(
    show_name: str,
    tmdb_id: int,
    season: int,
    episodes: List[int],
    auto_subscribe: bool = True,
    auto_download: bool = False,
    subscribe_threshold: int = 0
) -> MoviePilotResult:
    """
    处理缺失剧集
    
    Args:
        show_name: 剧集名称
        tmdb_id: TMDB ID
        season: 季号
        episodes: 缺失的集号列表
        auto_subscribe: 是否自动订阅缺失剧集
        auto_download: 是否尝试直接下载缺失剧集
        subscribe_threshold: 订阅阈值(缺失集数超过此数量才订阅整季)
        
    Returns:
        处理结果
    """
    # 检测是否已登录
    if not access_token:
        if not await login():
            return MoviePilotResult(
                success=False,
                message="MoviePilot登录失败",
                data=None
            )
    
    import re
    from utils.helpers import extract_year
    
    year = extract_year(show_name)
    clean_title = re.sub(r"\s*\(\d{4}\).*$", "", show_name)
    
    # 默认订阅开启
    should_subscribe = auto_subscribe
    
    # 检查订阅阈值条件
    if subscribe_threshold > 0 and len(episodes) <= subscribe_threshold:
        should_subscribe = False
    
    # 对于符合订阅条件的情况
    if should_subscribe:
        # 创建订阅
        subscribe_info = {
            'title': clean_title,
            'type': '电视剧',
            'year': year,
            'tmdb_id': tmdb_id,
            'douban_id': None,
            'season': season
        }
        
        print(f"  尝试订阅 {clean_title} 第{season}季")
        try:
            success, subscribe_id = await create_subscribe(subscribe_info)
            if success:
                return MoviePilotResult(
                    success=True,
                    message=f"已订阅 {clean_title} 第{season}季",
                    data={"subscribe_id": subscribe_id}
                )
            else:
                print(f"  ❌ 订阅 {clean_title} 第{season}季失败")
                if not auto_download:
                    return MoviePilotResult(
                        success=False,
                        message="订阅失败",
                        data=None
                    )
        except Exception as e:
            print(f"  订阅出错: {e}")
            if not auto_download:
                return MoviePilotResult(
                    success=False,
                    message=f"订阅出错: {e}",
                    data=None
                )
    
    # 对于下载单集的情况
    if auto_download and (not should_subscribe or (should_subscribe and not success)):
        search_term = f"{clean_title} S{season:02d}"
        print(f"  🔍 在MoviePilot中搜索: {search_term}")
        
        try:
            success, results = await search(search_term)
            if success and results:
                # 筛选可能的匹配项
                for result in results:
                    # 查找匹配的剧集
                    if any(f"S{season:02d}E{ep:02d}" in result["title"] for ep in episodes):
                        print(f"  找到匹配的资源: {result['title']}")
                        
                        # 下载参数
                        download_params = {
                            "id": result["torrent_info"]["id"],
                            "site": result["torrent_info"]["site"],
                            "enclosure": result["torrent_info"]["enclosure"],
                        }
                        
                        # 添加下载任务
                        try:
                            download_success, download_id = await add_download_task(download_params)
                            if download_success:
                                return MoviePilotResult(
                                    success=True,
                                    message=f"已添加下载任务: {result['title']}",
                                    data={"download_id": download_id}
                                )
                        except Exception as e:
                            print(f"  添加下载任务失败: {e}")
                            continue
                
                return MoviePilotResult(
                    success=False,
                    message="未找到合适的资源",
                    data=None
                )
            else:
                return MoviePilotResult(
                    success=False,
                    message="搜索失败",
                    data=None
                )
        except Exception as e:
            return MoviePilotResult(
                success=False,
                message=f"搜索出错: {e}",
                data=None
            )
    
    return MoviePilotResult(
        success=False,
        message="未执行任何操作",
        data=None
    ) 