#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Alist存储后端实现
"""

import asyncio
import aiohttp
import json
from typing import Dict, List, Any, Optional

from storage.base import StorageBackend, StorageItem
from utils.config import ALIST_URL, ALIST_USERNAME, ALIST_PASSWORD, ALIST_TOKEN, ALIST_PATH
from utils.helpers import extract_season_from_dirname, is_video_file


class AlistStorage(StorageBackend):
    """Alist存储后端实现"""
    
    def __init__(self, base_url: str = ALIST_URL, username: str = ALIST_USERNAME, 
                 password: str = ALIST_PASSWORD, token: str = ALIST_TOKEN, 
                 base_path: str = ALIST_PATH):
        """
        初始化Alist存储
        
        Args:
            base_url: Alist服务器URL
            username: Alist用户名
            password: Alist密码
            token: Alist访问令牌
            base_path: 媒体文件的基础路径
        """
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.token = token
        self.base_path = base_path.strip('/')
    
    async def _get_token(self) -> str:
        """
        获取或刷新Alist访问令牌
        
        Returns:
            访问令牌
        """
        if self.token:
            return self.token
        
        if not self.username or not self.password:
            raise Exception("未提供Alist凭据")
        
        url = f"{self.base_url}/api/auth/login"
        data = {
            "username": self.username,
            "password": self.password
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data) as response:
                    if response.status != 200:
                        raise Exception(f"Alist登录失败: HTTP {response.status}")
                    
                    result = await response.json()
                    if result.get("code") != 200:
                        raise Exception(f"Alist登录失败: {result.get('message')}")
                    
                    self.token = result.get("data", {}).get("token")
                    return self.token
        except Exception as e:
            raise Exception(f"获取Alist令牌失败: {e}")
    
    async def _make_api_request(self, endpoint: str, method: str = "GET", data: Dict = None) -> Dict:
        """
        向Alist API发送请求
        
        Args:
            endpoint: API端点
            method: HTTP方法
            data: 请求数据
            
        Returns:
            API响应
        """
        token = await self._get_token()
        url = f"{self.base_url}{endpoint}"
        
        headers = {"Authorization": token} if token else {}
        
        try:
            async with aiohttp.ClientSession() as session:
                if method == "GET":
                    response = await session.get(url, headers=headers)
                elif method == "POST":
                    response = await session.post(url, json=data, headers=headers)
                else:
                    raise Exception(f"不支持的HTTP方法: {method}")
                
                if response.status != 200:
                    raise Exception(f"Alist API请求失败: HTTP {response.status}")
                
                result = await response.json()
                if result.get("code") != 200:
                    raise Exception(f"Alist API错误: {result.get('message')}")
                
                return result
        except Exception as e:
            raise Exception(f"Alist API请求失败: {e}")
    
    async def _list_files(self, path: str) -> Dict:
        """
        列出Alist目录内容
        
        Args:
            path: 路径
            
        Returns:
            目录内容
        """
        endpoint = "/api/fs/list"
        full_path = f"{self.base_path}/{path}" if path else self.base_path
        data = {
            "path": f"/{full_path}".replace("//", "/")
        }
        
        return await self._make_api_request(endpoint, "POST", data)
    
    async def list_directories(self) -> List[str]:
        """
        获取Alist目录列表
        
        Returns:
            目录名称列表
        """
        try:
            result = await self._list_files("")
            content = result.get("data", {}).get("content", [])
            
            dirs = []
            for item in content:
                if item.get("is_dir"):
                    dirs.append(item.get("name"))
            
            return dirs
        except Exception as e:
            raise Exception(f"获取Alist目录列表失败: {e}")
    
    async def list_directory(self, path: str) -> List[StorageItem]:
        """
        列出指定Alist目录下的所有项目
        
        Args:
            path: 相对路径
            
        Returns:
            StorageItem列表
        """
        try:
            result = await self._list_files(path)
            content = result.get("data", {}).get("content", [])
            
            items = []
            for item in content:
                storage_item = StorageItem(
                    path=path,
                    name=item.get("name"),
                    is_dir=item.get("is_dir", False),
                    size=item.get("size", 0),
                    modified_time=item.get("modified", "")
                )
                items.append(storage_item)
            
            return items
        except Exception as e:
            raise Exception(f"获取Alist目录内容失败: {e}")
    
    async def get_directory_structure(self, dir_name: str) -> List[Dict[str, Any]]:
        """
        递归获取Alist目录结构和文件
        
        Args:
            dir_name: 目录名称
            
        Returns:
            包含文件信息的字典列表
        """
        try:
            files = []
            
            # 递归扫描目录
            async def scan_directory(path: str, relative_path: str = ""):
                items = await self.list_directory(path)
                
                for item in items:
                    # 计算当前项的路径
                    item_path = f"{path}/{item.name}" if path else item.name
                    item_rel_path = f"{relative_path}/{item.name}" if relative_path else item.name
                    
                    if item.is_dir:
                        # 检查是否是季目录
                        season_number = extract_season_from_dirname(item.name)
                        if season_number is not None:
                            # 找到季目录，扫描其中的文件
                            await scan_season_directory(item_path, item_rel_path, season_number)
                        else:
                            # 不是明确的季目录，递归检查
                            await scan_directory(item_path, item_rel_path)
                    elif is_video_file(item.name):
                        files.append({"path": item_rel_path, "season": None})
            
            async def scan_season_directory(path: str, relative_path: str, season_number: int):
                items = await self.list_directory(path)
                
                for item in items:
                    if not item.is_dir and is_video_file(item.name):
                        files.append({
                            "path": f"{relative_path}/{item.name}",
                            "season": season_number
                        })
            
            # 开始扫描
            await scan_directory(dir_name)
            return files
        except Exception as e:
            raise Exception(f"获取Alist目录结构失败: {e}") 