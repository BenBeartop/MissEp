# 剧集缺集检查工具

这是一个用于扫描媒体库中的剧集文件，并与TMDB数据进行比较，找出缺失的集数的工具。它还可以选择性地通过MoviePilot平台自动订阅或下载缺失的剧集。

## 🌟 功能特点

- ✨ 支持多种存储后端:
  - 🔸 Rclone：访问各种云存储
  - 🔸 Alist：通过Alist API访问多种存储
  - 🔸 WebDAV：标准WebDAV协议访问
  - 🔸 本地文件系统：直接访问本地或挂载的目录
- 📺 自动识别季集信息
- 🎬 与TMDB API交互获取正确的剧集信息
- 📝 生成缺失剧集报告
- 🚀 支持MoviePilot平台集成，可自动订阅/下载缺失剧集
- ⚡️ 缓存机制提高性能

## 📥 安装

1. 确保已安装Python 3.7+
2. 安装依赖:
   ```bash
   pip install -r requirements.txt
   ```
3. 如果使用Rclone，确保已安装rclone并配置好相应的远程存储

## ⚙️ 配置说明

主要配置在`config.yml`文件中:

### 存储配置
```yaml
storage:
  # 存储类型: rclone, alist, webdav, local
  type: rclone
  
  # Rclone配置
  rclone:
    remote: "remote:媒体库/剧集"
  
  # Alist配置
  alist:
    url: "http://localhost:5244"
    username: ""
    password: ""
    token: ""
    path: "/媒体库/剧集"
  
  # WebDAV配置
  webdav:
    url: "http://localhost:5244/dav"
    username: ""
    password: ""
    path: "/媒体库/剧集"
  
  # 本地路径配置
  local:
    path: "/path/to/media"
```

### MoviePilot配置
```yaml
moviepilot:
  url: "http://localhost:3000"
  username: "admin"
  password: "password"
  auto_subscribe: true    # 是否自动订阅缺失剧集
  auto_download: false    # 是否尝试直接下载缺失剧集
  subscribe_threshold: 0  # 订阅阈值(超过此数量才订阅整季)
```

### TMDB配置
```yaml
tmdb:
  api_key: "your_api_key"
  language: "zh-CN"
  timeout: 30
```

## 🚀 使用方法

基本用法:
```bash
python check_missing_episodes.py
```

指定存储类型:
```bash
python check_missing_episodes.py --storage local --local-path /path/to/media
python check_missing_episodes.py --storage webdav --webdav-url http://localhost:5244/dav --webdav-username user --webdav-password pass --webdav-path /media
python check_missing_episodes.py --storage alist --alist-url http://localhost:5244 --alist-username user --alist-password pass --alist-path /media
```

指定剧集:
```bash
python check_missing_episodes.py --show "哥谭 (2014)"
```

其他选项:
```bash
python check_missing_episodes.py --no-subscribe  # 禁用自动订阅
python check_missing_episodes.py --download      # 启用自动下载
python check_missing_episodes.py --threshold 3   # 设置订阅阈值为3集
python check_missing_episodes.py --force-check-all  # 强制检查所有剧集
```

合并旧的缓存文件:
```bash
python check_missing_episodes.py --merge-cache tmdb_cache.json
```
或
```bash
python merge_cache.py tmdb_cache.json
```

## 📁 模块结构

- 📂 `utils/`: 通用工具函数和配置
  - 📄 `config.py`: 全局配置
  - 📄 `helpers.py`: 辅助函数
  - 📄 `cache.py`: 缓存管理
- 📂 `storage/`: 存储后端实现
  - 📄 `base.py`: 存储后端抽象接口
  - 📄 `rclone.py`: Rclone存储实现
  - 📄 `alist.py`: Alist存储实现
  - 📄 `webdav.py`: WebDAV存储实现
  - 📄 `local.py`: 本地文件系统实现
  - 📄 `factory.py`: 存储后端工厂
- 📂 `tmdb/`: TMDB API交互
- 📂 `media_manager/`: 媒体管理器(MoviePilot)集成
- 📄 `main.py`: 主程序逻辑
- 📄 `check_missing_episodes.py`: 入口点

## 📝 输出文件

- `*_cache.json`: 缓存文件，包含TMDB映射和完整剧集记录
- `*_missing_report.txt`: 缺失剧集报告
- `*_skipped_files.log`: 无法解析的文件记录

## 💐 致谢

- [Sakura_embyboss](https://github.com/berry8838/Sakura_embyboss): MoviePilot API集成部分代码参考了该项目的实现
- [MoviePilot](https://github.com/jxxghp/MoviePilot): 优秀的自动化追剧下载工具
- [TMDB](https://www.themoviedb.org/): 提供影视信息API
- [Rclone](https://rclone.org/): 优秀的云存储管理工具
- [Alist](https://alist.nn.ci/): 优秀的文件列表程序

## 📜 License

GPL-3.0 license 