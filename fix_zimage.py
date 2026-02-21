"""ComfyUI z-image (ZIT) 이미지 생성 추가"""
from pathlib import Path

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1) step2_images.py에 ComfyUI 핸들러 추가
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

NEW_STEP2 = '''"""STEP 2: 이미지 생성 (Replicate / Google / ComfyUI 선택)"""
import json
import time
import random
import logging
import urllib.request
import httpx
import replicate
from pathlib import Path
from google import genai
from app import config

logger = logging.getLogger(__name__)

COMFYUI_URL = "http://localhost:8000"


def get_styles() -> dict:
    with open(config.PROMPTS_DIR / "image_style.json", "r", encoding="utf-8") as f:
        return json.load(f)


def build_prompt(image_prompt: str, style_key: str) -> str:
    styles = get_styles()
    style = styles.get(style_key, styles["animation"])
    return f"{style[\'prefix\']} {image_prompt}{style[\'suffix\']}"


def _gen_replicate(prompt: str, model_cfg: dict, out_path: Path) -> Path:
    params = {**model_cfg["params"], "prompt": prompt}
    output = replicate.run(model_cfg["model_id"], input=params)
    url = str(output[0]) if isinstance(output, list) else str(output)
    resp = httpx.get(url, timeout=120, follow_redirects=True)
    resp.raise_for_status()
    out_path.write_bytes(resp.content)
    return out_path


def _gen_google(prompt: str, model_cfg: dict, out_path: Path) -> Path:
    client = genai.Client(api_key=config.GEMINI_API_KEY)
    response = client.models.generate_content(
        model=model_cfg["model_id"],
        contents=prompt,
        config=genai.types.GenerateContentConfig(response_modalities=["image", "text"]),
    )
    for part in response.candidates[0].content.parts:
        if part.inline_data and part.inline_data.mime_type.startswith("image/"):
            out_path.write_bytes(part.inline_data.data)
            return out_path
    raise RuntimeError("Google API 응답에 이미지 없음")


def _comfy_post(endpoint: str, data: dict) -> dict:
    payload = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        f"{COMFYUI_URL}{endpoint}",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def _comfy_get(endpoint: str) -> dict:
    with urllib.request.urlopen(f"{COMFYUI_URL}{endpoint}", timeout=30) as resp:
        return json.loads(resp.read())


def _build_zimage_workflow(prompt: str, seed: int = None, width: int = 1024, height: int = 576) -> dict:
    """z-image turbo 워크플로우 빌드"""
    if seed is None:
        seed = random.randint(0, 2**53)
    return {"prompt": {
        "9": {
            "inputs": {
                "filename_prefix": "ddalgak_img",
                "images": ["43", 0]
            },
            "class_type": "SaveImage"
        },
        "39": {
            "inputs": {
                "clip_name": "qwen_3_4b.safetensors",
                "type": "lumina2",
                "device": "default"
            },
            "class_type": "CLIPLoader"
        },
        "40": {
            "inputs": {"vae_name": "ae.safetensors"},
            "class_type": "VAELoader"
        },
        "41": {
            "inputs": {
                "width": width,
                "height": height,
                "batch_size": 1
            },
            "class_type": "EmptySD3LatentImage"
        },
        "42": {
            "inputs": {"conditioning": ["45", 0]},
            "class_type": "ConditioningZeroOut"
        },
        "43": {
            "inputs": {
                "samples": ["44", 0],
                "vae": ["40", 0]
            },
            "class_type": "VAEDecode"
        },
        "44": {
            "inputs": {
                "seed": seed,
                "steps": 9,
                "cfg": 1,
                "sampler_name": "res_multistep",
                "scheduler": "simple",
                "denoise": 1,
                "model": ["47", 0],
                "positive": ["45", 0],
                "negative": ["42", 0],
                "latent_image": ["41", 0]
            },
            "class_type": "KSampler"
        },
        "45": {
            "inputs": {
                "text": prompt,
                "clip": ["39", 0]
            },
            "class_type": "CLIPTextEncode"
        },
        "46": {
            "inputs": {
                "unet_name": "z_image_turbo_bf16.safetensors",
                "weight_dtype": "default"
            },
            "class_type": "UNETLoader"
        },
        "47": {
            "inputs": {
                "shift": 3,
                "model": ["48", 0]
            },
            "class_type": "ModelSamplingAuraFlow"
        },
        "48": {
            "inputs": {
                "lora_name": "pixel_art_style_z_image_turbo.safetensors",
                "strength_model": 1,
                "model": ["46", 0]
            },
            "class_type": "LoraLoaderModelOnly"
        },
    }}


def _gen_comfyui(prompt: str, model_cfg: dict, out_path: Path) -> Path:
    """ComfyUI z-image로 이미지 생성"""
    # 16:9 비율 (1024x576) 또는 설정에서 가져오기
    width = model_cfg.get("params", {}).get("width", 1024)
    height = model_cfg.get("params", {}).get("height", 576)

    workflow = _build_zimage_workflow(prompt, width=width, height=height)

    # 프롬프트 큐잉
    result = _comfy_post("/prompt", workflow)
    prompt_id = result["prompt_id"]
    logger.info(f"ComfyUI z-image 큐잉: {prompt_id}")

    # 완료 대기
    import time as _time
    start = _time.time()
    timeout = 120
    while _time.time() - start < timeout:
        history = _comfy_get(f"/history/{prompt_id}")
        if prompt_id in history:
            outputs = history[prompt_id].get("outputs", {})
            # SaveImage 노드(9)에서 이미지 찾기
            for node_id, node_out in outputs.items():
                if "images" in node_out:
                    for item in node_out["images"]:
                        filename = item.get("filename", "")
                        subfolder = item.get("subfolder", "")
                        filetype = item.get("type", "output")
                        if not filename.endswith((".png", ".jpg", ".webp")):
                            continue
                        # 다운로드
                        params = f"filename={filename}&type={filetype}"
                        if subfolder:
                            params += f"&subfolder={subfolder}"
                        url = f"{COMFYUI_URL}/view?{params}"
                        resp = urllib.request.urlopen(url)
                        img_data = resp.read()
                        out_path.parent.mkdir(parents=True, exist_ok=True)
                        out_path.write_bytes(img_data)
                        logger.info(f"z-image 완료: {out_path.name} ({len(img_data)} bytes)")
                        return out_path
            # 에러 체크
            status = history[prompt_id].get("status", {})
            if status.get("status_str") == "error":
                msgs = status.get("messages", [])
                raise RuntimeError(f"ComfyUI z-image 에러: {msgs}")
        _time.sleep(1)

    raise TimeoutError(f"ComfyUI z-image 타임아웃 ({timeout}s)")


_HANDLERS = {"replicate": _gen_replicate, "google": _gen_google, "comfyui": _gen_comfyui}


def generate_single(scene: dict, style_key: str, model_key: str, output_dir: Path) -> dict:
    """단일 장면 이미지 생성"""
    output_dir.mkdir(parents=True, exist_ok=True)

    model_cfg = config.IMAGE_MODELS.get(model_key, config.IMAGE_MODELS[config.IMAGE_MODEL_DEFAULT])
    prompt = build_prompt(scene["image_prompt"], style_key)
    out_path = output_dir / f"scene_{scene[\'id\']:03d}.png"

    try:
        handler = _HANDLERS[model_cfg["provider"]]
        handler(prompt, model_cfg, out_path)
        time.sleep(0.3)
        return {"scene_id": scene["id"], "image_path": str(out_path), "prompt": prompt, "status": "success"}
    except Exception as e:
        return {"scene_id": scene["id"], "image_path": None, "prompt": prompt, "status": f"failed: {e}"}
'''

# 이스케이프 처리
content = NEW_STEP2.replace("\\'", "'")
Path("app/pipeline/step2_images.py").write_text(content, encoding="utf-8", newline="\n")
print("1) step2_images.py 업데이트 완료 (ComfyUI z-image 추가)")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2) config.py에 z-image 모델 추가
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
cfg = Path("app/config.py").read_text(encoding="utf-8")

ZIT_ENTRY = '''    "z-image": {
        "provider": "comfyui",
        "model_id": "z_image_turbo_bf16",
        "name": "Z-Image Turbo (로컬 ComfyUI)",
        "description": "로컬 ComfyUI z-image turbo - 무료, 빠름",
        "cost": 0,
        "params": {"width": 1024, "height": 576},
    },'''

# IMAGE_MODELS 딕셔너리의 첫 번째 항목 앞에 삽입
if '"z-image"' not in cfg:
    # "flux-schnell" 앞에 삽입
    marker = '    "flux-schnell"'
    if marker in cfg:
        cfg = cfg.replace(marker, ZIT_ENTRY + "\n" + marker)
        Path("app/config.py").write_text(cfg, encoding="utf-8", newline="\n")
        print("2) config.py에 z-image 모델 추가 완료")
    else:
        # IMAGE_MODELS = { 바로 뒤에 삽입
        marker2 = "IMAGE_MODELS = {"
        if marker2 in cfg:
            cfg = cfg.replace(marker2, marker2 + "\n" + ZIT_ENTRY)
            Path("app/config.py").write_text(cfg, encoding="utf-8", newline="\n")
            print("2) config.py에 z-image 모델 추가 완료 (IMAGE_MODELS 직후)")
        else:
            print("2) config.py에서 삽입 위치 못 찾음")
else:
    print("2) config.py에 z-image 이미 존재")

print("\nz-image 추가 완료! 서버 재시작 후 이미지 탭에서 'Z-Image Turbo' 선택 가능")
