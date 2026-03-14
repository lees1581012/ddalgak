"""Step 4: ?대?吏 ??鍮꾨뵒???대┰ ?앹꽦"""
import json
import os
import time
import uuid
import logging
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Optional

from google import genai
from app import config
from app.pipeline.utils import ensure_dir, save_json, load_json

logger = logging.getLogger(__name__)

COMFYUI_URL = config.COMFYUI_BASE_URL


# ?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧??
# Gemini ITV ?꾨＼?꾪듃 ?앹꽦
# ?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧??

def generate_itv_prompts(script: dict, output_path: Path = None) -> list:
    """Gemini濡?媛??щ퀎 ?대?吏?믩퉬?붿삤 蹂???꾨＼?꾪듃 ?앹꽦"""
    client = genai.Client(api_key=config.GEMINI_API_KEY)

    scenes = script if isinstance(script, list) else script.get("scenes", [])
    title = script.get("title", "") if isinstance(script, dict) else ""

    scene_list = ""
    for s in scenes:
        scene_list += f"- ??{s.get('id', '?')}: {s.get('narration', '')[:100]}\n"
        scene_list += f"  ?대?吏: {s.get('image_prompt', '')[:100]}\n"

    system_prompt = """You are an Image-to-Video (I2V) prompt specialist for a cute 3D animated YouTube channel.

Rules:
1. Write in English, max 150 characters per prompt.
2. ONLY describe what is ALREADY in the image. Do NOT add new characters, objects, animals, or people.
3. Do NOT change the background or setting. The scene must look identical to the source image.
4. Describe camera movement: slow zoom in, gentle pan, dolly forward, soft orbit, slight tilt, etc.
5. Describe subtle character motion ONLY for characters visible in the image: blinking, nodding, pointing, looking surprised, tilting head, breathing, tail swaying, etc.
6. NO background music. NO dialogue sounds. NO ambient noise. NO sound effects.
7. Keep movements smooth, slow, and gentle - no fast or jarring motions.
8. Do NOT morph, transform, or distort any element in the image.
9. Do NOT add text, UI elements, or watermarks.
10. Return ONLY a JSON array: ["prompt1", "prompt2", ...]
11. Array length must exactly match the number of scenes."""
    user_prompt = f"""Video title: {title}

Scenes:
{scene_list}

Generate {len(scenes)} I2V prompts. Return JSON array only."""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=user_prompt,
        config=genai.types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.7,
        ),
    )

    raw = response.text.strip()
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0].strip()
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0].strip()

    prompts = json.loads(raw)

    # 媛쒖닔 留욎텛湲?
    while len(prompts) < len(scenes):
        prompts.append("Slow cinematic zoom in with subtle ambient movement")
    prompts = prompts[:len(scenes)]

    # 고정 suffix: 뜬금없는 요소 방지
    ITV_SUFFIX = (
        ". Do not introduce any new elements. "
        "No new characters, animals, people, objects, or props that are not in the original image. "
        "No morphing, no transformation, no scene change. "
        "No text overlay, no subtitles, no UI. "
        "No sudden camera jumps or rapid movements. "
        "Only animate what already exists in the image with slow, gentle motion."
    )
    prompts = [p.rstrip(". ") + ITV_SUFFIX for p in prompts]

    if output_path:
        save_json(prompts, output_path)
        logger.info(f"ITV ?꾨＼?꾪듃 {len(prompts)}媛???? {output_path}")

    return prompts


# ?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧??
# Replicate API (minimax video-01-live)
# ?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧??

def generate_video_replicate(
    image_path: Path,
    prompt: str,
    output_dir: Path,
    scene_id: int,
    model: str = "minimax/video-01-live",
) -> dict:
    """Replicate API濡??대?吏 ??鍮꾨뵒???앹꽦"""
    import replicate
    import urllib.request as req

    ensure_dir(output_dir)

    logger.info(f"??{scene_id}: Replicate ({model}) ?쒖옉")

    # ?대?吏瑜?base64 data URI ?먮뒗 ?뚯씪濡??꾨떖
    with open(image_path, "rb") as f:
        image_data = f.read()

    try:
        output = replicate.run(
            model,
            input={
                "prompt": prompt,
                "first_frame_image": open(image_path, "rb"),
            },
        )

        # output? URL 臾몄옄???먮뒗 FileOutput
        video_url = str(output)
        if hasattr(output, "url"):
            video_url = output.url

        # ?ㅼ슫濡쒕뱶
        final_path = output_dir / f"scene_{scene_id:03d}.mp4"
        req.urlretrieve(video_url, str(final_path))

        logger.info(f"??{scene_id}: Replicate ?꾨즺 ??{final_path}")
        return {
            "scene_id": scene_id,
            "video_path": str(final_path),
            "duration": 5.0,
            "mode": "replicate",
            "status": "success",
        }

    except Exception as e:
        logger.error(f"??{scene_id}: Replicate ?ㅽ뙣 ??{e}")
        return {
            "scene_id": scene_id,
            "video_path": None,
            "duration": 0,
            "mode": "replicate",
            "status": "error",
            "error": str(e),
        }


# ?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧??
# Google Veo API
# ?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧??

def generate_video_google(
    image_path: Path,
    prompt: str,
    output_dir: Path,
    scene_id: int,
) -> dict:
    """Google Veo API濡??대?吏 ??鍮꾨뵒???앹꽦"""
    import base64

    ensure_dir(output_dir)
    logger.info(f"??{scene_id}: Google Veo ?쒖옉")

    try:
        client = genai.Client(api_key=config.GEMINI_API_KEY)

        # ?대?吏 濡쒕뱶
        with open(image_path, "rb") as f:
            image_bytes = f.read()

        image_part = genai.types.Part.from_bytes(
            data=image_bytes,
            mime_type="image/png",
        )

        # Veo濡?鍮꾨뵒???앹꽦
        response = client.models.generate_content(
            model="veo-2.0-generate-001",
            contents=[
                prompt,
                image_part,
            ],
            config=genai.types.GenerateContentConfig(
                response_modalities=["video"],
            ),
        )

        # 鍮꾨뵒??異붿텧
        final_path = output_dir / f"scene_{scene_id:03d}.mp4"

        for part in response.candidates[0].content.parts:
            if part.video_metadata is not None or hasattr(part, "inline_data"):
                video_data = part.inline_data.data
                with open(final_path, "wb") as f:
                    f.write(video_data)
                logger.info(f"??{scene_id}: Google Veo ?꾨즺 ??{final_path}")
                return {
                    "scene_id": scene_id,
                    "video_path": str(final_path),
                    "duration": 5.0,
                    "mode": "google-veo",
                    "status": "success",
                }

        raise ValueError("Veo ?묐떟?먯꽌 鍮꾨뵒?ㅻ? 李얠쓣 ???놁쓬")

    except Exception as e:
        logger.error(f"??{scene_id}: Google Veo ?ㅽ뙣 ??{e}")
        return {
            "scene_id": scene_id,
            "video_path": None,
            "duration": 0,
            "mode": "google-veo",
            "status": "error",
            "error": str(e),
        }


# ?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧??
# ComfyUI LTX2 (濡쒖뺄)
# ?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧??

def _comfy_post(endpoint: str, data: dict) -> dict:
    payload = json.dumps(data).encode("utf-8")
    url = f"{COMFYUI_URL}{endpoint}"
    logger.info(f"_comfy_post: URL={url}")
    logger.info(f"_comfy_post: payload length={len(payload)}")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            response_data = resp.read()
            logger.info(f"_comfy_post: response length={len(response_data)}, status={resp.status}")
            return json.loads(response_data)
    except urllib.error.HTTPError as e:
        logger.error(f"_comfy_post: HTTPError {e.code} - {e.reason}")
        logger.error(f"_comfy_post: response body: {e.read().decode() if e.readable() else 'N/A'}")
        raise
    except Exception as e:
        logger.error(f"_comfy_post: Exception → {e}")
        raise


def _comfy_get(endpoint: str) -> dict:
    with urllib.request.urlopen(f"{COMFYUI_URL}{endpoint}", timeout=30) as resp:
        return json.loads(resp.read())


def _upload_image_to_comfy(image_path: Path) -> str:
    """ComfyUI로 이미지 업로드 (httpx 사용)"""
    import httpx
    import mimetypes

    filename = image_path.name
    mime = mimetypes.guess_type(str(image_path))[0] or "image/png"

    try:
        with open(image_path, "rb") as f:
            files = {"image": (filename, f, mime)}
            response = httpx.post(
                f"{COMFYUI_URL}/upload/image",
                files=files,
                timeout=60.0
            )
            response.raise_for_status()
            result = response.json()
            uploaded_name = result.get("name", filename)
            logger.info(f"이미지 업로드 성공: {filename} → {uploaded_name}")
            return uploaded_name
    except Exception as e:
        logger.error(f"이미지 업로드 실패: {e}")
        # fallback: ComfyUI input 폴더에 직접 복사
        try:
            comfy_input = Path("C:/Users/A/Documents/ComfyUI/input")
            if comfy_input.exists():
                dest = comfy_input / filename
                import shutil
                shutil.copy2(image_path, dest)
                logger.info(f"fallback: 파일 직접 복사 → {dest}")
                return filename
            else:
                raise RuntimeError(f"ComfyUI input 폴더를 찾을 수 없음: {comfy_input}")
        except Exception as e2:
            logger.error(f"fallback도 실패: {e2}")
            raise RuntimeError(f"이미지 업로드 실패: {e}, fallback 실패: {e2}")



def _queue_prompt(workflow: dict) -> str:
    logger.info(f"_queue_prompt: 워크플로우 전송 시도")
    logger.info(f"_queue_prompt: COMFYUI_URL={COMFYUI_URL}")
    try:
        result = _comfy_post("/prompt", workflow)
        prompt_id = result.get("prompt_id")
        logger.info(f"_queue_prompt: 성공, prompt_id={prompt_id}")
        return prompt_id
    except Exception as e:
        logger.error(f"_queue_prompt: 실패 → {e}")
        raise


def _wait_for_completion(prompt_id: str, timeout: int = 600) -> dict:
    import time
    start = time.time()
    while time.time() - start < timeout:
        history = _comfy_get(f"/history/{prompt_id}")
        if prompt_id in history:
            status = history[prompt_id].get("status", {})
            if status.get("completed", False) or status.get("status_str") == "success":
                return history
            if status.get("status_str") == "error":
                msgs = status.get("messages", [])
                raise RuntimeError(f"ComfyUI error: {msgs}")
        time.sleep(3)
    raise TimeoutError(f"ComfyUI timeout ({timeout}s)")

def _build_ltx2_workflow(
    image_filename: str,
    prompt: str,
    frame_count: int = 121,
    seed: int = 10,
) -> dict:
    """LTX-2 I2V API ?뚰겕?뚮줈??(ComfyUI API Format)"""
    return {"prompt": {
        "75": {
            "inputs": {
                "filename_prefix": "ddalgak_i2v",
                "format": "auto",
                "codec": "auto",
                "video": ["92:97", 0]
            },
            "class_type": "SaveVideo"
        },
        "98": {
            "inputs": {"image": image_filename},
            "class_type": "LoadImage"
        },
        "102": {
            "inputs": {
                "longer_edge": 1536,
                "images": ["98", 0]
            },
            "class_type": "ResizeImagesByLongerEdge"
        },
        "92:8": {
            "inputs": {"sampler_name": "euler"},
            "class_type": "KSamplerSelect"
        },
        "92:9": {
            "inputs": {
                "steps": 20, "max_shift": 2.05, "base_shift": 0.95,
                "stretch": True, "terminal": 0.1,
                "latent": ["92:56", 0]
            },
            "class_type": "LTXVScheduler"
        },
        "92:60": {
            "inputs": {
                "text_encoder": "gemma_3_12B_it_fp4_mixed.safetensors",
                "ckpt_name": "ltx-2-19b-dev-fp8.safetensors",
                "device": "default"
            },
            "class_type": "LTXAVTextEncoderLoader"
        },
        "92:66": {
            "inputs": {"sampler_name": "gradient_estimation"},
            "class_type": "KSamplerSelect"
        },
        "92:73": {
            "inputs": {"sigmas": "0.909375, 0.725, 0.421875, 0.0"},
            "class_type": "ManualSigmas"
        },
        "92:81": {
            "inputs": {
                "positive": ["92:22", 0],
                "negative": ["92:22", 1],
                "latent": ["92:80", 0]
            },
            "class_type": "LTXVCropGuides"
        },
        "92:82": {
            "inputs": {
                "cfg": 1,
                "model": ["92:1", 0],
                "positive": ["92:81", 0],
                "negative": ["92:81", 1]
            },
            "class_type": "CFGGuider"
        },
        "92:51": {
            "inputs": {
                "frames_number": ["92:62", 0],
                "frame_rate": 25, "batch_size": 1,
                "audio_vae": ["92:48", 0]
            },
            "class_type": "LTXVEmptyLatentAudio"
        },
        "92:22": {
            "inputs": {
                "frame_rate": 25,
                "positive": ["92:3", 0],
                "negative": ["92:4", 0]
            },
            "class_type": "LTXVConditioning"
        },
        "92:4": {
            "inputs": {
                "text": "blurry, low quality, still frame, frames, watermark, overlay, titles, has blurbox, has subtitles",
                "clip": ["92:60", 0]
            },
            "class_type": "CLIPTextEncode"
        },
        "92:89": {
            "inputs": {
                "width": ["92:105", 0], "height": ["92:105", 1],
                "batch_size": 1, "color": 0
            },
            "class_type": "EmptyImage"
        },
        "92:41": {
            "inputs": {
                "noise": ["92:11", 0], "guider": ["92:47", 0],
                "sampler": ["92:8", 0], "sigmas": ["92:9", 0],
                "latent_image": ["92:56", 0]
            },
            "class_type": "SamplerCustomAdvanced"
        },
        "92:67": {
            "inputs": {"noise_seed": 0},
            "class_type": "RandomNoise"
        },
        "92:11": {
            "inputs": {"noise_seed": seed},
            "class_type": "RandomNoise"
        },
        "92:3": {
            "inputs": {
                "text": prompt,
                "clip": ["92:60", 0]
            },
            "class_type": "CLIPTextEncode"
        },
        "92:97": {
            "inputs": {
                "fps": 25,
                "images": ["92:95", 0],
                "audio": ["92:96", 0]
            },
            "class_type": "CreateVideo"
        },
        "92:80": {
            "inputs": {"av_latent": ["92:41", 0]},
            "class_type": "LTXVSeparateAVLatent"
        },
        "92:95": {
            "inputs": {
                "samples": ["92:94", 0],
                "vae": ["92:1", 2]
            },
            "class_type": "VAEDecode"
        },
        "92:94": {
            "inputs": {"av_latent": ["92:70", 1]},
            "class_type": "LTXVSeparateAVLatent"
        },
        "92:70": {
            "inputs": {
                "noise": ["92:67", 0], "guider": ["92:82", 0],
                "sampler": ["92:66", 0], "sigmas": ["92:73", 0],
                "latent_image": ["92:83", 0]
            },
            "class_type": "SamplerCustomAdvanced"
        },
        "92:96": {
            "inputs": {
                "samples": ["92:94", 1],
                "audio_vae": ["92:48", 0]
            },
            "class_type": "LTXVAudioVAEDecode"
        },
        "92:48": {
            "inputs": {"ckpt_name": "ltx-2-19b-dev-fp8.safetensors"},
            "class_type": "LTXVAudioVAELoader"
        },
        "92:56": {
            "inputs": {
                "video_latent": ["92:107", 0],
                "audio_latent": ["92:51", 0]
            },
            "class_type": "LTXVConcatAVLatent"
        },
        "92:90": {
            "inputs": {
                "upscale_method": "lanczos", "scale_by": 0.5,
                "image": ["92:89", 0]
            },
            "class_type": "ImageScaleBy"
        },
        "92:62": {
            "inputs": {"value": frame_count},
            "class_type": "PrimitiveInt"
        },
        "92:91": {
            "inputs": {"image": ["92:90", 0]},
            "class_type": "GetImageSize"
        },
        "92:105": {
            "inputs": {"image": ["102", 0]},
            "class_type": "GetImageSize"
        },
        "92:99": {
            "inputs": {
                "img_compression": 33,
                "image": ["92:106", 0]
            },
            "class_type": "LTXVPreprocess"
        },
        "92:43": {
            "inputs": {
                "width": ["92:91", 0], "height": ["92:91", 1],
                "length": ["92:62", 0], "batch_size": 1
            },
            "class_type": "EmptyLTXVLatentVideo"
        },
        "92:107": {
            "inputs": {
                "strength": 1, "bypass": False,
                "vae": ["92:1", 2],
                "image": ["92:99", 0],
                "latent": ["92:43", 0]
            },
            "class_type": "LTXVImgToVideoInplace"
        },
        "92:83": {
            "inputs": {
                "video_latent": ["92:108", 0],
                "audio_latent": ["92:80", 1]
            },
            "class_type": "LTXVConcatAVLatent"
        },
        "92:108": {
            "inputs": {
                "strength": 1, "bypass": False,
                "vae": ["92:1", 2],
                "image": ["92:99", 0],
                "latent": ["92:43", 0]
            },
            "class_type": "LTXVImgToVideoInplace"
        },
        "92:47": {
            "inputs": {
                "cfg": 4,
                "model": ["92:1", 0],
                "positive": ["92:22", 0],
                "negative": ["92:22", 1]
            },
            "class_type": "CFGGuider"
        },
        "92:106": {
            "inputs": {
                "longer_edge": 1536,
                "images": ["102", 0]
            },
            "class_type": "ResizeImagesByLongerEdge"
        },
        "92:1": {
            "inputs": {"ckpt_name": "ltx-2-19b-dev-fp8.safetensors"},
            "class_type": "CheckpointLoaderSimple"
        },
        
    }}
def generate_video_comfyui(image_path: Path, prompt: str, output_dir: Path,
                           scene_id: int, frame_count: int = 121) -> dict:
    """ComfyUI LTX2로 I2V 비디오 생성"""
    ensure_dir(output_dir)
    logger.info(f"씬 {scene_id}: ComfyUI LTX2 시작")

    try:
        # 1) 이미지 업로드
        logger.info(f"씬 {scene_id}: 이미지 업로드 시도 → {image_path}")
        image_filename = _upload_image_to_comfy(image_path)
        logger.info(f"씬 {scene_id}: 이미지 업로드 완료 → {image_filename}")

        # 2) 워크플로우 빌드
        import random
        seed = random.randint(1, 2**31)
        logger.info(f"씬 {scene_id}: 워크플로우 빌드 (seed={seed})")
        workflow = _build_ltx2_workflow(image_filename, prompt, frame_count, seed)
        logger.info(f"씬 {scene_id}: 워크플로우 빌드 완료")

        # 3) 큐 제출
        logger.info(f"씬 {scene_id}: ComfyUI 큐 제출 시도")
        prompt_id = _queue_prompt(workflow)
        logger.info(f"씬 {scene_id}: 큐 제출 완료 → {prompt_id}")

        # 4) 완료 대기
        logger.info(f"씬 {scene_id}: 완료 대기 시작 (timeout=600s)")
        history = _wait_for_completion(prompt_id, timeout=600)
        logger.info(f"씬 {scene_id}: 완료 대기 완료")

        # 5) 결과 다운로드
        logger.info(f"씬 {scene_id}: 비디오 다운로드 시도")
        video_path = _download_output(prompt_id, history, output_dir, scene_id)

        if video_path and video_path.exists():
            logger.info(f"씬 {scene_id}: 완료 → {video_path}")
            return {
                "scene_id": scene_id,
                "video_path": str(video_path),
                "duration": frame_count / 25.0,
                "mode": "comfyui",
                "status": "success",
            }
        else:
            logger.error(f"씬 {scene_id}: 출력 파일을 찾을 수 없음")
            return {
                "scene_id": scene_id,
                "video_path": None,
                "duration": 0,
                "mode": "comfyui",
                "status": "error",
                "error": "출력 파일을 찾을 수 없음",
            }

    except Exception as e:
        import traceback
        logger.error(f"씬 {scene_id}: ComfyUI 에러 → {e}")
        logger.error(f"씬 {scene_id}: Traceback:\n{traceback.format_exc()}")
        return {
            "scene_id": scene_id,
            "video_path": None,
            "duration": 0,
            "mode": "comfyui",
            "status": "error",
            "error": str(e),
        }


def _download_output(prompt_id: str, history_data: dict, output_dir: Path, 
                     scene_id: int) -> Optional[Path]:
    """ComfyUI 히스토리에서 생성된 비디오 다운로드"""
    outputs = history_data.get(prompt_id, {}).get("outputs", {})

    for node_id, node_out in outputs.items():
        # video, videos, gifs, images 키 모두 확인
        for key in ("video", "videos", "gifs", "images"):
            if key in node_out:
                for item in node_out[key]:
                    filename = item.get("filename", "")
                    subfolder = item.get("subfolder", "")
                    filetype = item.get("type", "output")

                    # ComfyUI /view API로 다운로드
                    params = f"filename={filename}&type={filetype}"
                    if subfolder:
                        params += f"&subfolder={subfolder}"
                    url = f"{COMFYUI_URL}/view?{params}"

                    try:
                        resp = urllib.request.urlopen(url)
                        video_data = resp.read()
                        ext = Path(filename).suffix or ".mp4"
                        if ext not in (".mp4", ".webm", ".mov"):
                            continue
                        final_path = output_dir / f"scene_{scene_id:03d}{ext}"
                        final_path.write_bytes(video_data)
                        logger.info(f"씬 {scene_id}: 다운로드 완료 ({len(video_data)} bytes)")
                        return final_path
                    except Exception as e:
                        logger.warning(f"씬 {scene_id}: 다운로드 실패 {filename}: {e}")
                        continue

    # fallback: ComfyUI output 폴더에서 직접 찾기
    comfy_output = Path("C:/Users/A/Documents/ComfyUI/output")
    import glob
    pattern = str(comfy_output / f"ddalgak_i2v_{scene_id:05d}*.mp4")
    matches = sorted(glob.glob(pattern), reverse=True)
    if not matches:
        pattern = str(comfy_output / "ddalgak_i2v_*.mp4")
        matches = sorted(glob.glob(pattern), key=lambda x: Path(x).stat().st_mtime, reverse=True)
    
    if matches:
        import shutil
        src = Path(matches[0])
        final_path = output_dir / f"scene_{scene_id:03d}.mp4"
        shutil.copy2(src, final_path)
        logger.info(f"씬 {scene_id}: fallback 복사 {src} -> {final_path}")
        return final_path

    logger.warning(f"씬 {scene_id}: ComfyUI 출력에서 비디오를 찾을 수 없음")
    return None


def generate_single(image_path: Path, prompt: str, output_dir: Path,
                    scene_id: int, mode: str = "comfyui", frame_count: int = 121) -> dict:
    """통합 비디오 생성 - 모드에 따라 분기"""
    if mode == "comfyui":
        return generate_video_comfyui(image_path, prompt, output_dir, scene_id, frame_count)
    elif mode in ("replicate", "seedance"):
        return generate_video_replicate(image_path, prompt, output_dir, scene_id)
    elif mode == "google":
        return generate_video_google(image_path, prompt, output_dir, scene_id)
    else:
        return {
            "scene_id": scene_id,
            "video_path": None,
            "duration": 0,
            "mode": mode,
            "status": "error",
            "error": f"Unknown mode: {mode}",
        }


