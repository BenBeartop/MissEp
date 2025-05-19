#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
WebDAV存储后端实现
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional
from io import BytesIO
from xml.etree import ElementTree as ET
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, unquote, quote

import aiohttp
from aiohttp import BasicAuth

from storage.base import StorageBackend, StorageItem
from utils.config import WEBDAV_URL, WEBDAV_USERNAME, WEBDAV_PASSWORD, WEBDAV_PATH
from utils.helpers import extract_season_from_dirname, is_video_file


class WebDAVStorage(StorageBackend):
    """WebDAV存储后端实现"""
    
    def __init__(self, base_url: str = WEBDAV_URL, username: str = WEBDAV_USERNAME, 
                 password: str = WEBDAV_PASSWORD, base_path: str = WEBDAV_PATH):
        """
        初始化WebDAV存储
        
        Args:
            base_url: WebDAV服务器URL
            username: WebDAV用户名
            password: WebDAV密码
            base_path: 媒体文件的基础路径
        """
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.base_path = base_path.strip('/')
        self.auth = BasicAuth(username, password) if username and password else None
        
        # 调试信息
        print(f"WebDAV配置:")
        print(f"  基础URL: {self.base_url}")
        print(f"  基础路径: {self.base_path}")
        print(f"  认证信息: {'已配置' if self.auth else '未配置'}")
    
    def _normalize_path(self, path: str = "") -> str:
        """
        规范化路径，确保路径格式正确
        
        Args:
            path: 相对路径
            
        Returns:
            规范化后的路径
        """
        # 移除开头和结尾的斜杠
        path = path.strip('/')
        
        # 如果路径与基础路径的最后一部分相同，则跳过该路径
        base_dir_name = self.base_path.split('/')[-1]
        if path == base_dir_name:
            print(f"跳过与基础路径同名的目录: {path}")
            return self.base_path
        
        # 如果路径已经包含基础路径，不要重复添加
        if self.base_path and path.startswith(self.base_path):
            full_path = path
        else:
            base_path = self.base_path.strip('/')
            # 组合路径
            if path:
                if base_path:
                    full_path = f"{base_path}/{path}"
                else:
                    full_path = path
            else:
                full_path = base_path
        
        # URL编码路径中的特殊字符
        encoded_parts = [quote(part) for part in full_path.split('/') if part]
        encoded_path = '/'.join(encoded_parts)
        
        return encoded_path
    
    def _get_full_url(self, path: str = "") -> str:
        """
        获取完整的WebDAV URL
        
        Args:
            path: 相对路径
            
        Returns:
            完整URL
        """
        normalized_path = self._normalize_path(path)
        if normalized_path:
            return f"{self.base_url}/{normalized_path}"
        return self.base_url
    
    async def list_directories(self) -> List[str]:
        """
        获取WebDAV目录列表
        
        Returns:
            目录名称列表
        """
        url = self._get_full_url()
        print(f"请求URL: {url}")  # 调试信息
        
        # 准备PROPFIND请求
        headers = {
            "Depth": "1",
            "Content-Type": "application/xml; charset=utf-8"
        }
        data = """<?xml version="1.0" encoding="utf-8"?>
        <D:propfind xmlns:D="DAV:">
            <D:prop>
                <D:resourcetype/>
                <D:displayname/>
            </D:prop>
        </D:propfind>"""
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.request("PROPFIND", url, headers=headers, 
                                         data=data, auth=self.auth) as response:
                    if response.status == 404:
                        print(f"错误: 路径不存在 - {url}")
                        return []
                    elif response.status not in (207, 200):
                        error_text = await response.text()
                        print(f"WebDAV请求失败: HTTP {response.status}")
                        print(f"错误详情: {error_text}")
                        raise Exception(f"WebDAV请求失败: HTTP {response.status} - {error_text}")
                    
                    content = await response.text()
                    dirs = self._parse_directory_listing(content, True)
                    
                    # 如果目录名与基础路径的最后一部分相同，则跳过
                    base_dir_name = self.base_path.split('/')[-1]
                    return [d for d in dirs if d != base_dir_name]
        except aiohttp.ClientError as e:
            print(f"网络请求错误: {e}")
            raise Exception(f"WebDAV请求失败: {e}")
        except Exception as e:
            print(f"获取目录列表时出错: {e}")
            raise
    
    def _parse_directory_listing(self, content: str, dirs_only: bool = False) -> List[str]:
        """
        解析WebDAV目录列表XML
        
        Args:
            content: WebDAV PROPFIND响应内容
            dirs_only: 是否只返回目录
            
        Returns:
            路径名列表
        """
        try:
            # 解析XML
            root = ET.fromstring(content)
            
            # WebDAV命名空间
            ns = {
                'd': 'DAV:',
            }
            
            # 获取所有响应元素
            responses = root.findall('.//d:response', ns)
            
            result = []
            base_url = self._get_full_url()
            base_url_path = urlparse(base_url).path
            
            for response in responses:
                href = response.find('./d:href', ns).text
                href_path = unquote(urlparse(href).path)
                
                # 跳过基本URL路径
                if href_path == base_url_path:
                    continue
                
                # 判断是否是目录
                resourcetype = response.find('.//d:resourcetype', ns)
                is_dir = resourcetype is not None and resourcetype.find('.//d:collection', ns) is not None
                
                if dirs_only and not is_dir:
                    continue
                
                # 提取名称
                path_parts = href_path.rstrip('/').split('/')
                name = unquote(path_parts[-1])
                
                if name:  # 排除空名称
                    result.append(name)
            
            return result
        except ET.ParseError as e:
            print(f"XML解析错误: {e}")
            print(f"XML内容: {content}")
            raise Exception(f"解析WebDAV目录响应失败: XML解析错误 - {e}")
        except Exception as e:
            raise Exception(f"解析WebDAV目录响应失败: {e}")
    
    async def list_directory(self, path: str) -> List[StorageItem]:
        """
        列出指定WebDAV目录下的所有项目
        
        Args:
            path: 相对路径
            
        Returns:
            StorageItem列表
        """
        url = self._get_full_url(path)
        print(f"请求URL: {url}")  # 调试信息
        
        # 准备PROPFIND请求
        headers = {
            "Depth": "1",
            "Content-Type": "application/xml; charset=utf-8"
        }
        data = """<?xml version="1.0" encoding="utf-8"?>
        <D:propfind xmlns:D="DAV:">
            <D:prop>
                <D:resourcetype/>
                <D:getcontentlength/>
                <D:getlastmodified/>
                <D:displayname/>
            </D:prop>
        </D:propfind>"""
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.request("PROPFIND", url, headers=headers, 
                                         data=data, auth=self.auth) as response:
                    if response.status == 404:
                        print(f"错误: 路径不存在 - {url}")
                        return []
                    elif response.status not in (207, 200):
                        error_text = await response.text()
                        print(f"WebDAV请求失败: HTTP {response.status}")
                        print(f"错误详情: {error_text}")
                        raise Exception(f"WebDAV请求失败: HTTP {response.status} - {error_text}")
                    
                    content = await response.text()
                    return self._parse_storage_items(content, path)
        except aiohttp.ClientError as e:
            print(f"网络请求错误: {e}")
            raise Exception(f"WebDAV请求失败: {e}")
        except Exception as e:
            print(f"获取目录内容时出错: {e}")
            raise
    
    def _parse_storage_items(self, content: str, base_path: str) -> List[StorageItem]:
        """
        解析WebDAV响应为StorageItem列表
        
        Args:
            content: WebDAV PROPFIND响应内容
            base_path: 基础路径
            
        Returns:
            StorageItem列表
        """
        try:
            # 解析XML
            root = ET.fromstring(content)
            
            # WebDAV命名空间
            ns = {
                'd': 'DAV:',
            }
            
            # 获取所有响应元素
            responses = root.findall('.//d:response', ns)
            
            items = []
            url = self._get_full_url(base_path)
            url_path = urlparse(url).path
            
            for response in responses:
                href = response.find('./d:href', ns).text
                href_path = unquote(urlparse(href).path)
                
                # 跳过基本URL路径
                if href_path == url_path:
                    continue
                
                # 获取属性
                prop = response.find('.//d:prop', ns)
                
                # 判断是否是目录
                resourcetype = prop.find('./d:resourcetype', ns)
                is_dir = resourcetype is not None and resourcetype.find('./d:collection', ns) is not None
                
                # 获取文件大小
                size = 0
                size_elem = prop.find('./d:getcontentlength', ns)
                if size_elem is not None and size_elem.text:
                    try:
                        size = int(size_elem.text)
                    except ValueError:
                        size = 0
                
                # 获取修改时间
                modified_time = ""
                modified_elem = prop.find('./d:getlastmodified', ns)
                if modified_elem is not None and modified_elem.text:
                    modified_time = modified_elem.text
                
                # 提取名称
                path_parts = href_path.rstrip('/').split('/')
                name = unquote(path_parts[-1])
                
                if name:  # 排除空名称
                    storage_item = StorageItem(
                        path=base_path,
                        name=name,
                        is_dir=is_dir,
                        size=size,
                        modified_time=modified_time
                    )
                    items.append(storage_item)
            
            return items
        except ET.ParseError as e:
            print(f"XML解析错误: {e}")
            print(f"XML内容: {content}")
            raise Exception(f"解析WebDAV响应失败: XML解析错误 - {e}")
        except Exception as e:
            raise Exception(f"解析WebDAV响应失败: {e}")
    
    async def get_directory_structure(self, dir_name: str) -> List[Dict[str, Any]]:
        """
        递归获取WebDAV目录结构和文件
        
        Args:
            dir_name: 目录名称
            
        Returns:
            包含文件信息的字典列表
        """
        try:
            files = []
            
            # 获取目录内容
            items = await self.list_directory(dir_name)
            
            # 检查是否有季目录
            season_dirs = []
            regular_files = []
            
            for item in items:
                if item.is_dir:
                    if extract_season_from_dirname(item.name) is not None:
                        season_dirs.append(item)
                elif is_video_file(item.name):
                    regular_files.append(item)
            
            # 如果有季目录，优先处理季目录
            if season_dirs:
                for season_dir in season_dirs:
                    season_number = extract_season_from_dirname(season_dir.name)
                    if season_number is not None:
                        season_path = f"{dir_name}/{season_dir.name}"
                        season_items = await self.list_directory(season_path)
                        
                        for item in season_items:
                            if not item.is_dir and is_video_file(item.name):
                                files.append({
                                    "path": f"{season_dir.name}/{item.name}",
                                    "season": season_number
                                })
            
            # 处理非季目录中的视频文件
            for item in regular_files:
                files.append({
                    "path": item.name,
                    "season": None
                })
            
            return files
            
        except Exception as e:
            raise Exception(f"获取WebDAV目录结构失败: {e}") 