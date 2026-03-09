"""
API 라우트 — 단계별 스튜디오 API
"""
import asyncio
import json
import traceback
from pathlib import Path
from fastapi import APIRouter, Request, Body
from fastapi import Form, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from sse_starlette.sse import EventSourceResponse

from app.main import templates
from app import config
from app.pipeline.utils import ensure_dir, generate_project_id, save_json, load_json
from app.pipeline import step1_script, step2_images, step3_tts, step4_video, step5_compose, step6_metadata
router = APIRouter()


# ═══════════════════════════════════════════════════════════
# 페이지
# ═══════════════════════════════════════════════════════════

@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "image_models": config.IMAGE_MODELS,
        "tts_voices": config.TTS_VOICES,
    })


# ═══════════════════════════════════════════════════════════
# API: 설정 정보
# ═══════════════════════════════════════════════════════════

@router.get("/api/models")
async def get_models():
    return {
        "image_models": {
            k: {"name": v["name"], "description": v["description"],
                "cost": v["cost"], "provider": v["provider"]}
            for k, v in config.IMAGE_MODELS.items()
        },
        "styles": step2_images.get_styles(),
        "tts_voices": config.TTS_VOICES,
    }


# ═══════════════════════════════════════════════════════════
# API: 프로젝트 생성
# ═══════════════════════════════════════════════════════════

@router.post("/api/project/create")
async def create_project(body: dict = Body(...)):
    article = body.get("article", "").strip()
    if not article:
        return JSONResponse({"error": "기사가 비어있습니다"}, status_code=400)

    project_id = generate_project_id()
    project_dir = ensure_dir(config.OUTPUT_DIR / project_id)
    (project_dir / "input_article.txt").write_text(article, encoding="utf-8")

    return {"project_id": project_id, "article_length": len(article)}


# ═══════════════════════════════════════════════════════════
# STEP 1: 대본 생성
# ═══════════════════════════════════════════════════════════

@router.post("/api/step1/generate")
async def step1_generate(body: dict = Body(...)):
    project_id = body["project_id"]
    category = body.get("category", "경제")
    project_dir = config.OUTPUT_DIR / project_id

    article = (project_dir / "input_article.txt").read_text(encoding="utf-8")

    try:
        script_data = await asyncio.to_thread(
            step1_script.generate_script, article, category
        )
        save_json(script_data, project_dir / "script.json")
        return {
            "status": "ok",
            "title": script_data.get("title", ""),
            "scene_count": len(script_data["scenes"]),
            "scenes": script_data["scenes"],
        }
    except Exception as e:
        return JSONResponse({"error": str(e), "traceback": traceback.format_exc()}, status_code=500)


# ═══════════════════════════════════════════════════════════
# STEP 1: 대본 저장 (사용자 수정 후)
# ═══════════════════════════════════════════════════════════

@router.post("/api/step1/save")
async def step1_save(body: dict = Body(...)):
    project_id = body["project_id"]
    scenes = body["scenes"]
    title = body.get("title", "")
    project_dir = config.OUTPUT_DIR / project_id

    script_data = {"title": title, "scenes": scenes}
    save_json(script_data, project_dir / "script.json")
    return {"status": "ok", "scene_count": len(scenes)}


# ═══════════════════════════════════════════════════════════
# STEP 2: 이미지 생성 (SSE — 장면별 실시간)
# ═══════════════════════════════════════════════════════════

@router.get("/api/step2/generate")
async def step2_generate(
    request: Request,
    project_id: str,
    style: str = "animation",
    image_model: str = "flux-schnell",
):
    project_dir = config.OUTPUT_DIR / project_id
    script_data = load_json(project_dir / "script.json")
    scenes = script_data["scenes"]

    async def event_gen():
        image_results = []
        for i, scene in enumerate(scenes):
            if await request.is_disconnected():
                return

            result = await asyncio.to_thread(
                step2_images.generate_single,
                scene, style, image_model, project_dir / "images"
            )
            image_results.append(result)

            yield {"event": "progress", "data": json.dumps({
                "current": i + 1,
                "total": len(scenes),
                "scene_id": scene["id"],
                "status": result["status"],
                "image_path": result.get("image_path", ""),
            }, ensure_ascii=False)}

        save_json(image_results, project_dir / "image_results.json")
        ok = sum(1 for r in image_results if r["status"] == "success")

        yield {"event": "complete", "data": json.dumps({
            "total": len(scenes),
            "success": ok,
            "failed": len(scenes) - ok,
        }, ensure_ascii=False)}

    return EventSourceResponse(event_gen())


# ═══════════════════════════════════════════════════════════
# STEP 2: 단일 장면 이미지 재생성
# ═══════════════════════════════════════════════════════════

@router.post("/api/step2/regenerate")
async def step2_regenerate(body: dict = Body(...)):
    project_id = body["project_id"]
    scene = body["scene"]
    style = body.get("style", "animation")
    image_model = body.get("image_model", "flux-schnell")
    project_dir = config.OUTPUT_DIR / project_id

    try:
        result = await asyncio.to_thread(
            step2_images.generate_single,
            scene, style, image_model, project_dir / "images"
        )

        # image_results.json 업데이트
        results_path = project_dir / "image_results.json"
        if results_path.exists():
            results = load_json(results_path)
            for idx, r in enumerate(results):
                if r.get("scene_id") == scene["id"]:
                    results[idx] = result
                    break
            save_json(results, results_path)

        return {"status": "ok", "result": result}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ═══════════════════════════════════════════════════════════
# STEP 3: TTS (SSE)
# ═══════════════════════════════════════════════════════════

# Edge TTS voice name → 내부 voice_id 매핑
_VOICE_COMPAT_MAP = {
     "ko-KR-SunHiNeural": "ko_sunhi",
    "ko-KR-InJoonNeural": "ko_injoon",
    "ko-KR-HyunsuNeural": "ko_hyunsu",
    "ko-KR-BongJinNeural": "ko_bongjin",
    "ko-KR-GookMinNeural": "ko_gookmin",
    "ko-KR-JiMinNeural": "ko_jimin",
    "ko-KR-SeoHyeonNeural": "ko_seohyeon",
    "ko-KR-SoonBokNeural": "ko_soonbok",
    "ko-KR-YuJinNeural": "ko_yujin",
    "en-US-AriaNeural": "en_heart",
    "ja-JP-NanamiNeural": "ja_alpha",
}

@router.get("/api/step3/generate")
async def step3_generate(
    request: Request,
    project_id: str,
    voice: str = "ko-KR-SunHiNeural",
    speed: float = 1.25,
):
    project_dir = config.OUTPUT_DIR / project_id
    script_data = load_json(project_dir / "script.json")
    scenes = script_data["scenes"]

    # voice 호환 처리: Edge TTS 이름이 오면 내부 ID로 변환
    voice_id = _VOICE_COMPAT_MAP.get(voice, voice)

    async def event_gen():
        audio_results = []
        for i, scene in enumerate(scenes):
            if await request.is_disconnected():
                return

            scene_id = scene.get("id", i + 1)
            narration = scene.get("narration", scene.get("text", ""))

            if not narration.strip():
                result = {
                    "scene_id": scene_id,
                    "path": None,
                    "duration": 0,
                    "engine": "skipped",
                    "status": "skipped",
                }
            else:
                try:
                    output_base = project_dir / "audio" / f"scene_{scene_id:03d}"
                    res = await asyncio.to_thread(
                        step3_tts.generate_scene_audio,
                        text=narration,
                        voice_id=voice_id,
                        speed=speed,
                        output_path=output_base,
                    )
                    result = {
                        "scene_id": scene_id,
                        "path": res["path"],
                        "duration": res["duration"],
                        "engine": res["engine"],
                        "status": "success",
                    }
                except Exception as e:
                    result = {
                        "scene_id": scene_id,
                        "path": None,
                        "duration": 0,
                        "engine": "error",
                        "status": "error",
                        "error": str(e),
                    }

            audio_results.append(result)

            yield {"event": "progress", "data": json.dumps({
                "current": i + 1,
                "total": len(scenes),
                "scene_id": scene_id,
                "status": result["status"],
                "duration": result.get("duration", 0),
            }, ensure_ascii=False)}

        save_json(audio_results, project_dir / "audio_results.json")
        total_dur = sum(r["duration"] for r in audio_results if r["status"] == "success")

        yield {"event": "complete", "data": json.dumps({
            "total": len(scenes),
            "total_duration": round(total_dur, 1),
        }, ensure_ascii=False)}

    return EventSourceResponse(event_gen())


# ═══════════════════════════════════════════════════════════
# STEP 4: 영상 합성
# ═══════════════════════════════════════════════════════════

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 4: 비디오 생성 (NEW)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.post("/api/step4/single-prompt")
async def step4_single_prompt(body: dict = Body(...)):
    """단일 씬 ITV 프롬프트 생성 (Gemini + 이미지)"""
    project_id = body["project_id"]
    scene_id = body["scene_id"]
    narration = body.get("narration", "")
    project_dir = config.OUTPUT_DIR / project_id
    image_path = project_dir / "images" / f"scene_{scene_id:03d}.png"

    try:
        from google import genai
        client = genai.Client(api_key=config.GEMINI_API_KEY)
        parts = []
        if image_path.exists():
            img_bytes = image_path.read_bytes()
            parts.append(genai.types.Part.from_bytes(data=img_bytes, mime_type="image/png"))

        system_msg = (
            "You are a video director for a cute 3D animated YouTube channel. "
            "Given this image and narration, write a SHORT English prompt (max 150 chars) "
            "describing camera movement and character motion for image-to-video AI.\n\n"
            f"Narration: {narration}\n\n"
            "Rules:\n"
            "- Describe camera movement (slow zoom, gentle pan, dolly) and character motion (nod, point, look surprised)\n"
            "- NO background music, NO dialogue. Only rare brief sound effects (gasp, pop).\n"
            "- Motion must match the narration content. No bizarre or unrelated movements.\n"
            "- Reply with ONLY the motion prompt, nothing else."
        )
        parts.append(system_msg)

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=parts,
        )
        prompt = response.text.strip().strip('"')
        return JSONResponse({"prompt": prompt})
    except Exception as e:
        return JSONResponse({"prompt": "Slow cinematic zoom in with gentle lighting", "error": str(e)})

@router.post("/api/step4/prompts")
async def step4_generate_prompts(body: dict = Body(...)):
    """각 씬의 I2V 프롬프트 생성 (수동 모드용)"""
    project_id = body["project_id"]
    project_dir = config.OUTPUT_DIR / project_id
    script_data = load_json(project_dir / "script.json")

    prompts = step4_video.generate_itv_prompts(
        script=script_data["scenes"],
        output_path=project_dir / "itv_prompts.json",
    )
    return JSONResponse({"prompts": prompts})


@router.get("/api/step4/generate")
async def step4_generate_videos(
    request: Request,
    project_id: str,
    mode: str = "comfyui",
    start: int = 1,
    end: int = 5,
    frame_count: int = 121,
):
    """비디오 생성 (SSE)"""
    project_dir = config.OUTPUT_DIR / project_id
    script_data = load_json(project_dir / "script.json")
    scenes = script_data["scenes"]

    # ITV 프롬프트 로드
    prompts_path = project_dir / "itv_prompts.json"
    itv_prompts = load_json(prompts_path) if prompts_path.exists() else []

    async def event_gen():
        video_results = []
        total = len(scenes)

        for idx, scene in enumerate(scenes):
            if await request.is_disconnected():
                return

            scene_id = scene.get("id", idx + 1)
            image_path = project_dir / "images" / f"scene_{scene_id:03d}.png"
            in_range = start <= scene_id <= end

            # 프롬프트 결정
            prompt = ""
            if idx < len(itv_prompts):
                p = itv_prompts[idx]
                prompt = p if isinstance(p, str) else p.get("itv_prompt", "")
            if not prompt:
                prompt = scene.get("image_prompt", "Cinematic slow zoom in")

            if in_range and image_path.exists() and mode != "manual":
                try:
                    result = await asyncio.to_thread(
                        step4_video.generate_single,
                        image_path=image_path,
                        prompt=prompt,
                        output_dir=project_dir / "videos",
                        scene_id=scene_id,
                        mode=mode,
                        frame_count=frame_count,
                    )
                except Exception as e:
                    result = {
                        "scene_id": scene_id,
                        "video_path": None,
                        "duration": 0,
                        "mode": "error",
                        "status": "error",
                        "error": str(e),
                    }
            else:
                result = {
                    "scene_id": scene_id,
                    "video_path": str(image_path) if image_path.exists() else None,
                    "duration": 0,
                    "mode": "slideshow",
                    "status": "slideshow",
                }

            video_results.append(result)

            yield {"event": "progress", "data": json.dumps({
                "current": idx + 1,
                "total": total,
                "scene_id": scene_id,
                "status": result["status"],
                "mode": result.get("mode", mode),
            }, ensure_ascii=False)}

        save_json(video_results, project_dir / "video_results.json")

        yield {"event": "complete", "data": json.dumps({
            "total": total,
            "success": sum(1 for r in video_results if r["status"] == "success"),
            "failed": sum(1 for r in video_results if r["status"] == "error"),
        }, ensure_ascii=False)}

    return EventSourceResponse(event_gen())

@router.post("/api/step4/regenerate")
async def step4_regenerate_video(body: dict = Body(...)):
    """단일 씬 비디오 재생성"""
    project_id = body["project_id"]
    scene_id = body["scene_id"]
    prompt = body.get("prompt", "")
    project_dir = config.OUTPUT_DIR / project_id

    image_path = project_dir / "images" / f"scene_{scene_id:03d}.png"
    if not image_path.exists():
        return JSONResponse({"error": "이미지가 없습니다"}, status_code=404)

    try:
        mode = body.get("mode", "comfyui")
        result = await asyncio.to_thread(
            step4_video.generate_single,
            image_path=image_path,
            prompt=prompt,
            output_dir=project_dir / "videos",
            scene_id=scene_id,
            mode=mode,
        )
        # video_results.json 업데이트
        results_path = project_dir / "video_results.json"
        if results_path.exists():
            all_results = load_json(results_path)
            updated = False
            for i, r in enumerate(all_results):
                if r.get("scene_id") == scene_id:
                    all_results[i] = result
                    updated = True
                    break
            if not updated:
                all_results.append(result)
            save_json(all_results, results_path)

        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/api/step4/upload")
async def step4_upload_video(
    project_id: str = Form(...),
    scene_id: int = Form(...),
    video: UploadFile = File(...),
):
    """수동 모드: 외부에서 만든 비디오 업로드"""
    project_dir = config.OUTPUT_DIR / project_id
    video_dir = project_dir / "videos"
    video_dir.mkdir(parents=True, exist_ok=True)

    output_path = video_dir / f"scene_{scene_id:03d}.mp4"
    with open(output_path, "wb") as f:
        content = await video.read()
        f.write(content)

    result = {
        "scene_id": scene_id,
        "video_path": str(output_path),
        "duration": 0,
        "mode": "manual-upload",
        "status": "success",
    }

    # video_results.json 업데이트
    results_path = project_dir / "video_results.json"
    if results_path.exists():
        all_results = load_json(results_path)
    else:
        all_results = []

    updated = False
    for i, r in enumerate(all_results):
        if r.get("scene_id") == scene_id:
            all_results[i] = result
            updated = True
            break
    if not updated:
        all_results.append(result)
    save_json(all_results, results_path)

    return JSONResponse(result)


@router.get("/api/project/{project_id}/video/{scene_id}")
async def get_scene_video(project_id: str, scene_id: int):
    """씬 비디오 파일 서빙"""
    video_dir = config.OUTPUT_DIR / project_id / "videos"
    for ext in [".mp4", ".webm"]:
        path = video_dir / f"scene_{scene_id:03d}{ext}"
        if path.exists():
            media_type = "video/mp4" if ext == ".mp4" else "video/webm"
            return FileResponse(path, media_type=media_type)
    return JSONResponse({"error": "비디오 없음"}, status_code=404)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 5: 영상 합성 (기존 step4)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.post("/api/step5/compose")
async def step5_run(body: dict = Body(...)):
    project_id = body["project_id"]
    burn_subs = body.get("burn_subtitles", True)
    project_dir = config.OUTPUT_DIR / project_id

    try:
        script_data = load_json(project_dir / "script.json")
        image_results = load_json(project_dir / "image_results.json") if (project_dir / "image_results.json").exists() else {}
        audio_results = load_json(project_dir / "audio_results.json") if (project_dir / "audio_results.json").exists() else {}

        output = await asyncio.to_thread(
            step5_compose.compose_video,
            script_data, image_results, audio_results, project_dir, burn_subs
        )
        video_url = f"/api/project/{project_id}/final/video"
        srt_url = f"/api/project/{project_id}/final/srt"
        return JSONResponse({"video_url": video_url, "srt_url": srt_url})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 6: 메타데이터 (기존 step5)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.post("/api/step6/metadata")
async def step6_run(body: dict = Body(...)):
    project_id = body["project_id"]
    project_dir = config.OUTPUT_DIR / project_id

    try:
        script_data = load_json(project_dir / "script.json")
        result = await asyncio.to_thread(
            step6_metadata.generate_metadata, script_data
        )
        # metadata.json 저장
        import json
        meta_path = project_dir / "metadata.json"
        meta_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return JSONResponse({"metadata": result})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/api/step6/thumbnail")
async def step6_thumbnail(body: dict = Body(...)):
    project_id = body["project_id"]
    project_dir = config.OUTPUT_DIR / project_id

    try:
        script_data = load_json(project_dir / "script.json")
        thumb_path = await asyncio.to_thread(
            step6_metadata.generate_thumbnail, script_data, project_dir
        )
        return JSONResponse({"thumbnail_url": f"/api/project/{project_id}/final/thumbnail"})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/project/{project_id}/final/thumbnail")
async def get_thumbnail(project_id: str):
    thumb_path = config.OUTPUT_DIR / project_id / "final" / "thumbnail.png"
    if thumb_path.exists():
        return FileResponse(thumb_path, media_type="image/png")
    return JSONResponse({"error": "썸네일 없음"}, status_code=404)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 프로젝트 Resume / 조회
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/api/project/{project_id}")
async def get_project(project_id: str):
    """프로젝트 전체 상태 조회 (Resume용)"""
    project_dir = config.OUTPUT_DIR / project_id
    if not project_dir.exists():
        return JSONResponse({"error": "프로젝트 없음"}, status_code=404)

    data = {"project_id": project_id, "steps": {}}

    # Step 1: 스크립트
    script_path = project_dir / "script.json"
    if script_path.exists():
        data["script"] = load_json(script_path)
        data["steps"]["script"] = "done"
    else:
        data["steps"]["script"] = "pending"

    # Step 2: 이미지
    img_path = project_dir / "image_results.json"
    if img_path.exists():
        data["image_results"] = load_json(img_path)
        data["steps"]["images"] = "done"
    else:
        data["steps"]["images"] = "pending"

    # Step 3: 오디오
    audio_path = project_dir / "audio_results.json"
    if audio_path.exists():
        data["audio_results"] = load_json(audio_path)
        data["steps"]["audio"] = "done"
    else:
        data["steps"]["audio"] = "pending"

    # Step 4: 비디오
    video_path = project_dir / "video_results.json"
    if video_path.exists():
        data["video_results"] = load_json(video_path)
        data["steps"]["video"] = "done"
    else:
        data["steps"]["video"] = "pending"

    # Step 5: 합성 영상
    final_video = project_dir / "final" / "output.mp4"
    if final_video.exists():
        data["video_url"] = f"/api/project/{project_id}/final/video"
        data["srt_url"] = f"/api/project/{project_id}/final/srt"
        data["steps"]["compose"] = "done"
    else:
        data["steps"]["compose"] = "pending"

    # Step 6: 메타데이터
    meta_path = project_dir / "metadata.json"
    if meta_path.exists():
        data["metadata"] = load_json(meta_path)
        data["steps"]["metadata"] = "done"
    else:
        data["steps"]["metadata"] = "pending"

    # ITV 프롬프트
    itv_path = project_dir / "itv_prompts.json"
    if itv_path.exists():
        data["itv_prompts"] = load_json(itv_path)

    return JSONResponse(data)


@router.get("/api/projects")
async def list_projects():
    """최근 프로젝트 목록 (Resume 선택용)"""
    output_dir = config.OUTPUT_DIR
    if not output_dir.exists():
        return JSONResponse({"projects": []})

    projects = []
    for d in sorted(output_dir.iterdir(), reverse=True):
        if d.is_dir() and (d / "script.json").exists():
            script = load_json(d / "script.json")
            title = script.get("title", d.name)
            scene_count = len(script.get("scenes", []))

            # 진행 상태 파악
            steps_done = []
            if (d / "script.json").exists(): steps_done.append("script")
            if (d / "image_results.json").exists(): steps_done.append("images")
            if (d / "audio_results.json").exists(): steps_done.append("audio")
            if (d / "video_results.json").exists(): steps_done.append("video")
            if (d / "final" / "output.mp4").exists(): steps_done.append("compose")
            if (d / "metadata.json").exists(): steps_done.append("metadata")

            projects.append({
                "project_id": d.name,
                "title": title,
                "scene_count": scene_count,
                "steps_done": steps_done,
                "has_video": (d / "final" / "output.mp4").exists(),
            })

    return JSONResponse({"projects": projects[:20]})


@router.get("/api/project/{project_id}/final/video")
async def get_final_video(project_id: str):
    path = config.OUTPUT_DIR / project_id / "final" / "output.mp4"
    if path.exists():
        return FileResponse(path, media_type="video/mp4")
    return JSONResponse({"error": "영상 없음"}, status_code=404)


@router.get("/api/project/{project_id}/final/srt")
async def get_final_srt(project_id: str):
    path = config.OUTPUT_DIR / project_id / "final" / "subtitles.srt"
    if path.exists():
        return FileResponse(path, media_type="text/plain")
    return JSONResponse({"error": "자막 없음"}, status_code=404)


@router.get("/api/project/{project_id}/image/{scene_id}")
async def get_scene_image(project_id: str, scene_id: int):
    path = config.OUTPUT_DIR / project_id / "images" / f"scene_{scene_id:03d}.png"
    if path.exists():
        return FileResponse(path, media_type="image/png")
    return JSONResponse({"error": "이미지 없음"}, status_code=404)


@router.get("/api/project/{project_id}/audio/{scene_id}")
async def get_scene_audio(project_id: str, scene_id: int):
    audio_dir = config.OUTPUT_DIR / project_id / "audio"
    for ext in [".wav", ".mp3"]:
        path = audio_dir / f"scene_{scene_id:03d}{ext}"
        if path.exists():
            mt = "audio/wav" if ext == ".wav" else "audio/mpeg"
            return FileResponse(path, media_type=mt)
    return JSONResponse({"error": "오디오 없음"}, status_code=404)

