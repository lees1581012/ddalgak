"""STEP 5: 메타데이터 + 썸네일"""
import httpx
import replicate
from pathlib import Path
from google import genai
from app import config
from app.pipeline.utils import extract_json_from_text


def generate_metadata(script_data: dict) -> dict:
    client = genai.Client(api_key=config.GEMINI_API_KEY)
    narration = "\n".join(f"[{s['id']}] {s['narration']}" for s in script_data["scenes"])

    meta_prompt = (config.PROMPTS_DIR / "metadata.txt").read_text(encoding="utf-8")

    response = client.models.generate_content(
        model=config.SCRIPT_MODEL,
        contents=f"## 영상 제목: {script_data.get('title','')}\n\n## 대본:\n{narration}\n\n메타데이터를 생성해 주세요.",
        config=genai.types.GenerateContentConfig(system_instruction=meta_prompt, temperature=0.7),
    )
    return extract_json_from_text(response.text)


def generate_thumbnail(script_data: dict, project_dir: Path) -> Path:
    client = genai.Client(api_key=config.GEMINI_API_KEY)
    resp = client.models.generate_content(
        model=config.SCRIPT_MODEL,
        contents=f"영상 제목: {script_data.get('title','')}\n첫 장면: {script_data['scenes'][0]['narration']}\n\n이 유튜브 영상의 썸네일 이미지를 위한 영어 프롬프트를 하나만 작성해 주세요. 프롬프트만 출력.",
    )
    prompt = f"YouTube thumbnail, eye-catching, bold, {resp.text.strip()}"

    output = replicate.run("black-forest-labs/flux-schnell",
        input={"prompt": prompt, "aspect_ratio": "16:9", "num_outputs": 1, "output_format": "png", "go_fast": True})

    url = str(output[0]) if isinstance(output, list) else str(output)
    thumb_path = project_dir / "final" / "thumbnail.png"
    thumb_path.parent.mkdir(parents=True, exist_ok=True)
    thumb_path.write_bytes(httpx.get(url, timeout=120, follow_redirects=True).content)
    return thumb_path