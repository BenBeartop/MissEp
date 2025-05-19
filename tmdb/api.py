#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TMDB API交互模块
"""

import json
import aiohttp
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass

from utils.config import TMDB_API_KEY, LANGUAGE, TIMEOUT
from utils.helpers import MediaProcessError, extract_year, CacheData

@dataclass
class TMDBShow:
    """TMDB剧集信息"""
    id: int
    name: str
    first_air_date: Optional[str] = None
    
    @property
    def year(self) -> Optional[int]:
        """获取首播年份"""
        if self.first_air_date and len(self.first_air_date) >= 4:
            try:
                return int(self.first_air_date[:4])
            except ValueError:
                return None
        return None

async def search_tv_show(title: str, cache: CacheData) -> Tuple[Optional[int], Optional[str]]:
    """
    搜索剧集,支持缓存和年份匹配
    
    Args:
        title: 剧集标题
        cache: 缓存数据对象
        
    Returns:
        (tmdb_id, tmdb_name)元组或(None, None)
    """
    # 检查缓存
    if title in cache.tmdb_map:
        tmdb_id = cache.tmdb_map[title]
        # 查询名称,如果没有名称信息则使用标题
        tmdb_name = title
        for name, id in cache.tmdb_map.items():
            if id == tmdb_id and name != title:
                tmdb_name = name.split(" (")[0]  # 移除年份
                break
        return tmdb_id, tmdb_name

    # 提取剧集名称中的年份信息
    year = extract_year(title)
    
    # 清理标题中的年份和其他信息
    import re
    clean_title = re.sub(r"\s*\(\d{4}\).*$", "", title)
    
    # 构建搜索URL
    url = f"https://api.themoviedb.org/3/search/tv"
    params = {
        "api_key": TMDB_API_KEY,
        "language": LANGUAGE,
        "query": clean_title
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=TIMEOUT) as response:
                if response.status != 200:
                    raise MediaProcessError(f"TMDB API请求失败: HTTP {response.status}", "TMDB")
                
                data = await response.json()
                if not data.get("results"):
                    return None, None
                
                results = [TMDBShow(
                    id=r["id"],
                    name=r["name"],
                    first_air_date=r.get("first_air_date", "")
                ) for r in data["results"]]
                
                # 如果有年份信息,优先选择与年份匹配的剧集
                if year:
                    # 精确匹配年份
                    for show in results:
                        if show.year == year:
                            print(f"  找到精确匹配年份 {year} 的剧集: {show.name} (ID: {show.id})")
                            cache.tmdb_map[title] = show.id
                            return show.id, show.name
                    
                    # 接近匹配年份 (±1年)
                    for show in results:
                        if show.year and abs(show.year - year) <= 1:
                            print(f"  找到接近匹配年份 {year} 的剧集: {show.name} ({show.year}, ID: {show.id})")
                            cache.tmdb_map[title] = show.id
                            return show.id, show.name
                    
                    # 如果没有直接匹配,打印警告并尝试选择最接近的
                    print(f"  警告：没有找到年份为 {year} 的精确匹配")
                    best_match = None
                    closest_diff = 9999
                    
                    for show in results:
                        if show.year:
                            diff = abs(show.year - year)
                            if diff < closest_diff:
                                closest_diff = diff
                                best_match = show
                    
                    if best_match:
                        print(f"  自动选择最接近的版本: {best_match.name} ({best_match.year}, ID: {best_match.id})")
                        cache.tmdb_map[title] = best_match.id
                        return best_match.id, best_match.name
                
                # 如果没有年份或无法找到匹配年份的剧集,使用第一个结果
                show = results[0]
                year_str = str(show.year) if show.year else "未知"
                print(f"  使用搜索结果第一项: {show.name} ({year_str}, ID: {show.id})")
                
                cache.tmdb_map[title] = show.id
                return show.id, show.name
                
    except aiohttp.ClientError as e:
        raise MediaProcessError(f"TMDB API请求失败: {e}", "TMDB")
    except json.JSONDecodeError as e:
        raise MediaProcessError(f"TMDB API返回数据解析失败: {e}", "TMDB")
    except Exception as e:
        if isinstance(e, MediaProcessError):
            raise
        raise MediaProcessError(f"TMDB搜索错误: {e}", "TMDB")

async def get_tmdb_structure(tv_id: int) -> Dict[int, List[int]]:
    """
    获取剧集结构(季 + 集)
    
    Args:
        tv_id: TMDB剧集ID
        
    Returns:
        按季节组织的剧集列表字典
    """
    from collections import defaultdict
    structure = defaultdict(list)
    
    # 获取剧集基本信息
    tv_url = f"https://api.themoviedb.org/3/tv/{tv_id}"
    params = {
        "api_key": TMDB_API_KEY,
        "language": LANGUAGE
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(tv_url, params=params, timeout=TIMEOUT) as response:
                if response.status != 200:
                    raise MediaProcessError(f"获取剧集信息失败: HTTP {response.status}", "TMDB")
                
                tv_data = await response.json()
                
                # 获取每季信息
                for season in tv_data.get("seasons", []):
                    snum = season["season_number"]
                    if snum == 0:  # 跳过特别篇
                        continue
                    
                    # 获取季详细信息
                    season_url = f"https://api.themoviedb.org/3/tv/{tv_id}/season/{snum}"
                    async with session.get(season_url, params=params, timeout=TIMEOUT) as season_response:
                        if season_response.status != 200:
                            print(f"  警告: 无法获取第{snum}季信息")
                            continue
                        
                        season_data = await season_response.json()
                        episodes = [ep["episode_number"] for ep in season_data.get("episodes", [])]
                        structure[snum] = episodes
                
                return structure
                
    except aiohttp.ClientError as e:
        raise MediaProcessError(f"TMDB API请求失败: {e}", "TMDB")
    except json.JSONDecodeError as e:
        raise MediaProcessError(f"TMDB API返回数据解析失败: {e}", "TMDB")
    except Exception as e:
        if isinstance(e, MediaProcessError):
            raise
        raise MediaProcessError(f"获取剧集结构失败: {e}", "TMDB")