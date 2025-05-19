# 드라마 에피소드 결핍 검사 도구

이 도구는 미디어 라이브러리에서 드라마 파일을 스캔하고 TMDB 데이터와 비교하여 누락된 에피소드를 찾는 데 사용됩니다. 또한 MoviePilot 플랫폼을 통해 누락된 에피소드를 자동으로 구독하거나 다운로드할 수 있습니다.

## 🌟 기능 특징

- ✨ 다양한 저장소 백엔드 지원:
  - 🔸 Rclone: 다양한 클라우드 스토리지에 액세스
  - 🔸 Alist: Alist API를 통해 다양한 스토리지에 액세스
  - 🔸 WebDAV: 표준 WebDAV 프로토콜 액세스
  - 🔸 로컬 파일 시스템: 로컬 또는 마운트된 디렉토리에 직접 액세스
- 📺 시즌 및 에피소드 정보 자동 인식
- 🎬 TMDB API와 상호 작용하여 올바른 드라마 정보 가져오기
- 📝 누락된 에피소드 보고서 생성
- 🚀 MoviePilot 플랫폼 통합 지원, 누락된 에피소드 자동 구독/다운로드 가능
- ⚡️ 캐시 메커니즘으로 성능 향상

## 📥 설치

1. Python 3.7+ 설치 확인
2. 종속성 설치:
   ```bash
   pip install -r requirements.txt
   ```
3. Rclone을 사용하는 경우, rclone을 설치하고 적절한 원격 스토리지를 구성했는지 확인

## ⚙️ 구성 설명

주요 구성은 `config.yml` 파일에 있습니다:

### 저장소 구성
```yaml
storage:
  # 저장소 유형: rclone, alist, webdav, local
  type: rclone
  
  # Rclone 구성
  rclone:
    remote: "remote:미디어 라이브러리/드라마"
  
  # Alist 구성
  alist:
    url: "http://localhost:5244"
    username: ""
    password: ""
    token: ""
    path: "/미디어 라이브러리/드라마"
  
  # WebDAV 구성
  webdav:
    url: "http://localhost:5244/dav"
    username: ""
    password: ""
    path: "/미디어 라이브러리/드라마"
  
  # 로컬 경로 구성
  local:
    path: "/path/to/media"
```

### MoviePilot 구성
```yaml
moviepilot:
  url: "http://localhost:3000"
  username: "admin"
  password: "password"
  auto_subscribe: true    # 누락된 에피소드 자동 구독 여부
  auto_download: false    # 누락된 에피소드 직접 다운로드 시도 여부
  subscribe_threshold: 0  # 구독 임계값(이 수량을 초과해야 시즌 전체 구독)
```

### TMDB 구성
```yaml
tmdb:
  api_key: "your_api_key"
  language: "ko-KR"
  timeout: 30
```

## 🚀 사용 방법

기본 사용법:
```bash
python main.py
```

저장소 유형 지정:
```bash
python main.py --storage local --local-path /path/to/media
python main.py --storage webdav --webdav-url http://localhost:5244/dav --webdav-username user --webdav-password pass --webdav-path /media
python main.py --storage alist --alist-url http://localhost:5244 --alist-username user --alist-password pass --alist-path /media
```

드라마 지정:
```bash
python main.py --show "고담 (2014)"
```

기타 옵션:
```bash
python main.py --no-subscribe  # 자동 구독 비활성화
python main.py --download      # 자동 다운로드 활성화
python main.py --threshold 3   # 구독 임계값을 3 에피소드로 설정
python main.py --force-check-all  # 모든 드라마 강제 검사
```

이전 캐시 파일 병합:
```bash
python main.py --merge-cache tmdb_cache.json
```
또는
```bash
python merge_cache.py tmdb_cache.json
```

## 📁 모듈 구조

- 📂 `utils/`: 공용 도구 함수 및 구성
  - 📄 `config.py`: 전역 구성
  - 📄 `helpers.py`: 보조 함수
  - 📄 `cache.py`: 캐시 관리
- 📂 `storage/`: 저장소 백엔드 구현
  - 📄 `base.py`: 저장소 백엔드 추상 인터페이스
  - 📄 `rclone.py`: Rclone 저장소 구현
  - 📄 `alist.py`: Alist 저장소 구현
  - 📄 `webdav.py`: WebDAV 저장소 구현
  - 📄 `local.py`: 로컬 파일 시스템 구현
  - 📄 `factory.py`: 저장소 백엔드 팩토리
- 📂 `tmdb/`: TMDB API 상호 작용
- 📂 `media_manager/`: 미디어 관리자(MoviePilot) 통합
- 📄 `main.py`: 주요 프로그램 로직
- 📄 `main.py`: 진입점

## 📝 출력 파일

- `*_cache.json`: 캐시 파일, TMDB 매핑 및 완전한 드라마 기록 포함
- `*_missing_report.txt`: 누락된 에피소드 보고서
- `*_skipped_files.log`: 분석할 수 없는 파일 기록

## 💐 감사의 글

- [Sakura_embyboss](https://github.com/berry8838/Sakura_embyboss): MoviePilot API 통합 부분 코드 참조
- [MoviePilot](https://github.com/jxxghp/MoviePilot): 훌륭한 자동화 드라마 다운로드 도구
- [TMDB](https://www.themoviedb.org/): 영화 정보 API 제공
- [Rclone](https://rclone.org/): 훌륭한 클라우드 스토리지 관리 도구
- [Alist](https://alist.nn.ci/): 훌륭한 파일 목록 프로그램

## �� 라이선스

GPL-3.0 라이선스 