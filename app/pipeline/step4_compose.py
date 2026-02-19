"""STEP 4: FFmpeg 영상 합성"""
import subprocess
import shutil
from pathlib import Path
from app import config
from app.pipeline.utils import format_time_srt


def compose_video(image_results: list, audio_results: list,
                  script_data: dict, project_dir: Path,
                  burn_subtitles: bool = True) -> Path:

    final_dir = project_dir / "final"
    final_dir.mkdir(parents=True, exist_ok=True)
    video_dir = project_dir / "video"
    video_dir.mkdir(parents=True, exist_ok=True)

    # ── 오디오 합치기 ──
    audio_list = video_dir / "audio_list.txt"
    lines = [f"file '{r['audio_path']}'" for r in audio_results if r["status"] == "success"]
    audio_list.write_text("\n".join(lines), encoding="utf-8")

    merged_audio = video_dir / "merged.mp3"
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(audio_list), "-c", "copy", str(merged_audio)
    ], capture_output=True, check=True)

    # ── 이미지 concat 파일 ──
    img_list = video_dir / "img_list.txt"
    img_lines = []
    for img, aud in zip(image_results, audio_results):
        if img["status"] == "success" and aud["status"] == "success":
            img_lines.append(f"file '{img['image_path']}'")
            img_lines.append(f"duration {aud['duration']}")
    if img_lines:
        img_lines.append(img_lines[-2])
    img_list.write_text("\n".join(img_lines), encoding="utf-8")

    # ── SRT 자막 ──
    srt_path = video_dir / "subtitles.srt"
    srt_lines = []
    t = 0.0
    idx = 1
    for aud in audio_results:
        if aud["status"] != "success":
            continue
        end = t + aud["duration"]
        srt_lines += [str(idx), f"{format_time_srt(t)} --> {format_time_srt(end)}", aud["narration"], ""]
        t = end
        idx += 1
    srt_path.write_text("\n".join(srt_lines), encoding="utf-8")
    shutil.copy(srt_path, final_dir / "subtitles.srt")

    # ── FFmpeg 합성 ──
    res = config.VIDEO_RESOLUTION.replace("x", ":")
    output_path = final_dir / "output.mp4"

    # 기본 비디오 필터: 스케일 + 패딩
    vf = f"scale={res}:force_original_aspect_ratio=decrease,pad={res}:(ow-iw)/2:(oh-ih)/2,setsar=1"

    if burn_subtitles:
        # ★ 윈도우 경로 이스케이프 핵심 ★
        # FFmpeg subtitles 필터는 \ → / 변환, : → \\: 이스케이프 필요
        srt_str = str(srt_path).replace("\\", "/")
        srt_str = srt_str.replace(":", "\\:")

        style = (
            f"FontSize={config.SUBTITLE_FONTSIZE},"
            f"FontName={config.SUBTITLE_FONT},"
            f"PrimaryColour=&H00FFFFFF,"
            f"OutlineColour=&H00000000,"
            f"BorderStyle=3,"
            f"Outline={config.SUBTITLE_BORDERW},"
            f"Shadow=0,"
            f"MarginV=60"
        )
        vf += f",subtitles='{srt_str}':force_style='{style}'"

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(img_list),
        "-i", str(merged_audio),
        "-vf", vf,
        "-c:v", config.VIDEO_CODEC,
        "-crf", str(config.VIDEO_CRF),
        "-preset", "medium",
        "-c:a", "aac", "-b:a", "192k",
        "-r", str(config.VIDEO_FPS),
        "-shortest",
        "-movflags", "+faststart",
        str(output_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg 실패: {result.stderr[-500:]}")

    return output_path
