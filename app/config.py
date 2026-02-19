"""
딸깍 - 설정
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")

BASE_DIR = Path(__file__).parent.parent
APP_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
PROMPTS_DIR = APP_DIR / "prompts"

# ── 대본 ──
SCRIPT_MODEL = "gemini-2.5-flash"
SCRIPT_TEMPERATURE = 0.8

# ── 이미지 모델 ──
IMAGE_STYLE_DEFAULT = "animation"
IMAGE_MODEL_DEFAULT = "flux-schnell"

IMAGE_MODELS = {
    "flux-schnell": {
        "provider": "replicate",
        "model_id": "black-forest-labs/flux-schnell",
        "name": "FLUX Schnell",
        "description": "빠르고 저렴 (~$0.003/장)",
        "cost": 0.003,
        "params": {"aspect_ratio": "16:9", "num_outputs": 1, "output_format": "png", "go_fast": True},
    },
    "flux-1.1-pro": {
        "provider": "replicate",
        "model_id": "black-forest-labs/flux-1.1-pro",
        "name": "FLUX 1.1 Pro",
        "description": "고품질 범용 (~$0.04/장)",
        "cost": 0.04,
        "params": {"aspect_ratio": "16:9", "output_format": "png"},
    },
    "flux-kontext": {
        "provider": "replicate",
        "model_id": "black-forest-labs/flux-kontext-pro",
        "name": "FLUX Kontext Pro",
        "description": "캐릭터 일관성 (~$0.05/장)",
        "cost": 0.05,
        "params": {"aspect_ratio": "16:9", "output_format": "png"},
    },
    "seedream": {
        "provider": "replicate",
        "model_id": "bytedance/seedream-4.5",
        "name": "Seedream 4.5",
        "description": "리얼리스틱 (~$0.03/장)",
        "cost": 0.03,
        "params": {"aspect_ratio": "16:9", "image_format": "png"},
    },
    "ideogram": {
        "provider": "replicate",
        "model_id": "ideogram-ai/ideogram-v3-turbo",
        "name": "Ideogram V3 Turbo",
        "description": "텍스트 렌더링 최고 (~$0.02/장)",
        "cost": 0.02,
        "params": {"aspect_ratio": "16:9"},
    },
    "recraft-v3": {
        "provider": "replicate",
        "model_id": "recraft-ai/recraft-v3",
        "name": "Recraft V3",
        "description": "일러스트/벡터 (~$0.04/장)",
        "cost": 0.04,
        "params": {"size": "1365x1024"},
    },
    "imagen4-fast": {
        "provider": "replicate",
        "model_id": "google/imagen-4-fast",
        "name": "Imagen 4 Fast",
        "description": "Google Imagen (~$0.02/장)",
        "cost": 0.02,
        "params": {"aspect_ratio": "16:9", "output_format": "png"},
    },
    "nano-banana": {
        "provider": "google",
        "model_id": "gemini-3-pro-image-preview",
        "name": "Nano Banana (Gemini 3 Pro Image)",
        "description": "최고 품질 (~$0.134/장)",
        "cost": 0.134,
        "params": {},
    },
    "gemini-flash-image": {
        "provider": "google",
        "model_id": "gemini-2.0-flash",
        "name": "Gemini 2.0 Flash Image",
        "description": "가성비 (~$0.039/장)",
        "cost": 0.039,
        "params": {},
    },
}

# ── TTS ──
TTS_VOICE_DEFAULT = "ko-KR-SunHiNeural"
TTS_VOICES = {
    "ko-KR-SunHiNeural": "선희 - 밝은 여성",
    "ko-KR-InJoonNeural": "인준 - 남성",
    "ko-KR-HyunsuNeural": "현수 - 남성",
}

# ── FFmpeg ──
VIDEO_FPS = 30
VIDEO_RESOLUTION = "1280x720"
VIDEO_CODEC = "libx264"
VIDEO_CRF = 18
SUBTITLE_FONT = "NanumGothicBold"
SUBTITLE_FONTSIZE = 48
SUBTITLE_BORDERW = 3