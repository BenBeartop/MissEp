#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
本地文件系统存储后端实现
"""

import os
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

from storage.base import StorageBackend, StorageItem
from utils.config import LOCAL_PATH
from utils.helpers import extract_season_from_dirname, is_video_file


class LocalStorage(StorageBackend):
    """本地文件系统存储后端"""
    
    def __init__(self, local_path: str = LOCAL_PATH):
        """
        初始化本地存储
        
        Args:
            local_path: 本地文件系统路径
        """
        self.local_path = local_path
    
    async def list_directories(self) -> List[str]:
        """
        获取本地文件系统中的目录列表
        
        Returns:
            目录名称列表
        """
        try:
            base_path = Path(self.local_path)
            if not base_path.exists() or not base_path.is_dir():
                raise FileNotFoundError(f"路径不存在或不是目录: {self.local_path}")
            
            dirs = []
            # 使用loop.run_in_executor运行阻塞IO操作
            loop = asyncio.get_event_loop()
            entries = await loop.run_in_executor(None, lambda: list(base_path.iterdir()))
            
            for entry in entries:
                if entry.is_dir():
                    dirs.append(entry.name)
            
            return dirs
        except Exception as e:
            raise Exception(f"获取目录列表失败: {e}")
    
    async def list_directory(self, path: str) -> List[StorageItem]:
        """
        列出指定目录下的所有项目
        
        Args:
            path: 相对路径
            
        Returns:
            StorageItem列表
        """
        try:
            full_path = Path(self.local_path) / path if path else Path(self.local_path)
            if not full_path.exists() or not full_path.is_dir():
                raise FileNotFoundError(f"路径不存在或不是目录: {full_path}")
            
            items = []
            loop = asyncio.get_event_loop()
            entries = await loop.run_in_executor(None, lambda: list(full_path.iterdir()))
            
            for entry in entries:
                # 获取文件属性
                stat = await loop.run_in_executor(None, lambda: entry.stat())
                modified_time = datetime.fromtimestamp(stat.st_mtime).isoformat()
                
                storage_item = StorageItem(
                    path=path,
                    name=entry.name,
                    is_dir=entry.is_dir(),
                    size=stat.st_size,
                    modified_time=modified_time
                )
                items.append(storage_item)
            
            return items
        except Exception as e:
            raise Exception(f"获取目录内容失败: {e}")
    
    async def get_directory_structure(self, dir_name: str) -> List[Dict[str, Any]]:
        """
        递归获取目录结构和文件
        
        Args:
            dir_name: 目录名称
            
        Returns:
            包含文件信息的字典列表
        """
        try:
            base_dir = Path(self.local_path) / dir_name
            if not base_dir.exists() or not base_dir.is_dir():
                raise FileNotFoundError(f"路径不存在或不是目录: {base_dir}")
            
            files = []
            
            # 使用异步方式遍历目录
            async def scan_directory(current_dir: Path, relative_path: str = ""):
                loop = asyncio.get_event_loop()
                entries = await loop.run_in_executor(None, lambda: list(current_dir.iterdir()))
                
                for entry in entries:
                    # 计算相对路径
                    rel_path = f"{relative_path}/{entry.name}" if relative_path else entry.name
                    
                    if entry.is_dir():
                        # 检查是否是季目录
                        season_number = extract_season_from_dirname(entry.name)
                        if season_number is not None:
                            # 找到季目录，扫描其中的文件
                            await scan_season_directory(entry, rel_path, season_number)
                        else:
                            # 不是明确的季目录，递归检查
                            await scan_directory(entry, rel_path)
                    elif is_video_file(entry.name):
                        files.append({"path": rel_path, "season": None})
            
            async def scan_season_directory(season_dir: Path, relative_path: str, season_number: int):
                loop = asyncio.get_event_loop()
                entries = await loop.run_in_executor(None, lambda: list(season_dir.iterdir()))
                
                for entry in entries:
                    if not entry.is_dir() and is_video_file(entry.name):
                        files.append({
                            "path": f"{relative_path}/{entry.name}",
                            "season": season_number
                        })
            
            # 开始扫描
            await scan_directory(base_dir)
            return files
        except Exception as e:
            raise Exception(f"获取目录结构失败: {e}") 