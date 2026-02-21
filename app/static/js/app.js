/**
 * 딸깍 스튜디오 — 3단 레이아웃 프론트엔드
 */

// ═══════════════════════════════════════
// 전역 상태
// ═══════════════════════════════════════

const STATE = {
    projectId: null,
    title: '',
    scenes: [],
    selectedSceneIdx: 0,
    imageResults: [],
    audioResults: [],
    videoResults: [],
    itvPrompts: [],
    videoUrl: '',
    srtUrl: '',
};

// ═══════════════════════════════════════
// 탭 관리
// ═══════════════════════════════════════

function switchTab(name) {
    const btn = document.querySelector(`.nav-tab[data-tab="${name}"]`);
    if (btn && btn.disabled) return;

    document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));

    if (btn) btn.classList.add('active');
    const content = document.getElementById(`tab-${name}`);
    if (content) content.classList.add('active');

    if (name === 'images') initImageTab();
    if (name === 'audio') initAudioTab();
    if (name === 'video') initVideoTab();
    if (name === 'compose') initComposeTab();
}

function enableTab(name) {
    const btn = document.querySelector(`.nav-tab[data-tab="${name}"]`);
    if (btn) btn.disabled = false;
}

function markTabDone(name) {
    const btn = document.querySelector(`.nav-tab[data-tab="${name}"]`);
    if (btn) btn.classList.add('done');
}

// ═══════════════════════════════════════
// 유틸
// ═══════════════════════════════════════

function $(id) { return document.getElementById(id); }

function truncate(str, len) {
    if (!str) return '';
    return str.length > len ? str.substring(0, len) + '...' : str;
}

function copyText(id) {
    const el = $(id);
    navigator.clipboard.writeText(el.value || el.textContent);
    el.style.borderColor = 'var(--green)';
    setTimeout(() => { el.style.borderColor = ''; }, 1000);
}

function copyJSON() {
    const text = $('jsonPreview').textContent;
    navigator.clipboard.writeText(text);
}

function addLog(boxId, msg, cls) {
    const box = $(boxId);
    if (!box) return;
    const entry = document.createElement('div');
    entry.className = cls ? `log-${cls}` : '';
    const time = new Date().toLocaleTimeString('ko-KR');
    entry.textContent = `[${time}] ${msg}`;
    box.appendChild(entry);
    box.scrollTop = box.scrollHeight;
}

function getSelectedScene() {
    return STATE.scenes[STATE.selectedSceneIdx] || null;
}

// ═══════════════════════════════════════
// 사이드바 렌더링 (공용)
// ═══════════════════════════════════════

function renderSidebar(listId, countId, options = {}) {
    const list = $(listId);
    const count = $(countId);
    if (!list) return;

    list.innerHTML = '';
    if (count) count.textContent = STATE.scenes.length;

    STATE.scenes.forEach((scene, idx) => {
        const item = document.createElement('div');
        item.className = 'scene-sidebar-item' + (idx === STATE.selectedSceneIdx ? ' active' : '');

        const hasImg = STATE.imageResults.find(r => r.scene_id === scene.id && r.status === 'success');
        const hasAudio = STATE.audioResults.find(r => r.scene_id === scene.id && r.status === 'success');

        let thumbHtml = '';
        if (hasImg && STATE.projectId) {
            thumbHtml = `<img src="/api/project/${STATE.projectId}/image/${scene.id}?t=${Date.now()}" alt="">`;
        } else {
            thumbHtml = `<i class="fa-regular fa-image"></i>`;
        }

        let statusText = '';
        if (options.showAudioStatus) {
            statusText = hasAudio ? `${hasAudio.duration?.toFixed(1) || '?'}초` : '';
        } else if (options.showImageStatus) {
            statusText = hasImg ? '✓' : '';
        }

        let doneClass = '';
        if (options.showImageStatus && hasImg) doneClass = ' done';
        if (options.showAudioStatus && hasAudio) doneClass = ' done';

        item.className += doneClass;

        item.innerHTML = `
            <div class="scene-sidebar-thumb">${thumbHtml}</div>
            <div class="scene-sidebar-info">
                <div class="scene-sidebar-label">M${scene.id}</div>
                <div class="scene-sidebar-text">${truncate(scene.narration, 30)}</div>
            </div>
            <div class="scene-sidebar-status">${statusText}</div>
        `;

        item.onclick = () => {
            STATE.selectedSceneIdx = idx;
            renderSidebar(listId, countId, options);
            if (options.onSelect) options.onSelect(scene, idx);
        };

        list.appendChild(item);
    });
}

// ═══════════════════════════════════════
// 탭 1: 스토리 (대본)
// ═══════════════════════════════════════

async function generateScript() {
    const article = $('articleInput').value.trim();
    if (!article) { alert('기사를 입력해 주세요.'); return; }

    const btn = $('btnGenScript');
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 생성 중...';

    const logBox = $('scriptLogBox');
    logBox.innerHTML = '';
    addLog('scriptLogBox', '프로젝트 생성 중...', '');

    try {
        const createRes = await fetch('/api/project/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ article }),
        });
        const createData = await createRes.json();
        if (createData.error) throw new Error(createData.error);

        STATE.projectId = createData.project_id;
        $('projectBadge').textContent = STATE.projectId;
        addLog('scriptLogBox', `프로젝트: ${STATE.projectId}`, 'ok');

        const category = $('categorySelect').value;
        addLog('scriptLogBox', `대본 생성 중... (카테고리: ${category})`, '');

        const scriptRes = await fetch('/api/step1/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ project_id: STATE.projectId, category }),
        });
        const scriptData = await scriptRes.json();
        if (scriptData.error) throw new Error(scriptData.error);

        STATE.scenes = scriptData.scenes;
        STATE.title = scriptData.title;
        STATE.selectedSceneIdx = 0;

        addLog('scriptLogBox', `완료: "${STATE.title}" (${STATE.scenes.length}장면)`, 'ok');

        $('jsonPreview').textContent = JSON.stringify(
            { title: STATE.title, scenes: STATE.scenes }, null, 2
        );
        $('btnToProject').style.display = 'inline-flex';

        markTabDone('script');
        enableTab('images');

    } catch (e) {
        addLog('scriptLogBox', `오류: ${e.message}`, 'err');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> 스토리보드 생성';
    }
}

function loadScriptEditor() {
    $('scriptInputView').style.display = 'none';
    $('scriptEditView').style.display = 'flex';

    $('editTitle').value = STATE.title;
    renderScriptSidebar();
    selectSceneForEdit(0);
}

function renderScriptSidebar() {
    renderSidebar('sceneSidebarList', 'editSceneCount', {
        onSelect: (scene, idx) => selectSceneForEdit(idx),
    });
}

function selectSceneForEdit(idx) {
    STATE.selectedSceneIdx = idx;
    const scene = STATE.scenes[idx];
    if (!scene) return;

    $('editSceneBadge').textContent = `M${scene.id}`;
    $('editSceneTitle').textContent = truncate(scene.narration, 40);
    $('editNarration').value = scene.narration || '';
    $('editImagePrompt').value = scene.image_prompt || '';

    renderScriptSidebar();
}

function saveCurrentScene() {
    const scene = getSelectedScene();
    if (!scene) return;
    scene.narration = $('editNarration').value;
    scene.image_prompt = $('editImagePrompt').value;
    renderScriptSidebar();
}

function deleteCurrentScene() {
    if (STATE.scenes.length <= 1) { alert('최소 1개 장면이 필요합니다.'); return; }
    STATE.scenes.splice(STATE.selectedSceneIdx, 1);
    STATE.scenes.forEach((s, i) => s.id = i + 1);
    if (STATE.selectedSceneIdx >= STATE.scenes.length) {
        STATE.selectedSceneIdx = STATE.scenes.length - 1;
    }
    renderScriptSidebar();
    selectSceneForEdit(STATE.selectedSceneIdx);
}

function addScene() {
    const newId = STATE.scenes.length + 1;
    STATE.scenes.push({ id: newId, narration: '', image_prompt: '' });
    renderScriptSidebar();
    selectSceneForEdit(STATE.scenes.length - 1);
}

async function saveScriptAndNext() {
    saveCurrentScene();
    STATE.title = $('editTitle').value;

    const res = await fetch('/api/step1/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            project_id: STATE.projectId,
            title: STATE.title,
            scenes: STATE.scenes,
        }),
    });
    const data = await res.json();
    if (data.error) { alert(data.error); return; }

    enableTab('images');
    switchTab('images');
}

document.addEventListener('keydown', (e) => {
    if (e.ctrlKey && e.key === 'Enter') {
        const scriptTab = $('tab-script');
        if (scriptTab && scriptTab.classList.contains('active')) {
            if ($('scriptInputView').style.display !== 'none') {
                generateScript();
            }
        }
    }
});

// ═══════════════════════════════════════
// 탭 2: 이미지
// ═══════════════════════════════════════

function initImageTab() {
    renderSidebar('imgSidebarList', 'imgSceneCount', {
        showImageStatus: true,
        onSelect: (scene, idx) => selectImageScene(idx),
    });
    selectImageScene(STATE.selectedSceneIdx);
    updateImageCost();
    updateUngenCount();
}

function selectImageScene(idx) {
    STATE.selectedSceneIdx = idx;
    const scene = STATE.scenes[idx];
    if (!scene) return;

    $('imgSceneBadge').textContent = `M${scene.id}`;
    $('imgControlBadge').textContent = `M${scene.id}`;
    $('imgSceneTitle').textContent = truncate(scene.narration, 50);

    const area = $('imagePreviewArea');
    const result = STATE.imageResults.find(r => r.scene_id === scene.id && r.status === 'success');
    if (result && STATE.projectId) {
        area.innerHTML = `<img src="/api/project/${STATE.projectId}/image/${scene.id}?t=${Date.now()}" alt="장면 ${scene.id}">`;
    } else {
        area.innerHTML = `<div class="empty-state">
            <i class="fa-regular fa-image" style="font-size:3rem;opacity:0.3"></i>
            <p>미리보기 이미지가 없습니다</p>
        </div>`;
    }

    $('imgPromptEdit').value = scene.image_prompt || '';

    renderSidebar('imgSidebarList', 'imgSceneCount', {
        showImageStatus: true,
        onSelect: (s, i) => selectImageScene(i),
    });
}

function updateImageCost() {
    const sel = $('modelSelect');
    if (!sel) return;
    const match = sel.selectedOptions[0].textContent.match(/\$([0-9.]+)/);
    if (match) {
        const count = STATE.scenes.length || 30;
        const total = (parseFloat(match[1]) * count).toFixed(2);
    }
}

function updateUngenCount() {
    const ungen = STATE.scenes.filter(s =>
        !STATE.imageResults.find(r => r.scene_id === s.id && r.status === 'success')
    ).length;
    const el1 = $('imgUngenCount');
    if (el1) el1.textContent = ungen;
}

function togglePromptEdit() {
    const ta = $('imgPromptEdit');
    ta.style.display = ta.style.display === 'none' ? 'block' : 'none';
}

function generateImages() {
    const style = $('styleSelect').value;
    const model = $('modelSelect').value;
    const btn = $('btnBatchImages');
    btn.disabled = true;

    const section = $('imgProgressSection');
    const fill = $('imgProgressFill');
    const text = $('imgProgressText');
    section.style.display = 'block';

    const params = new URLSearchParams({
        project_id: STATE.projectId,
        style,
        image_model: model,
    });

    const es = new EventSource(`/api/step2/generate?${params}`);

    es.addEventListener('progress', (e) => {
        const d = JSON.parse(e.data);
        const pct = Math.round((d.current / d.total) * 100);
        fill.style.width = pct + '%';
        text.textContent = `${d.current}/${d.total}`;

        const resultObj = { scene_id: d.scene_id, status: d.status, path: d.image_path };
        const existing = STATE.imageResults.findIndex(r => r.scene_id === d.scene_id);
        if (existing >= 0) STATE.imageResults[existing] = resultObj;
        else STATE.imageResults.push(resultObj);

        renderSidebar('imgSidebarList', 'imgSceneCount', {
            showImageStatus: true,
            onSelect: (s, i) => selectImageScene(i),
        });

        const sel = getSelectedScene();
        if (sel && sel.id === d.scene_id) {
            selectImageScene(STATE.selectedSceneIdx);
        }
    });

    es.addEventListener('complete', (e) => {
        es.close();
        btn.disabled = false;
        markTabDone('images');
        enableTab('audio');
        updateUngenCount();
        initImageTab();
    });

    es.onerror = () => {
        es.close();
        btn.disabled = false;
    };
}

async function regenerateCurrentImage() {
    const scene = getSelectedScene();
    if (!scene) return;

    scene.image_prompt = $('imgPromptEdit').value;

    const btn = document.querySelector('#tab-images .control-panel .btn-primary');
    if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 생성 중...'; }

    try {
        const res = await fetch('/api/step2/regenerate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                project_id: STATE.projectId,
                scene,
                style: $('styleSelect').value,
                image_model: $('modelSelect').value,
            }),
        });
        const data = await res.json();
        if (data.error) throw new Error(data.error);

        const idx = STATE.imageResults.findIndex(r => r.scene_id === scene.id);
        if (idx >= 0) STATE.imageResults[idx] = data.result;
        else STATE.imageResults.push(data.result);

        selectImageScene(STATE.selectedSceneIdx);
        updateUngenCount();

    } catch (e) {
        alert('재생성 실패: ' + e.message);
    } finally {
        if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> 이미지 생성'; }
    }
}

function deleteCurrentImage() {
    const scene = getSelectedScene();
    if (!scene) return;
    STATE.imageResults = STATE.imageResults.filter(r => r.scene_id !== scene.id);
    selectImageScene(STATE.selectedSceneIdx);
    updateUngenCount();
}

function deleteAllImages() {
    if (!confirm('모든 이미지를 삭제할까요?')) return;
    STATE.imageResults = [];
    initImageTab();
}

function selectAllImages() {
    // placeholder
}

$('modelSelect')?.addEventListener('change', () => {
    updateImageCost();
    updateUngenCount();
});

// ═══════════════════════════════════════
// 탭 3: 오디오
// ═══════════════════════════════════════

function initAudioTab() {
    renderSidebar('audioSidebarList', 'audioSceneCount', {
        showAudioStatus: true,
        onSelect: (scene, idx) => selectAudioScene(idx),
    });
    selectAudioScene(STATE.selectedSceneIdx);
    updateAudioCounts();
}

function selectAudioScene(idx) {
    STATE.selectedSceneIdx = idx;
    const scene = STATE.scenes[idx];
    if (!scene) return;

    $('audioSceneBadge').textContent = `M${scene.id}`;
    $('audioSceneTitle').textContent = truncate(scene.narration, 50);
    $('audioNarrationPreview').textContent = scene.narration || '-';
    $('audioSelectedScene').textContent = `M${scene.id}`;

    const result = STATE.audioResults.find(r => r.scene_id === scene.id && r.status === 'success');
    const player = $('audioPreviewPlayer');
    if (result && STATE.projectId) {
        player.src = `/api/project/${STATE.projectId}/audio/${scene.id}`;
        $('audioDurationPreview').textContent = `${result.duration?.toFixed(1) || '?'}초`;
    } else {
        player.src = '';
        $('audioDurationPreview').textContent = '-';
    }

    renderSidebar('audioSidebarList', 'audioSceneCount', {
        showAudioStatus: true,
        onSelect: (s, i) => selectAudioScene(i),
    });
}

function updateAudioCounts() {
    const done = STATE.audioResults.filter(r => r.status === 'success').length;
    const total = STATE.scenes.length;
    const ungen = total - done;

    const el = $('audioTotalCount'); if (el) el.textContent = total;
    const el2 = $('audioDoneCount'); if (el2) el2.textContent = done;
    const el3 = $('audioProgressCount'); if (el3) el3.textContent = '0';
    const el4 = $('audioUngenCount'); if (el4) el4.textContent = ungen;
    const el5 = $('audioUngenCount2'); if (el5) el5.textContent = ungen;
}

async function generateSingleAudio() {
    const scene = getSelectedScene();
    if (!scene) return;
    alert('현재는 일괄 생성만 지원됩니다. "미생성 일괄" 버튼을 사용해 주세요.');
}

function generateAudio() {
    const voice = $('voiceSelect').value;
    const btn = $('btnBatchAudio');
    btn.disabled = true;

    const params = new URLSearchParams({
        project_id: STATE.projectId,
        voice,
    });

    const es = new EventSource(`/api/step3/generate?${params}`);

    es.addEventListener('progress', (e) => {
        const d = JSON.parse(e.data);

        const resultObj = { scene_id: d.scene_id, status: d.status, duration: d.duration || 0 };
        const idx = STATE.audioResults.findIndex(r => r.scene_id === d.scene_id);
        if (idx >= 0) STATE.audioResults[idx] = resultObj;
        else STATE.audioResults.push(resultObj);

        updateAudioCounts();

        renderSidebar('audioSidebarList', 'audioSceneCount', {
            showAudioStatus: true,
            onSelect: (s, i) => selectAudioScene(i),
        });

        const sel = getSelectedScene();
        if (sel && sel.id === d.scene_id) {
            selectAudioScene(STATE.selectedSceneIdx);
        }
    });

    es.addEventListener('complete', (e) => {
        es.close();
        btn.disabled = false;
        markTabDone('audio');
        enableTab('video');
        updateAudioCounts();
        initAudioTab();
    });

    es.onerror = () => {
        es.close();
        btn.disabled = false;
    };
}

function deleteAllAudio() {
    if (!confirm('모든 오디오를 삭제할까요?')) return;
    STATE.audioResults = [];
    initAudioTab();
}

// ═══════════════════════════════════════
// 탭 4: AI 비디오 생성
// ═══════════════════════════════════════

function initVideoTab() {
    renderSidebar('videoSidebarList', 'videoSceneCount', {
        showImageStatus: true,
        onSelect: (scene, idx) => {
            $('videoSceneBadge').textContent = `M${scene.id}`;
            $('videoSceneTitle').textContent = truncate(scene.narration, 50);

            const imgResult = STATE.imageResults.find(r => r.scene_id === scene.id && r.status === 'success');
            if (imgResult && STATE.projectId) {
                $('videoSourceImg').src = `/api/project/${STATE.projectId}/image/${scene.id}`;
                $('videoSourceImg').style.display = 'block';
            } else {
                $('videoSourceImg').style.display = 'none';
            }

            const vidResult = STATE.videoResults.find(r => r.scene_id === scene.id && r.status === 'success');
            if (vidResult) {
                $('videoResultArea').innerHTML = `<video controls src="/api/project/${STATE.projectId}/video/${scene.id}" style="width:100%;border-radius:var(--radius)"></video>`;
                $('videoStatusBadge').textContent = '완료';
                $('videoStatusBadge').style.background = 'var(--success)';
            } else {
                $('videoResultArea').innerHTML = '<div class="empty-state"><i class="fa-solid fa-film" style="font-size:2rem;opacity:0.3"></i><p>영상이 생성되면 여기에 표시됩니다</p></div>';
                $('videoStatusBadge').textContent = '대기';
                $('videoStatusBadge').style.background = 'var(--surface)';
            }

            const prompts = STATE.itvPrompts || [];
            $('videoPromptText').value = prompts[idx] || '';
        },
    });
    $('videoRangeEnd').value = Math.min(5, STATE.scenes.length);
    updateVideoProgress();
}

function updateVideoProgress() {
    const results = STATE.videoResults || [];
    const done = results.filter(r => r && r.status === 'success').length;
    const fail = results.filter(r => r && r.status === 'error').length;
    const pending = STATE.scenes.length - done - fail;
    if ($('videoDoneCount')) $('videoDoneCount').textContent = done;
    if ($('videoPendingCount')) $('videoPendingCount').textContent = pending;
    if ($('videoFailCount')) $('videoFailCount').textContent = fail;
}

async function autoGenerateItvPrompt() {
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
}

function copyItvPrompt() {
    const text = $('videoPromptText').value;
    navigator.clipboard.writeText(text);
}

async function generateAllItvPrompts() {
    try {
        const res = await fetch('/api/step4/prompts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ project_id: STATE.projectId })
        });
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        STATE.itvPrompts = data.prompts;
        alert(`ITV 프롬프트 ${data.prompts.length}개 생성 완료`);
    } catch (e) {
        alert('프롬프트 생성 실패: ' + e.message);
    }
}

async function exportItvPrompts() {
    const prompts = STATE.itvPrompts || [];
    if (prompts.length === 0) {
        alert('먼저 프롬프트를 생성하세요');
        return;
    }
    const blob = new Blob([JSON.stringify(prompts, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `itv_prompts_${STATE.projectId}.json`;
    a.click();
    URL.revokeObjectURL(url);
}

async function generateSingleVideo() {
    const idx = STATE.selectedSceneIdx;
    const scene = STATE.scenes[idx];
    if (!scene) return;

    const mode = $('videoModeSelect').value;
    const prompt = $('videoPromptText').value || `Cinematic scene: ${scene.narration.slice(0, 80)}`;
    const frames = parseInt($('videoFrameCount').value);

    $('btnVideoSingle').disabled = true;
    $('videoGenStatus').style.display = 'flex';
    $('videoGenStatusText').textContent = `M${scene.id} 생성 중...`;

    try {
        const res = await fetch('/api/step4/regenerate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                project_id: STATE.projectId,
                scene_id: scene.id,
                prompt: prompt,
                mode: mode,
                frame_count: frames
            })
        });
        const data = await res.json();
        if (data.error) throw new Error(data.error);

        const existing = STATE.videoResults.findIndex(r => r.scene_id === scene.id);
        if (existing >= 0) STATE.videoResults[existing] = data;
        else STATE.videoResults.push(data);

        $('videoResultArea').innerHTML = `<video controls src="/api/project/${STATE.projectId}/video/${scene.id}" style="width:100%;border-radius:var(--radius)"></video>`;
        $('videoStatusBadge').textContent = '완료';
        $('videoStatusBadge').style.background = 'var(--success)';
        updateVideoProgress();

    } catch (e) {
        alert('영상 생성 실패: ' + e.message);
    } finally {
        $('btnVideoSingle').disabled = false;
        $('videoGenStatus').style.display = 'none';
    }
}

function generateVideos() {
    const start = parseInt($('videoRangeStart').value);
    const end = parseInt($('videoRangeEnd').value);
    const mode = $('videoModeSelect').value;
    const frames = parseInt($('videoFrameCount').value);

    $('btnVideoGen').disabled = true;
    $('videoGenStatus').style.display = 'flex';

    const evtSource = new EventSource(
        `/api/step4/generate?project_id=${STATE.projectId}&mode=${mode}&start=${start}&end=${end}&frame_count=${frames}`
    );

    evtSource.addEventListener('progress', (e) => {
        const d = JSON.parse(e.data);
        $('videoGenStatusText').textContent = `M${d.scene_id} 처리 중... (${d.current}/${d.total})`;

        const existing = STATE.videoResults.findIndex(r => r.scene_id === d.scene_id);
        const resultObj = { status: d.status, scene_id: d.scene_id };
        if (existing >= 0) STATE.videoResults[existing] = resultObj;
        else STATE.videoResults.push(resultObj);

        updateVideoProgress();
    });

    evtSource.addEventListener('complete', (e) => {
        evtSource.close();
        const d = JSON.parse(e.data);
        $('btnVideoGen').disabled = false;
        $('videoGenStatus').style.display = 'none';
        alert(`비디오 생성 완료: ${d.success}개 성공, ${d.failed}개 실패`);

        if (d.failed === 0) {
            markTabDone('video');
            enableTab('compose');
        }
        updateVideoProgress();
    });

    evtSource.addEventListener('error', (e) => {
        if (e.data) {
            alert('에러: ' + e.data);
        }
        evtSource.close();
        $('btnVideoGen').disabled = false;
        $('videoGenStatus').style.display = 'none';
    });
}

async function uploadSceneVideo() {
    const fileInput = $('videoUploadFile');
    if (!fileInput.files.length) {
        alert('파일을 선택하세요');
        return;
    }

    const idx = STATE.selectedSceneIdx;
    const scene = STATE.scenes[idx];
    const formData = new FormData();
    formData.append('video', fileInput.files[0]);
    formData.append('project_id', STATE.projectId);
    formData.append('scene_id', scene.id);

    try {
        const res = await fetch('/api/step4/upload', {
            method: 'POST',
            body: formData
        });
        const data = await res.json();
        if (data.error) throw new Error(data.error);

        const existing = STATE.videoResults.findIndex(r => r.scene_id === scene.id);
        const resultObj = { status: 'success', scene_id: scene.id, path: data.path };
        if (existing >= 0) STATE.videoResults[existing] = resultObj;
        else STATE.videoResults.push(resultObj);

        $('videoResultArea').innerHTML = `<video controls src="/api/project/${STATE.projectId}/video/${scene.id}" style="width:100%;border-radius:var(--radius)"></video>`;
        $('videoStatusBadge').textContent = '완료';
        updateVideoProgress();
        alert('업로드 완료!');
    } catch (e) {
        alert('업로드 실패: ' + e.message);
    }
}

// ═══════════════════════════════════════
// 탭 5: 합성 (FFmpeg)
// ═══════════════════════════════════════

function initComposeTab() {
    renderSidebar('composeSidebarList', 'composeSceneCount', {
        showImageStatus: true,
        showAudioStatus: true,
        onSelect: (scene, idx) => {
            $('composeSceneBadge').textContent = `M${scene.id}`;
            $('composeSceneTitle').textContent = truncate(scene.narration, 50);
        },
    });
}

async function composeVideo() {
    const btn = $('btnCompose');
    btn.disabled = true;
    $('composeStatus').style.display = 'flex';

    const burnSubs = $('burnSubsSelect').value === 'true';

    try {
        const res = await fetch('/api/step5/compose', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                project_id: STATE.projectId,
                burn_subs: burnSubs,
            }),
        });
        const data = await res.json();
        if (data.error) throw new Error(data.error);

        STATE.videoUrl = data.video_url;
        STATE.srtUrl = data.srt_url;

        $('composePreview').innerHTML = `<video controls src="${data.video_url}" style="width:100%;border-radius:var(--radius)"></video>`;
        $('composeDownloads').style.display = 'block';
        $('dlVideoCompose').href = data.video_url;
        $('dlSrtCompose').href = data.srt_url;

        $('previewVideo').src = data.video_url;

        markTabDone('compose');
        enableTab('preview');
        enableTab('meta');

    } catch (e) {
        alert('합성 오류: ' + e.message);
    } finally {
        btn.disabled = false;
        $('composeStatus').style.display = 'none';
    }
}

// ═══════════════════════════════════════
// 탭 6: 프리뷰 (자막 설정)
// ═══════════════════════════════════════

['subSize', 'subY', 'subX', 'subOpacity'].forEach(id => {
    const el = $(id);
    if (el) {
        el.addEventListener('input', () => {
            const valEl = $(id + 'Val');
            if (valEl) valEl.textContent = el.value;
        });
    }
});

['subTextColor', 'subBgColor'].forEach(id => {
    const el = $(id);
    if (el) {
        el.addEventListener('input', () => {
            const valEl = $(id + 'Val');
            if (valEl) valEl.textContent = el.value;
        });
    }
});

// ═══════════════════════════════════════
// 탭 7: 메타데이터 & 썸네일
// ═══════════════════════════════════════

async function generateMeta() {
    const btn = $('btnMeta');
    btn.disabled = true;
    $('metaStatus').style.display = 'flex';

    try {
        const res = await fetch('/api/step6/metadata', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ project_id: STATE.projectId }),
        });
        const data = await res.json();
        if (data.error) throw new Error(data.error);

        const meta = data.metadata;

        if (data.thumbnail_url) {
            $('metaThumb').src = data.thumbnail_url;
            $('dlThumb').href = data.thumbnail_url;
            $('metaThumbCard').style.display = 'block';
        }

        const titleList = $('metaTitles');
        titleList.innerHTML = '';
        (meta.titles || []).forEach(t => {
            const li = document.createElement('li');
            li.textContent = t;
            li.onclick = () => {
                navigator.clipboard.writeText(t);
                li.style.borderColor = 'var(--green)';
                setTimeout(() => li.style.borderColor = '', 1000);
            };
            titleList.appendChild(li);
        });

        const tagCloud = $('metaHashtags');
        tagCloud.innerHTML = '';
        (meta.hashtags || []).forEach(tag => {
            const span = document.createElement('span');
            span.textContent = tag;
            span.onclick = () => navigator.clipboard.writeText(tag);
            tagCloud.appendChild(span);
        });

        $('metaDesc').value = meta.description || '';

        if ($('dlVideoFinal')) $('dlVideoFinal').href = STATE.videoUrl;
        if ($('dlSrtFinal')) $('dlSrtFinal').href = STATE.srtUrl;

        $('metaResult').style.display = 'block';
        markTabDone('meta');

    } catch (e) {
        alert('메타 오류: ' + e.message);
    } finally {
        btn.disabled = false;
        $('metaStatus').style.display = 'none';
    }
}

// ═══════════════════════════════════════
// 프로젝트 불러오기 (Resume)
// ═══════════════════════════════════════

async function loadProjectList() {
    const res = await fetch('/api/projects');
    const data = await res.json();
    const projects = data.projects || [];

    if (projects.length === 0) {
        alert('저장된 프로젝트가 없습니다.');
        return;
    }

    let msg = '프로젝트 선택 (번호 입력):\n\n';
    projects.forEach((p, i) => {
        const steps = p.steps_done.join(', ');
        msg += `${i + 1}. [${p.project_id}] ${p.title.slice(0, 30)}... (${steps})\n`;
    });

    const choice = prompt(msg);
    if (!choice) return;

    const idx = parseInt(choice) - 1;
    if (isNaN(idx) || idx < 0 || idx >= projects.length) {
        alert('잘못된 번호');
        return;
    }

    await resumeProject(projects[idx].project_id);
}

async function resumeProject(projectId) {
    const res = await fetch(`/api/project/${projectId}`);
    const data = await res.json();

    if (data.error) {
        alert('불러오기 실패: ' + data.error);
        return;
    }

    STATE.projectId = data.project_id;

    if (data.script) {
        STATE.scenes = data.script.scenes || [];
        STATE.title = data.script.title || '';
    }
    if (data.image_results) STATE.imageResults = data.image_results;
    if (data.audio_results) STATE.audioResults = data.audio_results;
    if (data.video_results) STATE.videoResults = data.video_results;

    const steps = data.steps || {};
    if (steps.script === 'done') {
        enableTab('images');
        markTabDone('script');
    }
    if (steps.images === 'done') {
        enableTab('audio');
        markTabDone('images');
    }
    if (steps.audio === 'done') {
        enableTab('video');
        markTabDone('audio');
    }
    if (steps.video === 'done') {
        enableTab('compose');
        markTabDone('video');
    }
    if (steps.compose === 'done') {
        enableTab('preview');
        enableTab('meta');
        markTabDone('compose');
        if (data.video_url) STATE.videoUrl = data.video_url;
        if (data.srt_url) STATE.srtUrl = data.srt_url;
    }
    if (steps.metadata === 'done') {
        enableTab('meta');
        markTabDone('meta');
    }

    if (typeof renderSidebar === 'function') renderSidebar();

    switchTab('script');
    if (typeof loadScriptEditor === 'function') loadScriptEditor();

    alert(`프로젝트 불러옴: ${STATE.scenes.length}씬\n${STATE.title}`);
}
