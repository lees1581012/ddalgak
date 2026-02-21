"""app.js의 autoGenerateItvPrompt를 API 호출로 변경"""

OLD = """async function autoGenerateItvPrompt() {
    const idx = STATE.selectedSceneIdx;
    const scene = STATE.scenes[idx];
    if (!scene) return;
    const prompt = `Camera slowly zooms in. ${scene.narration.slice(0, 100)}`;
    $('videoPromptText').value = prompt;
    if (!STATE.itvPrompts) STATE.itvPrompts = [];
    STATE.itvPrompts[idx] = prompt;
}"""

NEW = """async function autoGenerateItvPrompt() {
    const idx = STATE.selectedSceneIdx;
    const scene = STATE.scenes[idx];
    if (!scene) return;
    $('videoPromptText').value = 'AI 생성 중...';
    try {
        const res = await fetch('/api/step4/single-prompt', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                project_id: STATE.projectId,
                scene_id: scene.id || (idx + 1),
                narration: scene.narration || ''
            })
        });
        const data = await res.json();
        $('videoPromptText').value = data.prompt;
        if (!STATE.itvPrompts) STATE.itvPrompts = [];
        STATE.itvPrompts[idx] = data.prompt;
    } catch (e) {
        $('videoPromptText').value = 'Slow cinematic zoom in with gentle lighting';
    }
}"""

with open('app/static/js/app.js', 'r', encoding='utf-8') as f:
    content = f.read()

if OLD in content:
    content = content.replace(OLD, NEW)
    with open('app/static/js/app.js', 'w', encoding='utf-8', newline='\n') as f:
        f.write(content)
    print("Done! autoGenerateItvPrompt 교체 완료")
else:
    print("OLD 패턴을 찾을 수 없음 - 수동 확인 필요")