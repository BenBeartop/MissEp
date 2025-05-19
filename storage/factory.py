#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
存储后端工厂模块
"""

from typing import Optional

from utils.config import StorageType, STORAGE_TYPE
from storage.base import StorageBackend


def get_storage_backend() -> StorageBackend:
    """
    获取当前配置的存储后端
    
    Returns:
        存储后端实例
    """
    # 根据配置选择存储后端
    if STORAGE_TYPE == StorageType.RCLONE:
        from storage.rclone import RcloneStorage
        from utils.config import RCLONE_REMOTE
        return RcloneStorage(RCLONE_REMOTE)
    
    elif STORAGE_TYPE == StorageType.ALIST:
        from storage.alist import AlistStorage
        from utils.config import ALIST_URL, ALIST_USERNAME, ALIST_PASSWORD, ALIST_TOKEN, ALIST_PATH
        return AlistStorage(ALIST_URL, ALIST_USERNAME, ALIST_PASSWORD, ALIST_TOKEN, ALIST_PATH)
    
    elif STORAGE_TYPE == StorageType.WEBDAV:
        from storage.webdav import WebDAVStorage
        from utils.config import WEBDAV_URL, WEBDAV_USERNAME, WEBDAV_PASSWORD, WEBDAV_PATH
        return WebDAVStorage(WEBDAV_URL, WEBDAV_USERNAME, WEBDAV_PASSWORD, WEBDAV_PATH)
    
    elif STORAGE_TYPE == StorageType.LOCAL:
        from storage.local import LocalStorage
        from utils.config import LOCAL_PATH
        return LocalStorage(LOCAL_PATH)
    
    else:
        raise ValueError(f"不支持的存储类型: {STORAGE_TYPE}") 