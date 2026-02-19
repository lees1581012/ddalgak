"""STEP 3: TTS (Edge TTS)"""
import edge_tts
from pathlib import Path
from mutagen.mp3 import MP3
from app import config


async def generate_single(scene: dict, voice: str, output_dir: Path) -> dict:
    """단일 장면 TTS 생성 (async)"""
    output_dir.mkdir(parents=True, exist_ok=True)

    if not voice:
        voice = config.TTS_VOICE_DEFAULT

    out_path = output_dir / f"scene_{scene['id']:03d}.mp3"

    try:
        comm = edge_tts.Communicate(text=scene["narration"], voice=voice)
        await comm.save(str(out_path))
        audio = MP3(str(out_path))
        duration = audio.info.length
        return {"scene_id": scene["id"], "audio_path": str(out_path),
                "duration": round(duration, 2), "narration": scene["narration"], "status": "success"}
    except Exception as e:
        return {"scene_id": scene["id"], "audio_path": None,
                "duration": 0, "narration": scene["narration"], "status": f"failed: {e}"}