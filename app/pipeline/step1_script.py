"""STEP 1: 대본 생성"""
from google import genai
from app import config
from app.pipeline.utils import extract_json_from_text


def load_system_prompt() -> str:
    with open(config.PROMPTS_DIR / "script_system.txt", "r", encoding="utf-8") as f:
        return f.read()


def generate_script(article: str, category: str = "경제") -> dict:
    client = genai.Client(api_key=config.GEMINI_API_KEY)

    response = client.models.generate_content(
        model=config.SCRIPT_MODEL,
        contents=f"## 카테고리: {category}\n\n## 뉴스 기사 원문:\n{article}\n\n위 기사를 유튜브 영상 대본으로 만들어 주세요.",
        config=genai.types.GenerateContentConfig(
            system_instruction=load_system_prompt(),
            temperature=config.SCRIPT_TEMPERATURE,
        ),
    )

    script_data = extract_json_from_text(response.text)
    if "scenes" not in script_data:
        raise ValueError("대본에 scenes가 없습니다.")
    return script_data