#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
辅助工具模块,包含各种通用函数
"""

import re
import json
import asyncio
import aiofiles
import shutil
import functools
import time
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Any, Callable
from dataclasses import dataclass
from contextlib import asynccontextmanager

from utils.config import SKIPPED_LOG, CACHE_FILE

# 自定义异常类
class MediaProcessError(Exception):
    """媒体处理相关错误的基类"""
    def __init__(self, message: str, source: str = "unknown"):
        self.source = source
        super().__init__(f"[{source}] {message}")

def async_error_handler(source: str = "unknown"):
    """
    异步函数错误处理装饰器
    
    Args:
        source: 错误来源标识
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except MediaProcessError:
                raise
            except Exception as e:
                raise MediaProcessError(str(e), source)
        return wrapper
    return decorator

# 预编译正则表达式
SEASON_PATTERNS = [
    re.compile(r"[sS]eason\s*(\d+)"),     # Season 1
    re.compile(r"[sS](\d+)"),             # S01 
    re.compile(r"第(\d+)季")               # 第1季
]

# 全局锁,用于文件操作
file_lock = asyncio.Lock()

@asynccontextmanager
async def log_file_lock():
    """文件锁的上下文管理器"""
    async with file_lock:
        yield

async def log_skipped(filename: str):
    """记录跳过的文件,使用异步IO和文件锁"""
    async with log_file_lock():
        async with aiofiles.open(SKIPPED_LOG, "a", encoding="utf-8") as f:
            await f.write(f"{filename}\n")

# 从剧集名称中提取年份
def extract_year(title: str) -> Optional[int]:
    """从剧集名称中提取年份"""
    year_match = re.search(r"\((\d{4})\)", title)
    if year_match:
        return int(year_match.group(1))
    return None

# 从季节目录名中提取季号
def extract_season_from_dirname(dirname: str) -> Optional[int]:
    """从目录名中提取季号"""
    for pattern in SEASON_PATTERNS:
        match = pattern.search(dirname)
        if match:
            return int(match.group(1))
    return None

def is_video_file(filename: str) -> bool:
    """检查是否是视频文件"""
    from utils.config import VIDEO_EXTENSIONS
    return Path(filename).suffix.lower() in VIDEO_EXTENSIONS

# 解析文件名：支持中英文命名
def parse_filename(filepath: str, known_season: Optional[int] = None) -> Optional[Tuple[int, int]]:
    """
    解析文件名,提取季号和集号
    
    Args:
        filepath: 文件路径
        known_season: 已知的季号(如果有)
        
    Returns:
        (season, episode)元组或None
    """
    filename = filepath.split('/')[-1]  # 获取文件名
    
    patterns = [
        # 单集剧集格式
        r"[sS](\d{1,2})[eE](\d{1,2})",              # S01E01 格式
        r"[sS]eason\s*(\d{1,2}).*?[eE]pisode\s*(\d{1,2})",  # Season 1 Episode 1
        r"(\d{1,2})x(\d{1,2})",                     # 1x01 格式  
        r"[第](\d{1,2})[季].*?[第](\d{1,2})[集]",   # 第1季第1集 格式
        r"[.\s_](\d{1,2})(\d{2})[.\s_]"             # 101, 102 格式（第1季第1集）
    ]
    
    for pattern in patterns:
        match = re.search(pattern, filename, re.IGNORECASE)
        if match:
            season = int(match.group(1))
            episode = int(match.group(2))
            return season, episode
    
    # 如果有已知季号，尝试仅匹配集号
    if known_season is not None:
        episode_patterns = [
            r"[eE](\d{1,2})",                 # E01
            r"[eE]pisode\s*(\d{1,2})",        # Episode 1
            r"[第](\d{1,2})[集]",             # 第1集
            r"(\d{1,2})(?=\.|$|\s+)"          # 单独的数字，可能是集号
        ]
        
        for pattern in episode_patterns:
            match = re.search(pattern, filename, re.IGNORECASE)
            if match:
                return known_season, int(match.group(1))
    
    return None

@dataclass
class CacheData:
    """缓存数据结构"""
    complete_dirs: Dict[str, Dict[str, str]]
    tmdb_map: Dict[str, int]

    @classmethod
    def create_empty(cls) -> 'CacheData':
        return cls(complete_dirs={}, tmdb_map={})
    
    def is_complete_dir(self, dir_name: str) -> bool:
        """检查目录是否已完整"""
        return dir_name in self.complete_dirs
    
    def mark_complete_dir(self, dir_name: str, tmdb_id: int):
        """标记目录为完整"""
        self.complete_dirs[dir_name] = {
            "checked_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "tmdb_id": tmdb_id
        }
    
    def get_tmdb_info(self, title: str) -> Tuple[Optional[int], Optional[str]]:
        """获取TMDB信息"""
        if title in self.tmdb_map:
            tmdb_id = self.tmdb_map[title]
            # 查询名称,如果没有名称信息则使用标题
            tmdb_name = title
            for name, id in self.tmdb_map.items():
                if id == tmdb_id and name != title:
                    tmdb_name = name.split(" (")[0]  # 移除年份
                    break
            return tmdb_id, tmdb_name
        return None, None
    
    def add_tmdb_mapping(self, title: str, tmdb_id: int):
        """添加TMDB映射"""
        self.tmdb_map[title] = tmdb_id

@asynccontextmanager
async def atomic_write(filepath: Path):
    """原子写入文件的上下文管理器"""
    temp_path = filepath.with_suffix('.tmp')
    try:
        async with aiofiles.open(temp_path, 'w', encoding='utf-8') as f:
            yield f
        # 原子性地替换原文件
        temp_path.replace(filepath)
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise

async def save_cache(cache: CacheData):
    """保存缓存文件,使用临时文件确保原子性"""
    cache_path = Path(CACHE_FILE)
    cache_data = {
        "complete_dirs": cache.complete_dirs,
        "tmdb_map": cache.tmdb_map
    }
    
    async with atomic_write(cache_path) as f:
        await f.write(json.dumps(cache_data, ensure_ascii=False, indent=2))

async def load_cache() -> CacheData:
    """加载缓存文件,使用异步IO"""
    cache_path = Path(CACHE_FILE)
    if not cache_path.exists():
        return CacheData.create_empty()
    
    try:
        async with aiofiles.open(cache_path, "r", encoding="utf-8") as f:
            content = await f.read()
            data = json.loads(content)
            return CacheData(
                complete_dirs=data.get("complete_dirs", {}),
                tmdb_map=data.get("tmdb_map", {})
            )
    except (json.JSONDecodeError, IOError) as e:
        print(f"加载缓存文件出错: {e}")
        # 如果缓存文件损坏,创建备份并返回空缓存
        if cache_path.exists():
            backup_path = cache_path.with_suffix('.bak')
            shutil.copy2(cache_path, backup_path)
            print(f"已创建损坏缓存文件的备份: {backup_path}")
        return CacheData.create_empty()

async def reset_cache():
    """重置完整剧集缓存"""
    cache = await load_cache()
    cache.complete_dirs = {}  # 清空完整剧集记录
    await save_cache(cache)
    print("已重置完整剧集缓存")

async def merge_old_cache(old_cache_file: str):
    """
    合并旧缓存文件到新格式
    
    Args:
        old_cache_file: 旧缓存文件路径
    """
    old_path = Path(old_cache_file)
    if not old_path.exists():
        print(f"旧缓存文件不存在: {old_cache_file}")
        return
    
    try:
        # 读取旧缓存
        async with aiofiles.open(old_path, "r", encoding="utf-8") as f:
            content = await f.read()
            old_data = json.loads(content)
        
        # 加载当前缓存
        cache = await load_cache()
        
        # 合并TMDB映射
        if isinstance(old_data, dict):
            cache.tmdb_map.update(old_data)
        
        # 保存合并后的缓存
        await save_cache(cache)
        print(f"已合并旧缓存文件: {old_cache_file}")
        
        # 创建备份
        backup_path = old_path.with_suffix('.bak')
        shutil.copy2(old_path, backup_path)
        print(f"已创建旧缓存文件的备份: {backup_path}")
        
    except (json.JSONDecodeError, IOError) as e:
        print(f"合并缓存文件失败: {e}") 