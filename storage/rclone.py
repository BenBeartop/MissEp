#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Rclone存储后端实现
"""

import json
import asyncio
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path

from storage.base import StorageBackend, StorageItem
from utils.config import RCLONE_REMOTE
from utils.helpers import MediaProcessError, extract_season_from_dirname, is_video_file


class RcloneStorage(StorageBackend):
    """Rclone存储后端实现"""
    
    def __init__(self, remote_path: str = RCLONE_REMOTE):
        """
        初始化Rclone存储
        
        Args:
            remote_path: Rclone远程路径
        """
        self.remote_path = remote_path
    
    async def _run_rclone(self, args: List[str]) -> bytes:
        """运行rclone命令"""
        process = await asyncio.create_subprocess_exec(
            'rclone',
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            raise MediaProcessError(f"rclone命令执行失败: {stderr.decode()}", "Rclone")
        
        return stdout
    
    async def list_directories(self) -> List[str]:
        """获取根目录下的目录列表"""
        try:
            stdout = await self._run_rclone(['lsjson', self.remote_path])
            items = json.loads(stdout)
            return [item['Name'] for item in items if item['IsDir']]
        except Exception as e:
            raise MediaProcessError(f"获取目录列表失败: {e}", "Rclone")
    
    async def list_directory(self, path: str) -> List[StorageItem]:
        """
        列出指定目录下的所有项目
        
        Args:
            path: 相对路径
            
        Returns:
            StorageItem列表
        """
        full_path = f"{self.remote_path}/{path}" if path else self.remote_path
        
        try:
            proc = await asyncio.create_subprocess_exec(
                "rclone", "lsjson", full_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode != 0:
                raise MediaProcessError(f"无法读取目录 {path}: {stderr.decode()}", "Rclone")
            
            items_data = json.loads(stdout.decode())
            items = []
            
            for item in items_data:
                storage_item = StorageItem(
                    path=path,
                    name=item["Path"],
                    is_dir=item["IsDir"],
                    size=item.get("Size", 0),
                    modified_time=item.get("ModTime", "")
                )
                items.append(storage_item)
            
            return items
        except json.JSONDecodeError as e:
            raise MediaProcessError(f"解析目录内容失败: {e}", "Rclone")
        except Exception as e:
            raise MediaProcessError(f"获取目录内容失败: {e}", "Rclone")
    
    async def get_directory_structure(self, dir_name: str) -> List[Dict[str, Any]]:
        """
        递归获取目录结构和文件
        
        Args:
            dir_name: 目录名称
            
        Returns:
            包含文件信息的字典列表
        """
        remote_path = f"{self.remote_path}/{dir_name}"
        
        try:
            # 使用lsjson命令获取目录内容
            proc = await asyncio.create_subprocess_exec(
                "rclone", "lsjson", remote_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode != 0:
                raise MediaProcessError(f"无法读取目录 {dir_name}: {stderr.decode()}", "Rclone")
            
            items = json.loads(stdout.decode())
            files = []
            
            for item in items:
                item_path = item["Path"]
                if item["IsDir"]:
                    # 检查是否是季目录
                    season_number = extract_season_from_dirname(item_path)
                    if season_number is not None:
                        # 找到季目录,获取其中的文件
                        season_path = f"{remote_path}/{item_path}"
                        season_files = await self._get_season_files(season_path, season_number, item_path)
                        files.extend(season_files)
                    else:
                        # 不是明确的季目录,递归检查
                        subdir_path = f"{remote_path}/{item_path}"
                        subdir_files = await self._get_regular_files(subdir_path, item_path)
                        files.extend(subdir_files)
                elif is_video_file(item_path):
                    files.append({"path": item_path, "season": None})
            
            return files
        except json.JSONDecodeError as e:
            raise MediaProcessError(f"解析目录内容失败: {e}", "Rclone")
        except Exception as e:
            raise MediaProcessError(f"获取目录结构失败: {e}", "Rclone")
    
    async def _get_season_files(self, season_path: str, season_number: int, relative_path: str) -> List[Dict[str, Any]]:
        """
        获取季目录中的视频文件
        
        Args:
            season_path: 季目录完整路径
            season_number: 季号
            relative_path: 相对路径
            
        Returns:
            包含文件信息的字典列表
        """
        try:
            proc = await asyncio.create_subprocess_exec(
                "rclone", "lsf", season_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode != 0:
                raise MediaProcessError(f"无法读取季目录: {stderr.decode()}", "Rclone")
            
            files = []
            for file in stdout.decode().splitlines():
                if is_video_file(file):
                    files.append({
                        "path": f"{relative_path}/{file}",
                        "season": season_number
                    })
            return files
        except Exception as e:
            print(f"  无法读取季目录 {season_path}: {e}")
            return []
    
    async def _get_regular_files(self, dir_path: str, relative_path: str) -> List[Dict[str, Any]]:
        """
        获取普通目录中的视频文件
        
        Args:
            dir_path: 目录完整路径
            relative_path: 相对路径
            
        Returns:
            包含文件信息的字典列表
        """
        try:
            proc = await asyncio.create_subprocess_exec(
                "rclone", "lsf", dir_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode != 0:
                return []
            
            files = []
            for file in stdout.decode().splitlines():
                if is_video_file(file):
                    files.append({
                        "path": f"{relative_path}/{file}",
                        "season": None
                    })
            return files
        except Exception:
            return [] 