"""
?멸퉵 - ?ㅼ젙
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

# ?? ?蹂???
SCRIPT_MODEL = "gemini-2.5-flash"
SCRIPT_TEMPERATURE = 0.8

# ?? ?대?吏 紐⑤뜽 ??
IMAGE_STYLE_DEFAULT = "animation"
IMAGE_MODEL_DEFAULT = "flux-schnell"

IMAGE_MODELS = {
    "flux-schnell": {
        "provider": "replicate",
        "model_id": "black-forest-labs/flux-schnell",
        "name": "FLUX Schnell",
        "description": "鍮좊Ⅴ怨????(~$0.003/??",
        "cost": 0.003,
        "params": {"aspect_ratio": "16:9", "num_outputs": 1, "output_format": "png", "go_fast": True},
    },
    "flux-1.1-pro": {
        "provider": "replicate",
        "model_id": "black-forest-labs/flux-1.1-pro",
        "name": "FLUX 1.1 Pro",
        "description": "怨좏뭹吏?踰붿슜 (~$0.04/??",
        "cost": 0.04,
        "params": {"aspect_ratio": "16:9", "output_format": "png"},
    },
    "flux-kontext": {
        "provider": "replicate",
        "model_id": "black-forest-labs/flux-kontext-pro",
        "name": "FLUX Kontext Pro",
        "description": "罹먮┃???쇨???(~$0.05/??",
        "cost": 0.05,
        "params": {"aspect_ratio": "16:9", "output_format": "png"},
    },
    "seedream": {
        "provider": "replicate",
        "model_id": "bytedance/seedream-4.5",
        "name": "Seedream 4.5",
        "description": "由ъ뼹由ъ뒪??(~$0.03/??",
        "cost": 0.03,
        "params": {"aspect_ratio": "16:9", "image_format": "png"},
    },
    "ideogram": {
        "provider": "replicate",
        "model_id": "ideogram-ai/ideogram-v3-turbo",
        "name": "Ideogram V3 Turbo",
        "description": "?띿뒪???뚮뜑留?理쒓퀬 (~$0.02/??",
        "cost": 0.02,
        "params": {"aspect_ratio": "16:9"},
    },
    "recraft-v3": {
        "provider": "replicate",
        "model_id": "recraft-ai/recraft-v3",
        "name": "Recraft V3",
        "description": "?쇰윭?ㅽ듃/踰≫꽣 (~$0.04/??",
        "cost": 0.04,
        "params": {"size": "1365x1024"},
    },
    "imagen4-fast": {
        "provider": "replicate",
        "model_id": "google/imagen-4-fast",
        "name": "Imagen 4 Fast",
        "description": "Google Imagen (~$0.02/??",
        "cost": 0.02,
        "params": {"aspect_ratio": "16:9", "output_format": "png"},
    },
    "nano-banana": {
        "provider": "google",
        "model_id": "gemini-3-pro-image-preview",
        "name": "Nano Banana (Gemini 3 Pro Image)",
        "description": "理쒓퀬 ?덉쭏 (~$0.134/??",
        "cost": 0.134,
        "params": {},
    },
    "gemini-flash-image": {
        "provider": "google",
        "model_id": "gemini-2.0-flash",
        "name": "Gemini 2.0 Flash Image",
        "description": "媛?깅퉬 (~$0.039/??",
        "cost": 0.039,
        "params": {},
    },
}

# ?? TTS ??
TTS_VOICE_DEFAULT = "ko-KR-SunHiNeural"
TTS_VOICES = {
    "ko-KR-SunHiNeural": "?좏씗 - 諛앹? ?ъ꽦",
    "ko-KR-InJoonNeural": "?몄? - ?⑥꽦",
    "ko-KR-HyunsuNeural": "?꾩닔 - ?⑥꽦",
}

# ?? FFmpeg ??
VIDEO_FPS = 30
VIDEO_RESOLUTION = "1280x720"
VIDEO_CODEC = "libx264"
VIDEO_CRF = 18
SUBTITLE_FONT = "NanumGothicBold"
SUBTITLE_FONTSIZE = 48
SUBTITLE_BORDERW = 3

"""?꾨줈?앺듃 ?ㅼ젙"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ?? 寃쎈줈 ??
BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "output"
PROMPTS_DIR = APP_DIR / "prompts"

# ?? API ????
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# ?? ?쒕쾭 ??
HOST = "0.0.0.0"
PORT = int(os.getenv("PORT", 9000))

