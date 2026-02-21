"""routes.py에 single-prompt 엔드포인트 추가"""

ENDPOINT = '''
@router.post("/api/step4/single-prompt")
async def step4_single_prompt(body: dict = Body(...)):
    """단일 씬 ITV 프롬프트 생성 (Gemini + 이미지)"""
    project_id = body["project_id"]
    scene_id = body["scene_id"]
    narration = body.get("narration", "")
    project_dir = config.OUTPUT_DIR / project_id
    image_path = project_dir / "images" / f"scene_{scene_id:03d}.png"

    try:
        from google import genai
        client = genai.Client(api_key=config.GEMINI_API_KEY)
        parts = []
        if image_path.exists():
            img_bytes = image_path.read_bytes()
            parts.append(genai.types.Part.from_bytes(data=img_bytes, mime_type="image/png"))

        system_msg = (
            "You are a cinematic video director. Given this image and narration, "
            "write a SHORT English prompt (max 150 chars) describing camera movement "
            "and visual motion for an image-to-video AI.\\n\\n"
            f"Narration: {narration}\\n\\n"
            "Focus on: camera movement (pan, zoom, dolly, tilt), subject motion, lighting changes.\\n"
            "Do NOT describe the image content - only describe HOW it should move.\\n"
            "Reply with ONLY the motion prompt, nothing else."
        )
        parts.append(system_msg)

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=parts,
        )
        prompt = response.text.strip().strip('"')
        return JSONResponse({"prompt": prompt})
    except Exception as e:
        return JSONResponse({"prompt": "Slow cinematic zoom in with gentle lighting", "error": str(e)})

'''

with open('app/routes.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 296줄(인덱스 295) 앞에 삽입 - @router.post("/api/step4/prompts") 앞
insert_at = None
for i, line in enumerate(lines):
    if '@router.post("/api/step4/prompts")' in line:
        insert_at = i
        break

if insert_at is None:
    print("삽입 위치를 찾을 수 없음!")
else:
    before = lines[:insert_at]
    after = lines[insert_at:]
    with open('app/routes.py', 'w', encoding='utf-8', newline='\n') as f:
        f.writelines(before)
        f.write(ENDPOINT)
        f.writelines(after)
    print(f"Done! 삽입 위치: {insert_at + 1}줄")