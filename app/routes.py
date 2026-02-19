"""
API 라우트 — SSE로 실시간 진행 상황 스트리밍
"""
import asyncio
import json
import traceback
from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from sse_starlette.sse import EventSourceResponse

from app.main import templates
from app import config
from app.pipeline.utils import ensure_dir, generate_project_id, save_json
from app.pipeline import step1_script, step2_images, step3_tts, step4_compose, step5_metadata

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
# API: 파이프라인 실행 (SSE 스트리밍)
# ═══════════════════════════════════════════════════════════

@router.get("/api/run")
async def run_pipeline(
    request: Request,
    article: str,
    category: str = "경제",
    style: str = "animation",
    image_model: str = "flux-schnell",
    voice: str = "ko-KR-SunHiNeural",
    burn_subs: bool = True,
):
    """
    파이프라인 실행 — SSE로 진행 상황 실시간 스트리밍
    """
    async def event_generator():
        project_id = generate_project_id()
        project_dir = ensure_dir(config.OUTPUT_DIR / project_id)

        def send(step: str, status: str, message: str, data: dict = None):
            payload = {"step": step, "status": status, "message": message,
                       "project_id": project_id}
            if data:
                payload["data"] = data
            return json.dumps(payload, ensure_ascii=False)

        try:
            # ─── 기사 저장 ───
            (project_dir / "input_article.txt").write_text(article, encoding="utf-8")
            yield {"event": "progress", "data": send("init", "ok", f"프로젝트 생성: {project_id}")}

            # ─── STEP 1: 대본 생성 ───
            yield {"event": "progress", "data": send("script", "running", "대본 생성 중...")}
            await asyncio.sleep(0)  # yield 제어권

            script_data = await asyncio.to_thread(
                step1_script.generate_script, article, category
            )
            save_json(script_data, project_dir / "script.json")

            scene_count = len(script_data["scenes"])
            yield {"event": "progress", "data": send("script", "done",
                f"대본 완료: {script_data.get('title', '')} ({scene_count}장면)",
                {"title": script_data.get("title"), "scene_count": scene_count}
            )}

            # ─── STEP 2: 이미지 일괄 생성 ───
            yield {"event": "progress", "data": send("images", "running",
                f"이미지 생성 시작 (0/{scene_count})"
            )}

            image_results = []
            for i, scene in enumerate(script_data["scenes"]):
                # 연결 끊김 체크
                if await request.is_disconnected():
                    return

                result = await asyncio.to_thread(
                    step2_images.generate_single,
                    scene, style, image_model, project_dir / "images"
                )
                image_results.append(result)

                yield {"event": "progress", "data": send("images", "running",
                    f"이미지 생성 중 ({i+1}/{scene_count})",
                    {"current": i+1, "total": scene_count,
                     "scene_id": scene["id"],
                     "status": result["status"]}
                )}

            save_json(image_results, project_dir / "image_results.json")
            ok_count = sum(1 for r in image_results if r["status"] == "success")
            yield {"event": "progress", "data": send("images", "done",
                f"이미지 완료: {ok_count}/{scene_count}장"
            )}

            # ─── STEP 3: TTS ───
            yield {"event": "progress", "data": send("tts", "running", "음성 생성 시작...")}

            audio_results = []
            for i, scene in enumerate(script_data["scenes"]):
                if await request.is_disconnected():
                    return

                result = await step3_tts.generate_single(
                    scene, voice, project_dir / "audio"
                )
                audio_results.append(result)

                yield {"event": "progress", "data": send("tts", "running",
                    f"음성 생성 중 ({i+1}/{scene_count})",
                    {"current": i+1, "total": scene_count}
                )}

            save_json(audio_results, project_dir / "audio_results.json")
            total_dur = sum(r["duration"] for r in audio_results if r["status"] == "success")
            yield {"event": "progress", "data": send("tts", "done",
                f"음성 완료: {total_dur:.0f}초 ({total_dur/60:.1f}분)"
            )}

            # ─── STEP 4: 영상 합성 ───
            yield {"event": "progress", "data": send("compose", "running",
                "영상 합성 중... (시간이 걸릴 수 있습니다)"
            )}

            output_video = await asyncio.to_thread(
                step4_compose.compose_video,
                image_results, audio_results, script_data,
                project_dir, burn_subs
            )

            yield {"event": "progress", "data": send("compose", "done",
                f"영상 합성 완료"
            )}

            # ─── STEP 5: 메타데이터 + 썸네일 ───
            yield {"event": "progress", "data": send("metadata", "running", "메타데이터 생성 중...")}

            metadata = await asyncio.to_thread(
                step5_metadata.generate_metadata, script_data
            )
            save_json(metadata, project_dir / "final" / "metadata.json")

            yield {"event": "progress", "data": send("metadata", "running", "썸네일 생성 중...")}

            try:
                await asyncio.to_thread(
                    step5_metadata.generate_thumbnail, script_data, project_dir
                )
            except Exception:
                pass  # 썸네일 실패해도 계속 진행

            yield {"event": "progress", "data": send("metadata", "done", "메타데이터 완료")}

            # ─── 완료 ───
            video_url = f"/output/{project_id}/final/{output_video.name}"
            thumb_url = f"/output/{project_id}/final/thumbnail.png"
            srt_url = f"/output/{project_id}/final/subtitles.srt"

            yield {"event": "complete", "data": json.dumps({
                "project_id": project_id,
                "video_url": video_url,
                "thumbnail_url": thumb_url,
                "srt_url": srt_url,
                "metadata": metadata,
                "script": script_data,
                "total_duration": total_dur,
                "image_count": ok_count,
            }, ensure_ascii=False)}

        except Exception as e:
            yield {"event": "error", "data": json.dumps({
                "message": str(e),
                "traceback": traceback.format_exc(),
            }, ensure_ascii=False)}

    return EventSourceResponse(event_generator())


# ═══════════════════════════════════════════════════════════
# API: 프로젝트 목록
# ═══════════════════════════════════════════════════════════

@router.get("/api/projects")
async def list_projects():
    projects = []
    if config.OUTPUT_DIR.exists():
        for d in sorted(config.OUTPUT_DIR.iterdir(), reverse=True):
            if d.is_dir():
                meta_path = d / "final" / "metadata.json"
                script_path = d / "script.json"
                info = {"id": d.name, "has_video": (d / "final").exists()}
                if script_path.exists():
                    import json as j
                    s = j.loads(script_path.read_text(encoding="utf-8"))
                    info["title"] = s.get("title", "")
                if meta_path.exists():
                    info["has_metadata"] = True
                projects.append(info)
    return projects