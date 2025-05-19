#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
存储后端基类
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from pathlib import Path


@dataclass
class StorageItem:
    """表示存储中的项目（文件或目录）"""
    path: str
    name: str
    is_dir: bool
    size: int = 0
    modified_time: str = ""
    
    @property
    def full_path(self) -> str:
        """返回完整路径"""
        return str(Path(self.path) / self.name)


class StorageBackend(ABC):
    """存储后端抽象基类"""
    
    @abstractmethod
    async def list_directories(self) -> List[str]:
        """获取根目录下的目录列表"""
        pass
    
    @abstractmethod
    async def list_directory(self, path: str) -> List[StorageItem]:
        """列出指定目录下的所有项目"""
        pass
    
    @abstractmethod
    async def get_directory_structure(self, dir_name: str) -> List[Dict[str, Any]]:
        """
        递归获取目录结构和文件
        
        Args:
            dir_name: 目录名称
            
        Returns:
            包含文件信息的字典列表，每个字典包含path和season
        """
        pass 