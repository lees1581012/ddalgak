#!/usr/bin/env python3
"""
step5_compose.py - 이미지/비디오 + 오디오 + 자막 → MP4
비디오가 있는 씬은 mp4 사용, 없으면 이미지 슬라이드쇼
"""
import json
import subprocess
import shutil
from pathlib import Path
from rich.console import Console

console = Console()


def _escape_srt_path(path: Path) -> str:
    s = str(path.resolve()).replace("\\", "/")
    s = s.replace(":", "\\:")
    return s


def _get_duration(file_path: Path) -> float:
    cmd = [
        "ffprobe", "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "csv=p=0",
        str(file_path)
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return float(result.stdout.strip())
    except Exception:
        return 5.0


def compose_video(
    script_data: dict,
    image_results: dict,
    audio_results: dict,
    project_dir: Path,
    burn_subtitles: bool = True,
) -> Path:
    scenes = script_data["scenes"]
    images_dir = project_dir / "images"
    videos_dir = project_dir / "videos"
    audio_dir = project_dir / "audio"
    final_dir = project_dir / "final"
    final_dir.mkdir(parents=True, exist_ok=True)

    # video_results.json 로드
    vr_path = project_dir / "video_results.json"
    video_map = {}
    if vr_path.exists():
        vr_data = json.load(open(vr_path, encoding="utf-8"))
        for r in vr_data:
            if r.get("status") == "success" and r.get("video_path"):
                vp = Path(r["video_path"])
                if vp.exists():
                    video_map[r["scene_id"]] = vp

    console.print(f"  비디오 있는 씬: {list(video_map.keys())} / 전체 {len(scenes)}씬")

    # 1) 각 씬 오디오 duration
    durations = []
    for scene in scenes:
        audio_file = audio_dir / f"scene_{scene['id']:03d}.mp3"
        if audio_file.exists():
            dur = _get_duration(audio_file)
        else:
            dur = 5.0
        durations.append(max(dur, 1.0))

    # 2) 오디오 concat
    audio_list_file = project_dir / "audio_concat.txt"
    with open(audio_list_file, "w", encoding="utf-8") as f:
        for scene in scenes:
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

    # 3) SRT 자막
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
            f.write(f"{i+1}\n{fmt(start)} --> {fmt(end)}\n{scene['narration']}\n\n")
            current_time = end

    # 4) 각 씬별 비디오 클립 생성 (temp)
    temp_dir = project_dir / "temp_clips"
    temp_dir.mkdir(parents=True, exist_ok=True)
    clip_paths = []

    for i, scene in enumerate(scenes):
        sid = scene["id"]
        clip_path = temp_dir / f"clip_{sid:03d}.mp4"
        audio_file = audio_dir / f"scene_{sid:03d}.mp3"
        dur = durations[i]

        if sid in video_map:
            # 비디오 있는 씬: 비디오를 오디오 길이에 맞게 조정
            video_src = video_map[sid]
            video_dur = _get_duration(video_src)

            if video_dur >= dur:
                # 비디오가 더 길면 자르기
                cmd = [
                    "ffmpeg", "-y",
                    "-i", str(video_src),
                    "-t", f"{dur:.3f}",
                    "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:black",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                    "-an", "-pix_fmt", "yuv420p",
                    str(clip_path)
                ]
            else:
                # 비디오가 짧으면 마지막 프레임 정지 (freeze)
                cmd = [
                    "ffmpeg", "-y",
                    "-i", str(video_src),
                    "-vf", f"tpad=stop_mode=clone:stop_duration={dur - video_dur:.3f},scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:black",
                    "-t", f"{dur:.3f}",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                    "-an", "-pix_fmt", "yuv420p",
                    str(clip_path)
                ]
        else:
            # 이미지 슬라이드쇼
            img_file = images_dir / f"scene_{sid:03d}.png"
            if not img_file.exists():
                # 이미지가 없으면 검은 화면 플레이스홀더 사용
                console.print(f"  [yellow]씬 {sid}: 이미지 없음, 검은 화면 사용[/yellow]")
                # 검은 화면 생성 (무한 루프 + -t로 길이 제한)
                cmd = [
                    "ffmpeg", "-y",
                    "-f", "lavfi", "-i", "color=c=black:s=1280x720:r=30",
                    "-t", f"{dur:.3f}",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                    "-an", "-pix_fmt", "yuv420p",
                    str(clip_path)
                ]
            else:
                cmd = [
                    "ffmpeg", "-y",
                    "-loop", "1", "-i", str(img_file),
                    "-t", f"{dur:.3f}",
                    "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:black",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                    "-an", "-pix_fmt", "yuv420p", "-r", "30",
                    str(clip_path)
                ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            clip_paths.append(clip_path)
            src_type = "video" if sid in video_map else "image"
            console.print(f"  씬 {sid}: {src_type} 클립 생성 ({dur:.1f}s)")
        else:
            console.print(f"  [red]씬 {sid}: 클립 생성 실패[/red]")
            console.print(f"  [dim]{result.stderr[-300:]}[/dim]")

    # 5) 클립 concat
    clip_list_file = project_dir / "clip_concat.txt"
    with open(clip_list_file, "w", encoding="utf-8") as f:
        for cp in clip_paths:
            safe = str(cp.resolve()).replace("\\", "/")
            f.write(f"file '{safe}'\n")

    merged_video = project_dir / "merged_video.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(clip_list_file),
        "-c", "copy",
        str(merged_video)
    ], capture_output=True, timeout=300)

    # 6) 비디오 + 오디오 + 자막 합성
    output_path = final_dir / "output.mp4"
    vf = ""
    if burn_subtitles:
        escaped_srt = _escape_srt_path(srt_path)
        sub_style = "FontSize=20,FontName=NanumGothic,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2,MarginV=30"
        vf = f"subtitles='{escaped_srt}':force_style='{sub_style}'"

    cmd_final = [
        "ffmpeg", "-y",
        "-i", str(merged_video),
        "-i", str(merged_audio),
    ]
    if vf:
        cmd_final += ["-vf", vf]
    cmd_final += [
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        str(output_path)
    ]

    console.print("  최종 합성 중...")
    result = subprocess.run(cmd_final, capture_output=True, text=True, timeout=600)

    if result.returncode != 0:
        console.print("[yellow]  자막 burn-in 실패, 자막 없이 재시도...[/yellow]")
        cmd_nosub = [
            "ffmpeg", "-y",
            "-i", str(merged_video),
            "-i", str(merged_audio),
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            str(output_path)
        ]
        result2 = subprocess.run(cmd_nosub, capture_output=True, text=True, timeout=600)
        if result2.returncode != 0:
            raise RuntimeError(f"FFmpeg 합성 실패:\n{result2.stderr[-1000:]}")

    # temp 정리 (일단 보존)
    # shutil.rmtree(temp_dir, ignore_errors=True)

    console.print(f"  [bold green]영상 완성: {output_path}[/bold green]")
    return output_path


def run(image_results, audio_results, script_data, project_dir, burn_subtitles=True):
    return compose_video(script_data, image_results, audio_results, project_dir, burn_subtitles)
