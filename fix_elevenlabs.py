"""ElevenLabs TTS 추가"""
from pathlib import Path

tts_path = Path("app/pipeline/step3_tts.py")
content = tts_path.read_text(encoding="utf-8")

# 1) import 추가 (edge_tts import 뒤에)
old_import = "import edge_tts"
new_import = """import edge_tts
import httpx
from app import config"""
content = content.replace(old_import, new_import)

# 2) TTS_VOICES에 윤아 추가 (ko_edge_hyunbin 뒤에)
old_voice = '''    "ko_edge_hyunbin": {
        "engine": "edge",
        "edge_voice": "ko-KR-HyunsuNeural",
        "label": "한국어 남성 (현수)",
        "lang": "ko",
    },
}'''
new_voice = '''    "ko_edge_hyunbin": {
        "engine": "edge",
        "edge_voice": "ko-KR-HyunsuNeural",
        "label": "한국어 남성 (현수)",
        "lang": "ko",
    },
    # ── 한국어 (ElevenLabs) ──
    "ko_yoona": {
        "engine": "elevenlabs",
        "elevenlabs_voice_id": "IXHT7Ws17HAtaafMMXqL",
        "label": "한국어 여성 — 윤아 (ElevenLabs, 자연스러운 톤)",
        "lang": "ko",
    },
}'''
content = content.replace(old_voice, new_voice)

# 3) ElevenLabs 생성 함수 추가 (_generate_edge 함수 앞에)
elevenlabs_func = '''
# ──────────────────────────────────────────────
# ElevenLabs TTS 생성
# ──────────────────────────────────────────────
def _generate_elevenlabs(
    text: str,
    voice_id: str,
    speed: float,
    output_path: Path,
) -> float:
    """
    ElevenLabs API로 음성 생성 → MP3 저장.
    반환값: 오디오 길이(초).
    """
    api_key = config.ELEVENLABS_API_KEY
    if not api_key:
        raise RuntimeError("ELEVENLABS_API_KEY가 설정되지 않았습니다. .env를 확인하세요.")

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
            "style": 0.3,
            "use_speaker_boost": True,
        },
    }

    resp = httpx.post(url, json=payload, headers=headers, timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(f"ElevenLabs API 오류: {resp.status_code} {resp.text[:200]}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(resp.content)

    duration = _estimate_mp3_duration(output_path)
    logger.info(f"ElevenLabs 생성 완료: {output_path.name} ({duration:.1f}s)")
    return duration


'''

# Edge TTS 생성 섹션 앞에 삽입
old_edge_section = "# ──────────────────────────────────────────────\n# Edge TTS 생성"
content = content.replace(old_edge_section, elevenlabs_func + old_edge_section)

# 4) generate_scene_audio에 elevenlabs 분기 추가
old_engine = '''    # Edge TTS 엔진
    mp3_path = output_path.with_suffix(".mp3")
    dur = _generate_edge(text, voice_cfg["edge_voice"], speed, mp3_path)'''
new_engine = '''    # ElevenLabs 엔진
    if engine == "elevenlabs":
        mp3_path = output_path.with_suffix(".mp3")
        dur = _generate_elevenlabs(text, voice_cfg["elevenlabs_voice_id"], speed, mp3_path)
        return {"path": str(mp3_path), "duration": dur, "engine": "elevenlabs"}

    # Edge TTS 엔진
    mp3_path = output_path.with_suffix(".mp3")
    dur = _generate_edge(text, voice_cfg["edge_voice"], speed, mp3_path)'''
content = content.replace(old_engine, new_engine)

tts_path.write_text(content, encoding="utf-8")
print("step3_tts.py에 ElevenLabs 윤아 음성 추가 완료!")