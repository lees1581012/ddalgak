"""STEP 2: 이미지 생성 (Replicate / Google 선택)"""
import json
import time
import httpx
import replicate
from pathlib import Path
from google import genai
from app import config


def get_styles() -> dict:
    with open(config.PROMPTS_DIR / "image_style.json", "r", encoding="utf-8") as f:
        return json.load(f)


def build_prompt(image_prompt: str, style_key: str) -> str:
    styles = get_styles()
    style = styles.get(style_key, styles["animation"])
    return f"{style['prefix']} {image_prompt}{style['suffix']}"


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


_HANDLERS = {"replicate": _gen_replicate, "google": _gen_google}


def generate_single(scene: dict, style_key: str, model_key: str, output_dir: Path) -> dict:
    """단일 장면 이미지 생성"""
    output_dir.mkdir(parents=True, exist_ok=True)

    model_cfg = config.IMAGE_MODELS.get(model_key, config.IMAGE_MODELS[config.IMAGE_MODEL_DEFAULT])
    prompt = build_prompt(scene["image_prompt"], style_key)
    out_path = output_dir / f"scene_{scene['id']:03d}.png"

    try:
        handler = _HANDLERS[model_cfg["provider"]]
        handler(prompt, model_cfg, out_path)
        time.sleep(0.3)
        return {"scene_id": scene["id"], "image_path": str(out_path), "prompt": prompt, "status": "success"}
    except Exception as e:
        return {"scene_id": scene["id"], "image_path": None, "prompt": prompt, "status": f"failed: {e}"}