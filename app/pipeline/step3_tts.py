"""Step 3: TTS 음성 생성 (Edge TTS + Kokoro TTS 하이브리드)"""
import asyncio
import json
import os
import re
import logging
from pathlib import Path

import edge_tts
import numpy as np
import soundfile as sf

from app.pipeline.utils import ensure_dir, save_json, load_json

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Kokoro 파이프라인 캐시 (언어별 싱글턴)
# ──────────────────────────────────────────────
_kokoro_pipelines: dict = {}
_kokoro_available: bool | None = None


def _check_kokoro() -> bool:
    """Kokoro 라이브러리 사용 가능 여부 체크"""
    global _kokoro_available
    if _kokoro_available is None:
        try:
            from kokoro import KPipeline  # noqa: F401
            _kokoro_available = True
            logger.info("Kokoro TTS 사용 가능")
        except ImportError:
            _kokoro_available = False
            logger.warning("Kokoro TTS 미설치 — pip install kokoro>=0.9.4 soundfile")
    return _kokoro_available


def _get_kokoro_pipeline(lang_code: str):
    """
    언어 코드별 Kokoro KPipeline 싱글턴 반환.
    lang_code: 'a' (미국영어), 'b' (영국영어), 'j' (일본어)
    """
    if lang_code not in _kokoro_pipelines:
        from kokoro import KPipeline
        _kokoro_pipelines[lang_code] = KPipeline(lang_code=lang_code)
        logger.info(f"Kokoro pipeline 초기화 완료: lang_code='{lang_code}'")
    return _kokoro_pipelines[lang_code]


# ──────────────────────────────────────────────
# 엔진 & 음성 설정
# ──────────────────────────────────────────────
TTS_VOICES = {
    # ── 한국어 (Edge TTS) — 전체 9개 ──
    "ko_sunhi": {
        "engine": "edge",
        "edge_voice": "ko-KR-SunHiNeural",
        "label": "한국어 여성 — 선희 (밝은 톤)",
        "lang": "ko",
    },
    "ko_injoon": {
        "engine": "edge",
        "edge_voice": "ko-KR-InJoonNeural",
        "label": "한국어 남성 — 인준 (차분)",
        "lang": "ko",
    },
    "ko_hyunsu": {
        "engine": "edge",
        "edge_voice": "ko-KR-HyunsuNeural",
        "label": "한국어 남성 — 현수 (뉴스 앵커)",
        "lang": "ko",
    },
    "ko_bongjin": {
        "engine": "edge",
        "edge_voice": "ko-KR-BongJinNeural",
        "label": "한국어 남성 — 봉진",
        "lang": "ko",
    },
    "ko_gookmin": {
        "engine": "edge",
        "edge_voice": "ko-KR-GookMinNeural",
        "label": "한국어 남성 — 국민",
        "lang": "ko",
    },
    "ko_jimin": {
        "engine": "edge",
        "edge_voice": "ko-KR-JiMinNeural",
        "label": "한국어 여성 — 지민",
        "lang": "ko",
    },
    "ko_seohyeon": {
        "engine": "edge",
        "edge_voice": "ko-KR-SeoHyeonNeural",
        "label": "한국어 여성 — 서현",
        "lang": "ko",
    },
    "ko_soonbok": {
        "engine": "edge",
        "edge_voice": "ko-KR-SoonBokNeural",
        "label": "한국어 여성 — 순복 (나이든 톤)",
        "lang": "ko",
    },
    "ko_yujin": {
        "engine": "edge",
        "edge_voice": "ko-KR-YuJinNeural",
        "label": "한국어 여성 — 유진",
        "lang": "ko",
    },
    # ── 영어 — 미국 (Kokoro) ──
    "en_heart": {
        "engine": "kokoro",
        "kokoro_lang": "a",
        "kokoro_voice": "af_heart",
        "label": "English Female — Heart (US)",
        "lang": "en",
    },
    "en_bella": {
        "engine": "kokoro",
        "kokoro_lang": "a",
        "kokoro_voice": "af_bella",
        "label": "English Female — Bella (US)",
        "lang": "en",
    },
    "en_nicole": {
        "engine": "kokoro",
        "kokoro_lang": "a",
        "kokoro_voice": "af_nicole",
        "label": "English Female — Nicole (US)",
        "lang": "en",
    },
    "en_sarah": {
        "engine": "kokoro",
        "kokoro_lang": "a",
        "kokoro_voice": "af_sarah",
        "label": "English Female — Sarah (US)",
        "lang": "en",
    },
    "en_adam": {
        "engine": "kokoro",
        "kokoro_lang": "a",
        "kokoro_voice": "am_adam",
        "label": "English Male — Adam (US)",
        "lang": "en",
    },
    "en_michael": {
        "engine": "kokoro",
        "kokoro_lang": "a",
        "kokoro_voice": "am_michael",
        "label": "English Male — Michael (US)",
        "lang": "en",
    },
    "en_fenrir": {
        "engine": "kokoro",
        "kokoro_lang": "a",
        "kokoro_voice": "am_fenrir",
        "label": "English Male — Fenrir (US)",
        "lang": "en",
    },
    "en_puck": {
        "engine": "kokoro",
        "kokoro_lang": "a",
        "kokoro_voice": "am_puck",
        "label": "English Male — Puck (US)",
        "lang": "en",
    },
    # ── 영어 — 영국 (Kokoro) ──
    "en_emma": {
        "engine": "kokoro",
        "kokoro_lang": "b",
        "kokoro_voice": "bf_emma",
        "label": "English Female — Emma (UK)",
        "lang": "en",
    },
    "en_alice": {
        "engine": "kokoro",
        "kokoro_lang": "b",
        "kokoro_voice": "bf_alice",
        "label": "English Female — Alice (UK)",
        "lang": "en",
    },
    "en_george": {
        "engine": "kokoro",
        "kokoro_lang": "b",
        "kokoro_voice": "bm_george",
        "label": "English Male — George (UK)",
        "lang": "en",
    },
    "en_daniel": {
        "engine": "kokoro",
        "kokoro_lang": "b",
        "kokoro_voice": "bm_daniel",
        "label": "English Male — Daniel (UK)",
        "lang": "en",
    },
    # ── 일본어 (Kokoro) ──
    "ja_alpha": {
        "engine": "kokoro",
        "kokoro_lang": "j",
        "kokoro_voice": "jf_alpha",
        "label": "日本語 女性 — Alpha",
        "lang": "ja",
    },
    "ja_gongitsune": {
        "engine": "kokoro",
        "kokoro_lang": "j",
        "kokoro_voice": "jf_gongitsune",
        "label": "日本語 女性 — Gongitsune",
        "lang": "ja",
    },
    "ja_tebukuro": {
        "engine": "kokoro",
        "kokoro_lang": "j",
        "kokoro_voice": "jf_tebukuro",
        "label": "日本語 女性 — Tebukuro",
        "lang": "ja",
    },
    "ja_nezumi": {
        "engine": "kokoro",
        "kokoro_lang": "j",
        "kokoro_voice": "jf_nezumi",
        "label": "日本語 女性 — Nezumi",
        "lang": "ja",
    },
    "ja_kumo": {
        "engine": "kokoro",
        "kokoro_lang": "j",
        "kokoro_voice": "jm_kumo",
        "label": "日本語 男性 — Kumo",
        "lang": "ja",
    },
    # ── 한국어 Edge TTS 추가 폴백 ──
    "ko_edge_hyunbin": {
        "engine": "edge",
        "edge_voice": "ko-KR-HyunsuNeural",
        "label": "한국어 남성 (현수)",
        "lang": "ko",
    },
}

# Edge TTS 기본 폴백 (Kokoro 실패 시)
EDGE_FALLBACK = {
    "en": "en-US-AriaNeural",
    "ja": "ja-JP-NanamiNeural",
    "ko": "ko-KR-SunHiNeural",
}


def get_voice_list() -> list[dict]:
    """UI에 표시할 음성 목록 반환"""
    kokoro_ok = _check_kokoro()
    result = []
    for vid, info in TTS_VOICES.items():
        available = True
        if info["engine"] == "kokoro" and not kokoro_ok:
            available = False
        result.append({
            "id": vid,
            "label": info["label"],
            "lang": info["lang"],
            "engine": info["engine"],
            "available": available,
        })
    return result


# ──────────────────────────────────────────────
# Kokoro TTS 생성
# ──────────────────────────────────────────────
def _generate_kokoro(
    text: str,
    lang_code: str,
    voice_name: str,
    speed: float,
    output_path: Path,
) -> float:
    """
    Kokoro로 음성 생성 → WAV 저장.
    반환값: 오디오 길이(초).
    """
    pipeline = _get_kokoro_pipeline(lang_code)
    generator = pipeline(text, voice=voice_name, speed=speed)

    chunks = []
    for _gs, _ps, audio in generator:
        if audio is not None and len(audio) > 0:
            chunks.append(audio)

    if not chunks:
        raise RuntimeError("Kokoro가 오디오를 생성하지 못했습니다.")

    full_audio = np.concatenate(chunks)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(output_path), full_audio, 24000)

    duration = len(full_audio) / 24000
    logger.info(f"Kokoro 생성 완료: {output_path.name} ({duration:.1f}s)")
    return duration


# ──────────────────────────────────────────────
# Edge TTS 생성
# ──────────────────────────────────────────────
async def _generate_edge_async(
    text: str,
    edge_voice: str,
    speed: float,
    output_path: Path,
) -> float:
    """
    Edge TTS로 음성 생성 → MP3 저장.
    반환값: 오디오 길이(초).
    """
    rate_str = f"{int((speed - 1) * 100):+d}%"
    communicate = edge_tts.Communicate(text, edge_voice, rate=rate_str)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    await communicate.save(str(output_path))

    # 오디오 길이 계산 (mutagen 또는 추정)
    duration = _estimate_mp3_duration(output_path)
    logger.info(f"Edge TTS 생성 완료: {output_path.name} ({duration:.1f}s)")
    return duration


def _generate_edge(
    text: str,
    edge_voice: str,
    speed: float,
    output_path: Path,
) -> float:
    """Edge TTS 동기 래퍼"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(
            _generate_edge_async(text, edge_voice, speed, output_path)
        )
    finally:
        loop.close()


def _estimate_mp3_duration(path: Path) -> float:
    """MP3 파일 길이 추정 (mutagen 사용 시도 → 실패 시 파일크기 기반 추정)"""
    try:
        from mutagen.mp3 import MP3
        audio = MP3(str(path))
        return audio.info.length
    except Exception:
        # 128kbps 기준 추정
        size_bytes = path.stat().st_size
        return size_bytes / (128 * 1024 / 8)


# ──────────────────────────────────────────────
# 통합 생성 함수 (단일 씬)
# ──────────────────────────────────────────────
def generate_scene_audio(
    text: str,
    voice_id: str,
    speed: float,
    output_path: Path,
) -> dict:
    """
    씬 하나의 TTS 생성. 엔진 자동 분기.
    반환: {"path": str, "duration": float, "engine": str}
    """
    voice_cfg = TTS_VOICES.get(voice_id)
    if not voice_cfg:
        raise ValueError(f"알 수 없는 음성 ID: {voice_id}")

    engine = voice_cfg["engine"]

    # Kokoro 시도
    if engine == "kokoro" and _check_kokoro():
        try:
            wav_path = output_path.with_suffix(".wav")
            dur = _generate_kokoro(
                text=text,
                lang_code=voice_cfg["kokoro_lang"],
                voice_name=voice_cfg["kokoro_voice"],
                speed=speed,
                output_path=wav_path,
            )
            return {"path": str(wav_path), "duration": dur, "engine": "kokoro"}
        except Exception as e:
            logger.warning(f"Kokoro 실패, Edge TTS 폴백: {e}")
            # Edge TTS 폴백
            lang = voice_cfg.get("lang", "en")
            fallback_voice = EDGE_FALLBACK.get(lang, "en-US-AriaNeural")
            mp3_path = output_path.with_suffix(".mp3")
            dur = _generate_edge(text, fallback_voice, speed, mp3_path)
            return {"path": str(mp3_path), "duration": dur, "engine": "edge-fallback"}

    # Kokoro 미설치 or Edge TTS 엔진
    if engine == "kokoro" and not _check_kokoro():
        logger.warning(f"Kokoro 미설치 — Edge TTS 폴백 사용")
        lang = voice_cfg.get("lang", "en")
        fallback_voice = EDGE_FALLBACK.get(lang, "en-US-AriaNeural")
        mp3_path = output_path.with_suffix(".mp3")
        dur = _generate_edge(text, fallback_voice, speed, mp3_path)
        return {"path": str(mp3_path), "duration": dur, "engine": "edge-fallback"}

    # Edge TTS 엔진
    mp3_path = output_path.with_suffix(".mp3")
    dur = _generate_edge(text, voice_cfg["edge_voice"], speed, mp3_path)
    return {"path": str(mp3_path), "duration": dur, "engine": "edge"}


# ──────────────────────────────────────────────
# 전체 씬 일괄 생성 (SSE 진행률 콜백)
# ──────────────────────────────────────────────
def generate_all_audio(
    project_dir: Path,
    script: list[dict],
    voice_id: str,
    speed: float = 1.15,
    progress_callback=None,
) -> list[dict]:
    """
    모든 씬의 TTS를 순차 생성.
    progress_callback(current, total, scene_result) 형태.
    반환: [{"scene_id": int, "path": str, "duration": float, "engine": str}, ...]
    """
    audio_dir = ensure_dir(project_dir / "audio")
    results = []
    total = len(script)

    for idx, scene in enumerate(script):
        scene_id = scene.get("scene_id", idx + 1)
        narration = scene.get("narration", scene.get("text", ""))

        if not narration.strip():
            logger.warning(f"씬 {scene_id}: 나레이션 텍스트 없음, 건너뜀")
            result = {
                "scene_id": scene_id,
                "path": None,
                "duration": 0,
                "engine": "skipped",
            }
            results.append(result)
            if progress_callback:
                progress_callback(idx + 1, total, result)
            continue

        output_base = audio_dir / f"scene_{scene_id:03d}"

        try:
            result = generate_scene_audio(
                text=narration,
                voice_id=voice_id,
                speed=speed,
                output_path=output_base,
            )
            result["scene_id"] = scene_id
        except Exception as e:
            logger.error(f"씬 {scene_id} TTS 실패: {e}")
            result = {
                "scene_id": scene_id,
                "path": None,
                "duration": 0,
                "engine": "error",
                "error": str(e),
            }

        results.append(result)
        if progress_callback:
            progress_callback(idx + 1, total, result)

    # 결과 저장
    save_json(results, project_dir / "audio_results.json")
    return results


# ──────────────────────────────────────────────
# 단일 씬 재생성
# ──────────────────────────────────────────────
def regenerate_scene_audio(
    project_dir: Path,
    scene_id: int,
    narration: str,
    voice_id: str,
    speed: float = 1.15,
) -> dict:
    """기존 오디오 삭제 후 재생성"""
    audio_dir = ensure_dir(project_dir / "audio")

    # 기존 파일 삭제
    for ext in [".wav", ".mp3"]:
        old = audio_dir / f"scene_{scene_id:03d}{ext}"
        if old.exists():
            old.unlink()

    output_base = audio_dir / f"scene_{scene_id:03d}"
    result = generate_scene_audio(
        text=narration,
        voice_id=voice_id,
        speed=speed,
        output_path=output_base,
    )
    result["scene_id"] = scene_id

    # audio_results.json 업데이트
    results_path = project_dir / "audio_results.json"
    if results_path.exists():
        all_results = load_json(results_path)
        # 기존 항목 교체 or 추가
        updated = False
        for i, r in enumerate(all_results):
            if r.get("scene_id") == scene_id:
                all_results[i] = result
                updated = True
                break
        if not updated:
            all_results.append(result)
        save_json(all_results, results_path)

    return result
