#!/usr/bin/env python3
"""
step4_compose.py – 이미지 + 오디오 + 자막 → MP4
Windows FFmpeg 호환 (경로 이스케이프 수정)
"""
import json
import subprocess
import shutil
from pathlib import Path
from rich.console import Console
from rich.progress import Progress

console = Console()


def _escape_srt_path(path: Path) -> str:
    """FFmpeg subtitles 필터용 경로 이스케이프 (Windows 대응)"""
    s = str(path.resolve()).replace("\\", "/")
    s = s.replace(":", "\\:")
    return s


def _get_audio_duration(audio_path: Path) -> float:
    """ffprobe로 오디오 길이(초) 반환"""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "csv=p=0",
        str(audio_path)
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return float(result.stdout.strip())
    except Exception:
        return 5.0  # fallback


def compose_video(
    script_data: dict,
    image_results: dict,
    audio_results: dict,
    project_dir: Path,
    burn_subtitles: bool = True,
) -> Path:
    """이미지 슬라이드쇼 + 오디오 + 자막 → final/output.mp4"""

    scenes = script_data["scenes"]
    images_dir = project_dir / "images"
    audio_dir = project_dir / "audio"
    final_dir = project_dir / "final"
    final_dir.mkdir(parents=True, exist_ok=True)

    # ── 1) 장면별 duration 수집 ──
    durations = []
    for i, scene in enumerate(scenes):
        audio_file = audio_dir / f"scene_{scene['id']:03d}.mp3"
        if audio_file.exists():
            dur = _get_audio_duration(audio_file)
        else:
            dur = 5.0
        durations.append(max(dur, 1.0))

    total_duration = sum(durations)
    console.print(f"  총 장면: {len(scenes)}개, 총 길이: {total_duration:.1f}초")

    # ── 2) 오디오 concat ──
    audio_list_file = project_dir / "audio_concat.txt"
    with open(audio_list_file, "w", encoding="utf-8") as f:
        for i, scene in enumerate(scenes):
            audio_file = audio_dir / f"scene_{scene['id']:03d}.mp3"
            if audio_file.exists():
                safe = str(audio_file.resolve()).replace("\\", "/")
                f.write(f"file '{safe}'\n")

    merged_audio = project_dir / "merged_audio.mp3"
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(audio_list_file),
        "-c", "copy", str(merged_audio)
    ], capture_output=True, timeout=120)

    # ── 3) SRT 자막 생성 ──
    srt_path = final_dir / "subtitles.srt"
    current_time = 0.0
    with open(srt_path, "w", encoding="utf-8") as f:
        for i, scene in enumerate(scenes):
            start = current_time
            end = current_time + durations[i]

            def fmt(t):
                h = int(t // 3600)
                m = int((t % 3600) // 60)
                s = int(t % 60)
                ms = int((t - int(t)) * 1000)
                return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

            f.write(f"{i+1}\n")
            f.write(f"{fmt(start)} --> {fmt(end)}\n")
            f.write(f"{scene['narration']}\n\n")
            current_time = end

    console.print(f"  자막 생성: {srt_path}")

    # ── 4) 이미지 슬라이드쇼 입력 생성 ──
    img_list_file = project_dir / "image_list.txt"
    with open(img_list_file, "w", encoding="utf-8") as f:
        for i, scene in enumerate(scenes):
            img_file = images_dir / f"scene_{scene['id']:03d}.png"
            if img_file.exists():
                safe = str(img_file.resolve()).replace("\\", "/")
                f.write(f"file '{safe}'\n")
                f.write(f"duration {durations[i]:.3f}\n")
        # FFmpeg concat needs last image repeated
        last_img = images_dir / f"scene_{scenes[-1]['id']:03d}.png"
        if last_img.exists():
            safe = str(last_img.resolve()).replace("\\", "/")
            f.write(f"file '{safe}'\n")

    # ── 5) FFmpeg 합성 ──
    output_path = final_dir / "output.mp4"

    # 비디오 필터
    vf = "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:black"

    if burn_subtitles:
        escaped_srt = _escape_srt_path(srt_path)
        sub_style = "FontSize=20,FontName=NanumGothic,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2,MarginV=30"
        vf += f",subtitles='{escaped_srt}':force_style='{sub_style}'"

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(img_list_file),
        "-i", str(merged_audio),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        str(output_path)
    ]

    console.print("  FFmpeg 합성 중...")
    console.print(f"  [dim]명령어: {' '.join(cmd[:8])}...[/dim]")

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

    if result.returncode != 0:
        # 자막 burn-in 실패 시 자막 없이 재시도
        console.print("[yellow]  자막 burn-in 실패, 자막 없이 합성 재시도...[/yellow]")
        console.print(f"  [dim]FFmpeg stderr: {result.stderr[-500:]}[/dim]")

        vf_nosub = "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:black"
        cmd_nosub = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", str(img_list_file),
            "-i", str(merged_audio),
            "-vf", vf_nosub,
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-shortest",
            str(output_path)
        ]
        result2 = subprocess.run(cmd_nosub, capture_output=True, text=True, timeout=600)
        if result2.returncode != 0:
            raise RuntimeError(f"FFmpeg 합성 실패:\n{result2.stderr[-1000:]}")
        console.print("[yellow]  ⚠ 자막 없이 영상 생성됨 (SRT 파일은 별도 첨부)[/yellow]")
    else:
        console.print("[green]  ✓ 자막 burn-in 성공[/green]")

    console.print(f"  [bold green]영상 완성: {output_path}[/bold green]")
    return output_path


# ── CLI 호환용 wrapper ──
def run(image_results, audio_results, script_data, project_dir, burn_subtitles=True):
    return compose_video(script_data, image_results, audio_results, project_dir, burn_subtitles)