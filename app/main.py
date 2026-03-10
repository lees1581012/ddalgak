"""FastAPI 앱 생성"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.config import OUTPUT_DIR

app = FastAPI(title="딸깍 - 유튜브 영상 자동 제작")

# 정적 파일
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
app.mount("/output", StaticFiles(directory=OUTPUT_DIR), name="output")

# 라우트 등록
from app.routes import router
app.include_router(router)