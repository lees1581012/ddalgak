# 딸깍 (DdalGak) - 유튜브 영상 자동 제작 시스템 가이드

## 개요

**딸깍**은 뉴스 기사를 입력하면 AI가 자동으로 유튜브 영상을 만들어주는 파이썬 기반 웹 애플리케이션입니다.

```
뉴스 기사 → 대본 생성 → 이미지 생성 → 음성 생성 → 영상 생성 → 합성 → 메타데이터
```

---

## 프로젝트 구조

```
ddalgak/
├── run.py                      # 서버 실행 엔트리포인트
├── requirements.txt            # Python 의존성
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI 앱 생성
│   ├── config.py               # 환경설정 (API 키, 모델 설정)
│   ├── routes.py               # API 라우트 정의
│   ├── pipeline/               # 영상 제작 파이프라인
│   │   ├── step1_script.py     # 대본 생성 (Gemini)
│   │   ├── step2_images.py     # 이미지 생성 (Replicate/ComfyUI/Google)
│   │   ├── step3_tts.py        # 음성 생성 (Edge TTS/Kokoro/ElevenLabs)
│   │   ├── step4_video.py      # I2V 영상 생성 (LTX2/Replicate/Google)
│   │   ├── step5_compose.py    # 최종 영상 합성 (FFmpeg)
│   │   ├── step6_metadata.py   # 메타데이터 & 썸네일
│   │   └── utils.py            # 유틸리티 함수
│   ├── prompts/                # AI 프롬프트 템플릿
│   ├── templates/              # HTML 템플릿
│   └── static/                 # 정적 파일 (JS, CSS)
└── output/                     # 생성된 프로젝트 저장소
```

---

## 파이프라인 단계별 메커니즘

### STEP 1: 대본 생성 (`step1_script.py`)

**기능**: 뉴스 기사를 유튜브 대본으로 변환

**API**: Google Gemini 2.5 Flash

**과정**:
1. 사용자가 뉴스 기사 입력
2. `prompts/script_system.txt` 시스템 프롬프트 로드
3. Gemini API로 대본 생성 요청
4. 응답에서 JSON 추출 (제목 + 장면 리스트)

**출력 형식**:
```json
{
  "title": "영상 제목",
  "scenes": [
    {
      "id": 1,
      "narration": "나레이션 텍스트",
      "image_prompt": "이미지 생성용 프롬프트"
    }
  ]
}
```

---

### STEP 2: 이미지 생성 (`step2_images.py`)

**기능**: 각 장면의 일러스트 이미지 생성

**지원 모델**:
| 모델 | 제공자 | 비용 | 비고 |
|------|--------|------|------|
| z-image | ComfyUI (로컬) | 무료 | 빠름, 추천 |
| flux-schnell | Replicate | $0.003/장 | 빠름 |
| flux-1.1-pro | Replicate | $0.04/장 | 고품질 |
| gemini-flash-image | Google | $0.039/장 | |

**이미지 스타일** (`prompts/image_style.json`):
- `animation`: 애니메이션 스타일 (기본)
- `realistic`: 사실적인 스타일
- `3d-render`: 3D 렌더링
- `watercolor`: 수채화 스타일

**과정**:
1. 각 장면의 `image_prompt`를 스타일 접두사/접미사로 감싸기
2. 선택한 모델로 이미지 생성
3. `images/scene_001.png` 형식으로 저장

---

### STEP 3: 음성 생성 (`step3_tts.py`)

**기능**: 나레이션 텍스트를 음성으로 변환

**지원 엔진**:

| 엔진 | 지원 언어 | 비용 | 특징 |
|------|-----------|------|------|
| Edge TTS | 한국어, 영어, 일본어 | 무료 | Microsoft Neural |
| Kokoro | 영어(미국/영국), 일본어 | 무료 | 로컬 TTS |
| ElevenLabs | 한국어 (윤아) | 유료 | 자연스러운 톤 |

**한국어 음성 (Edge TTS)**:
- `ko_sunhi`: 선희 - 여성 (밝은 톤)
- `ko_injoon`: 인준 - 남성 (차분)
- `ko_hyunsu`: 현수 - 남성 (뉴스 앵커)
- `ko_yoona`: 윤아 - 여성 (ElevenLabs)

**과정**:
1. 각 장면의 `narration` 텍스트를 음성으로 변환
2. `audio/scene_001.mp3` 형식으로 저장
3. 오디오 길이 계산

---

### STEP 4: I2V 영상 생성 (`step4_video.py`)

**기능**: 정적 이미지를 움직이는 영상으로 변환 (Image-to-Video)

**지원 모드**:

| 모드 | 모델 | 특징 |
|------|------|------|
| comfyui | LTX-2 | 로컬 ComfyUI, 무료 |
| replicate | minimax/video-01-live | 유료 |
| google | veo-2.0-generate-001 | Google Veo |

**ITV 프롬프트 생성**:
1. Gemini 2.5 Flash로 각 이미지에 맞는 움직임 프롬프트 자동 생성
2. 카메라 무브먼트 + 캐릭터 모션만 설명 (새 요소 금지)
3. suffix 추가: "Do not introduce any new elements..."

**과정**:
1. 이미지를 ComfyUI 서버로 업로드
2. LTX-2 워크플로우 실행
3. 생성된 영상 다운로드
4. `videos/scene_001.mp4` 형식으로 저장

---

### STEP 5: 영상 합성 (`step5_compose.py`)

**기능**: 이미지/비디오 + 오디오 + 자막 → 최종 MP4

**과정**:
1. 각 씬별 클립 생성:
   - 비디오 있는 씬: 비디오 사용 (길이 조정)
   - 비디오 없는 씬: 이미지 슬라이드쇼
2. 모든 클립 연결 (concat)
3. 전체 오디오 병합
4. SRT 자막 생성
5. 최종 합성: 비디오 + 오디오 + 자막 burn-in

**FFmpeg 필터**:
- 비디오 스케일: `1280x720` (letterbox)
- 자막 스타일: NanumGothic, 흰색, 검은 테두리
- 코덱: H.264 (CRF 18), AAC 192kbps

---

### STEP 6: 메타데이터 & 썸네일 (`step6_metadata.py`)

**기능**: 유튜브 업로드용 메타데이터 생성

**출력물**:
- **메타데이터**: 제목, 설명, 태그, 카테고리
- **썸네일**: Flux Schnell로 자동 생성

---

## API 엔드포인트

### 페이지
- `GET /` - 메인 페이지

### 프로젝트 관리
- `POST /api/project/create` - 새 프로젝트 생성
- `GET /api/project/{id}` - 프로젝트 상태 조회
- `GET /api/projects` - 프로젝트 목록

### STEP 1: 대본
- `POST /api/step1/generate` - 대본 생성
- `POST /api/step1/save` - 대본 저장

### STEP 2: 이미지
- `GET /api/step2/generate` - 이미지 생성 (SSE)
- `POST /api/step2/regenerate` - 단일 이미지 재생성

### STEP 3: 음성
- `GET /api/step3/generate` - 음성 생성 (SSE)

### STEP 4: 영상
- `GET /api/step4/generate` - 영상 생성 (SSE)
- `POST /api/step4/regenerate` - 단일 영상 재생성
- `POST /api/step4/upload` - 수동 영상 업로드

### STEP 5: 합성
- `POST /api/step5/compose` - 최종 영상 합성

### STEP 6: 메타데이터
- `POST /api/step6/metadata` - 메타데이터 생성
- `POST /api/step6/thumbnail` - 썸네일 생성

---

## 설정 (`.env`)

```bash
# 필수
GEMINI_API_KEY=your_gemini_key
REPLICATE_API_TOKEN=your_replicate_token

# 선택 (ElevenLabs)
ELEVENLABS_API_KEY=your_elevenlabs_key

# 선택 (ComfyUI 로컬)
# ComfyUI는 http://localhost:8000에서 실행되어야 함
```

---

## 실행 방법

```bash
# 1. 가상환경 생성
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# 2. 의존성 설치
pip install -r requirements.txt

# 3. .env 파일 생성
cp .env.example .env
# .env에 API 키 입력

# 4. ComfyUI 실행 (선택사항, 로컬 z-image/LTX2 사용 시)
# 별도 ComfyUI 설치 필요

# 5. 서버 실행
python run.py
# 또는 uvicorn app.main:app --reload --host 0.0.0.0 --port 9000

# 6. 브라우저 접속
http://localhost:9000
```

---

## 프로젝트 폴더 구조 (output/)

```
output/
└── 20260219_153929/          # 프로젝트 ID (timestamp)
    ├── input_article.txt     # 입력 뉴스 기사
    ├── script.json           # 생성된 대본
    ├── image_results.json    # 이미지 생성 결과
    ├── audio_results.json    # 오디오 생성 결과
    ├── video_results.json    # 비디오 생성 결과
    ├── metadata.json         # 메타데이터
    ├── images/               # 장면별 이미지
    │   ├── scene_001.png
    │   └── scene_002.png
    ├── audio/                # 장면별 오디오
    │   ├── scene_001.mp3
    │   └── scene_002.mp3
    ├── videos/               # 장면별 영상
    │   ├── scene_001.mp4
    │   └── scene_002.mp4
    ├── final/                # 최종 결과물
    │   ├── output.mp4        # 최종 영상
    │   ├── subtitles.srt     # 자막 파일
    │   └── thumbnail.png     # 썸네일
    └── itv_prompts.json      # I2V 프롬프트
```

---

## 기술 스택

| 분야 | 기술 |
|------|------|
| 웹 프레임워크 | FastAPI |
| 서버 | Uvicorn |
| 템플릿 | Jinja2 |
| 실시간 통신 | SSE (Server-Sent Events) |
| AI/ML | Gemini, Replicate, ComfyUI |
| 오디오 | Edge TTS, Kokoro, ElevenLabs |
| 비디오 처리 | FFmpeg |
| 언어 | Python 3.10+ |

---

## 주요 의존성

```
fastapi>=0.115.0          # 웹 프레임워크
uvicorn[standard]>=0.30.0 # ASGI 서버
sse-starlette>=2.0.0      # SSE 지원
google-genai>=1.0.0       # Gemini API
replicate>=1.0.0          # Replicate API
edge-tts>=6.1.0           # Microsoft Edge TTS
mutagen>=1.47.0           # 오디오 메타데이터
httpx>=0.27.0             # HTTP 클라이언트
aiofiles>=23.0.0          # 비동기 파일 I/O
jinja2>=3.1.0             # 템플릿 엔진
```
