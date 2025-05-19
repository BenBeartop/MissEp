#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
配置管理模块
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional, Set
import yaml
from enum import Enum

class StorageType(Enum):
    """存储类型枚举"""
    RCLONE = "rclone"
    ALIST = "alist"
    WEBDAV = "webdav"
    LOCAL = "local"

class Config:
    """配置类"""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.storage_type = StorageType.RCLONE
            self.storage_config = {}
            self.tmdb_config = {}
            self.moviepilot_config = {}
            self.features = {}
            self.video_extensions = set()
            self.initialized = True
    
    @classmethod
    def load(cls, config_path: str = "config.yml") -> 'Config':
        """加载配置文件"""
        instance = cls()
        
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
        
        # 存储配置
        storage_config = config_data.get('storage', {})
        instance.storage_type = StorageType(storage_config.get('type', 'rclone'))
        instance.storage_config = storage_config
        
        # TMDB配置
        instance.tmdb_config = config_data.get('tmdb', {})
        
        # MoviePilot配置
        instance.moviepilot_config = config_data.get('moviepilot', {})
        
        # 功能配置
        instance.features = config_data.get('features', {})
        
        # 文件扩展名配置
        instance.video_extensions = set(config_data.get('video_extensions', []))
        
        return instance
    
    def get_storage_config(self, storage_type: Optional[StorageType] = None) -> Dict[str, Any]:
        """获取指定存储类型的配置"""
        storage_type = storage_type or self.storage_type
        return self.storage_config.get(storage_type.value, {})
    
    def get_file_paths(self) -> Dict[str, str]:
        """生成文件路径"""
        # 获取基础名称
        storage_config = self.get_storage_config()
        if self.storage_type == StorageType.RCLONE:
            base_name = storage_config.get('remote', '').split('/')[-1]
        elif self.storage_type in (StorageType.ALIST, StorageType.WEBDAV):
            base_name = storage_config.get('path', '').split('/')[-1]
        elif self.storage_type == StorageType.LOCAL:
            base_name = os.path.basename(storage_config.get('path', ''))
        else:
            base_name = "media"
        
        if not base_name:
            base_name = f"{self.storage_type.value}_media"
        
        return {
            'cache': f"{base_name}_cache.json",
            'report': f"{base_name}_missing_report.txt",
            'skipped': f"{base_name}_skipped_files.log"
        }

# 全局配置实例
CONFIG = Config.load()

# 导出常用配置
STORAGE_TYPE = CONFIG.storage_type
STORAGE_CONFIG = CONFIG.storage_config

# 文件路径
FILES = CONFIG.get_file_paths()
CACHE_FILE = FILES['cache']
REPORT_FILE = FILES['report']
SKIPPED_LOG = FILES['skipped']

# TMDB配置
TMDB_API_KEY = CONFIG.tmdb_config.get('api_key', '')
LANGUAGE = CONFIG.tmdb_config.get('language', 'zh-CN')
TIMEOUT = CONFIG.tmdb_config.get('timeout', 30)

# MoviePilot配置
MOVIEPILOT_URL = CONFIG.moviepilot_config.get('url', '')
MOVIEPILOT_USERNAME = CONFIG.moviepilot_config.get('username', '')
MOVIEPILOT_PASSWORD = CONFIG.moviepilot_config.get('password', '')
AUTO_SUBSCRIBE = CONFIG.moviepilot_config.get('auto_subscribe', True)
AUTO_DOWNLOAD = CONFIG.moviepilot_config.get('auto_download', False)
SUBSCRIBE_THRESHOLD = CONFIG.moviepilot_config.get('subscribe_threshold', 0)

# 功能配置
MAX_SHOWS = CONFIG.features.get('max_shows')

# 文件扩展名
VIDEO_EXTENSIONS = CONFIG.video_extensions

# 为了方便使用，导出常用配置变量
RCLONE_REMOTE = CONFIG.get_storage_config().get('remote', '')
ALIST_URL = CONFIG.get_storage_config(StorageType.ALIST).get('url', '')
ALIST_USERNAME = CONFIG.get_storage_config(StorageType.ALIST).get('username', '')
ALIST_PASSWORD = CONFIG.get_storage_config(StorageType.ALIST).get('password', '')
ALIST_TOKEN = CONFIG.get_storage_config(StorageType.ALIST).get('token', '')
ALIST_PATH = CONFIG.get_storage_config(StorageType.ALIST).get('path', '')
WEBDAV_URL = CONFIG.get_storage_config(StorageType.WEBDAV).get('url', '')
WEBDAV_USERNAME = CONFIG.get_storage_config(StorageType.WEBDAV).get('username', '')
WEBDAV_PASSWORD = CONFIG.get_storage_config(StorageType.WEBDAV).get('password', '')
WEBDAV_PATH = CONFIG.get_storage_config(StorageType.WEBDAV).get('path', '')
LOCAL_PATH = CONFIG.get_storage_config(StorageType.LOCAL).get('path', '')

# 导出所有配置
__all__ = [
    'CONFIG',
    'StorageType',
    'STORAGE_TYPE',
    'STORAGE_CONFIG',
    'RCLONE_REMOTE',
    'ALIST_URL',
    'ALIST_USERNAME',
    'ALIST_PASSWORD',
    'ALIST_TOKEN',
    'ALIST_PATH',
    'WEBDAV_URL',
    'WEBDAV_USERNAME',
    'WEBDAV_PASSWORD',
    'WEBDAV_PATH',
    'LOCAL_PATH',
    'TMDB_API_KEY',
    'LANGUAGE',
    'TIMEOUT',
    'MOVIEPILOT_URL',
    'MOVIEPILOT_USERNAME',
    'MOVIEPILOT_PASSWORD',
    'AUTO_SUBSCRIBE',
    'AUTO_DOWNLOAD',
    'SUBSCRIBE_THRESHOLD',
    'MAX_SHOWS',
    'VIDEO_EXTENSIONS',
    'CACHE_FILE',
    'REPORT_FILE',
    'SKIPPED_LOG'
] 