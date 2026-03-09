"""怨듯넻 ?좏떥由ы떚"""
import json
import re
import time
from pathlib import Path


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def generate_project_id() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def save_json(data, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def extract_json_from_text(text: str) -> dict:
    """AI 응답에서 JSON 추출 (자동 복구 포함)"""
    # 1) ```json ... ``` 블록 추출
    pattern = r"```json\s*(.*?)\s*```"
    match = re.search(pattern, text, re.DOTALL)
    raw = match.group(1) if match else text.strip()

    # 2) JSON 시작점 찾기
    start = -1
    for i, c in enumerate(raw):
        if c in ("{", "["):
            start = i
            break
    if start == -1:
        raise ValueError("AI 응답에서 JSON을 찾을 수 없습니다.")
    raw = raw[start:]

    # 3) 그대로 파싱 시도
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # 4) 흔한 오류 자동 수정
    fixed = raw
    fixed = re.sub(r",\s*}", "}", fixed)       # trailing comma before }
    fixed = re.sub(r",\s*\]", "]", fixed)      # trailing comma before ]
    fixed = re.sub(r"(?<!\\)\\(?![\"\\\/bfnrtu])", r"\\\\", fixed)  # bad escapes
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass

    # 5) 잘린 JSON 복구 - 괄호 균형 맞추기
    brace_open = 0  # {
    bracket_open = 0  # [
    for c in fixed:
        if c == "{": brace_open += 1
        elif c == "}": brace_open -= 1
        elif c == "[": bracket_open += 1
        elif c == "]": bracket_open -= 1

    # 필요한 닫는 괄호 추가
    if brace_open > 0 or bracket_open > 0:
        fixed = fixed.rstrip().rstrip(",")
        # 배열부터 닫기 (중첩 구조 고려)
        fixed += "]" * bracket_open
        fixed += "}" * brace_open
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            pass

    raise ValueError(f"JSON 파싱 실패. 원본 앞 200자: {raw[:200]}")



def format_time_srt(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
