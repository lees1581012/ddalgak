"""기존 프로젝트에서 특정 단계부터 재실행"""
import json
from pathlib import Path
from app.pipeline import step4_compose, step5_metadata
from app.pipeline.utils import load_json, save_json

# ★ 여기에 기존 프로젝트 폴더명 입력 ★
PROJECT_ID = "20260219_153929"

project_dir = Path("output") / PROJECT_ID

# 기존 데이터 로드
script_data = load_json(project_dir / "script.json")
image_results = load_json(project_dir / "image_results.json")
audio_results = load_json(project_dir / "audio_results.json")

print(f"프로젝트: {PROJECT_ID}")
print(f"장면 수: {len(script_data['scenes'])}")
print(f"이미지: {sum(1 for r in image_results if r['status']=='success')}장")
print(f"오디오: {sum(1 for r in audio_results if r['status']=='success')}개")

# ── STEP 4: 영상 합성 ──
print("\n▶ STEP 4: 영상 합성 시작...")
output_video = step4_compose.compose_video(
    image_results, audio_results, script_data,
    project_dir, burn_subtitles=True
)
print(f"✓ 완료: {output_video}")

# ── STEP 5: 메타데이터 ──
print("\n▶ STEP 5: 메타데이터 생성...")
metadata = step5_metadata.generate_metadata(script_data)
save_json(metadata, project_dir / "final" / "metadata.json")
print(f"✓ 제목 추천:")
for t in metadata.get("titles", []):
    print(f"  - {t}")

# 썸네일은 선택
try:
    print("\n▶ 썸네일 생성...")
    step5_metadata.generate_thumbnail(script_data, project_dir)
    print("✓ 썸네일 완료")
except Exception as e:
    print(f"⚠ 썸네일 실패 (무시): {e}")

print(f"\n🎬 완료! 영상: {output_video}")
