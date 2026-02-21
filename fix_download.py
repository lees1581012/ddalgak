"""_download_output을 ComfyUI output 폴더에서 직접 가져오도록 수정"""

with open('app/pipeline/step4_video.py', 'r', encoding='utf-8') as f:
    content = f.read()

old = '''def _download_output(prompt_id: str, history_data: dict, output_dir: Path, 
                     scene_id: int) -> Optional[Path]:
    """ComfyUI 히스토리에서 생성된 비디오 다운로드"""
    outputs = history_data.get(prompt_id, {}).get("outputs", {})

    for node_id, node_out in outputs.items():
        # video, videos, gifs 키 모두 확인
        for key in ("video", "videos", "gifs"):
            if key in node_out:
                for item in node_out[key]:
                    filename = item.get("filename", "")
                    subfolder = item.get("subfolder", "")
                    url = f"{COMFYUI_URL}/view?filename={filename}"
                    if subfolder:
                        url += f"&subfolder={subfolder}"

                    resp = urllib.request.urlopen(url)
                    video_data = resp.read()

                    ext = Path(filename).suffix or ".mp4"
                    final_path = output_dir / f"scene_{scene_id:03d}{ext}"
                    final_path.write_bytes(video_data)
                    return final_path

    logger.warning(f"씬 {scene_id}: ComfyUI 출력에서 비디오를 찾을 수 없음")
    return None'''

new = '''def _download_output(prompt_id: str, history_data: dict, output_dir: Path, 
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
    return None'''

if old in content:
    content = content.replace(old, new)
    with open('app/pipeline/step4_video.py', 'w', encoding='utf-8', newline='\n') as f:
        f.write(content)
    print("Done! _download_output 교체 완료")
else:
    print("매칭 실패 - 현재 _download_output 확인 필요")
    import re
    match = re.search(r'def _download_output.*?return None', content, re.DOTALL)
    if match:
        print(f"위치: {content[:match.start()].count(chr(10))+1}줄")
        print("내용 앞 200자:", match.group()[:200])