#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
缓存管理模块
"""

import os
import json
import shutil
import asyncio
import aiofiles
from pathlib import Path
from typing import Dict, Any, Optional

from utils.helpers import CacheData
from utils.config import CACHE_FILE

async def merge_old_cache(old_cache_file: str, new_cache_file: str) -> bool:
    """
    合并旧的缓存格式到新的统一缓存格式
    
    Args:
        old_cache_file: 旧缓存文件路径
        new_cache_file: 新缓存文件路径
        
    Returns:
        合并是否成功
    """
    # 检查旧文件是否存在
    if not os.path.exists(old_cache_file):
        print(f"错误：{old_cache_file} 文件不存在")
        return False
    
    # 创建新的缓存格式
    new_cache = {
        "complete_dirs": {},
        "tmdb_map": {}
    }
    
    # 加载旧的TMDB缓存
    try:
        async with aiofiles.open(old_cache_file, 'r', encoding='utf-8', errors='replace') as f:
            content = await f.read()
            tmdb_cache = json.loads(content)
            print(f"已加载 {old_cache_file}，包含 {len(tmdb_cache)} 条记录")
            new_cache["tmdb_map"] = tmdb_cache
    except Exception as e:
        print(f"加载 {old_cache_file} 时出错: {e}")
        return False
    
    # 如果已存在新缓存文件,则需要合并而不是覆盖
    if os.path.exists(new_cache_file):
        try:
            async with aiofiles.open(new_cache_file, 'r', encoding='utf-8', errors='replace') as f:
                content = await f.read()
                existing_cache = json.loads(content)
                
                # 合并complete_dirs
                if "complete_dirs" in existing_cache:
                    new_cache["complete_dirs"] = existing_cache["complete_dirs"]
                
                # 合并tmdb_map(保留两者内容,新的覆盖旧的)
                if "tmdb_map" in existing_cache:
                    merged_tmdb_map = existing_cache["tmdb_map"].copy()
                    merged_tmdb_map.update(new_cache["tmdb_map"])
                    new_cache["tmdb_map"] = merged_tmdb_map
                
                print(f"已合并现有缓存文件 {new_cache_file}")
        except Exception as e:
            print(f"加载现有 {new_cache_file} 时出错: {e}")
            # 但继续保存新的内容
    
    # 保存新的统一缓存
    try:
        temp_file = Path(new_cache_file).with_suffix('.tmp')
        async with aiofiles.open(temp_file, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(new_cache, ensure_ascii=False, indent=2))
        
        # 原子性地替换原文件
        shutil.move(str(temp_file), new_cache_file)
        print(f"已创建新的统一缓存文件 {new_cache_file}")
        return True
    except Exception as e:
        print(f"保存 {new_cache_file} 时出错: {e}")
        if os.path.exists(temp_file):
            os.unlink(temp_file)
        return False

async def reset_cache() -> bool:
    """
    重置缓存中的完整目录记录,但保留TMDB映射
    
    Returns:
        操作是否成功
    """
    if not Path(CACHE_FILE).exists():
        print("缓存文件不存在,无需重置")
        return True
        
    try:
        cache = await load_cache()
        cache.complete_dirs = {}
        await save_cache(cache)
        print("已重置缓存,清除完整剧集记录")
        return True
    except Exception as e:
        print(f"重置缓存时出错: {e}")
        return False

async def load_cache() -> CacheData:
    """从本模块导入,确保一致性"""
    from utils.helpers import load_cache as load_cache_impl
    return await load_cache_impl()

async def save_cache(cache: CacheData) -> None:
    """从本模块导入,确保一致性"""
    from utils.helpers import save_cache as save_cache_impl
    await save_cache_impl(cache) 