/**
 * 딸깍 - 프론트엔드
 */

// ── 예상 비용 계산 ──
const modelSelect = document.getElementById('modelSelect');
const costEstimate = document.getElementById('costEstimate');

function updateCost() {
    const opt = modelSelect.selectedOptions[0];
    // 옵션 텍스트에서 가격 추출
    const match = opt.textContent.match(/\$([0-9.]+)/);
    if (match) {
        const perImage = parseFloat(match[1]);
        const total = (perImage * 30).toFixed(2);
        costEstimate.textContent = `예상 비용: ~$${total} (30장 기준) | 장당 $${perImage}`;
    }
}
modelSelect.addEventListener('change', updateCost);
updateCost();


// ── 파이프라인 실행 ──
function startPipeline() {
    const article = document.getElementById('articleInput').value.trim();
    if (!article) {
        alert('뉴스 기사를 입력해 주세요.');
        return;
    }

    const params = new URLSearchParams({
        article: article,
        category: document.getElementById('categorySelect').value,
        style: document.getElementById('styleSelect').value,
        image_model: modelSelect.value,
        voice: document.getElementById('voiceSelect').value,
        burn_subs: document.getElementById('burnSubsSelect').value,
    });

    // UI 전환
    document.getElementById('inputPanel').style.display = 'none';
    document.getElementById('progressPanel').style.display = 'block';
    document.getElementById('resultPanel').style.display = 'none';
    document.getElementById('startBtn').disabled = true;

    // 상태 초기화
    ['script','images','tts','compose','metadata'].forEach(s => {
        setStepState(s, 'waiting');
        document.getElementById(`status-${s}`).textContent = '대기 중';
    });
    document.getElementById('logBox').innerHTML = '';

    // SSE 연결
    const evtSource = new EventSource(`/api/run?${params.toString()}`);

    evtSource.addEventListener('progress', (e) => {
        const d = JSON.parse(e.data);
        handleProgress(d);
    });

    evtSource.addEventListener('complete', (e) => {
        const d = JSON.parse(e.data);
        evtSource.close();
        showResult(d);
    });

    evtSource.addEventListener('error', (e) => {
        // SSE 에러 이벤트 (서버에서 보낸 것)
        if (e.data) {
            const d = JSON.parse(e.data);
            addLog(`❌ 오류: ${d.message}`, 'err');
        }
        evtSource.close();
        document.getElementById('startBtn').disabled = false;
    });

    evtSource.onerror = () => {
        // 연결 자체 에러
        evtSource.close();
        document.getElementById('startBtn').disabled = false;
    };
}


// ── 진행 상황 처리 ──
function handleProgress(d) {
    const { step, status, message, data } = d;

    if (status === 'running') {
        setStepState(step, 'running');
        document.getElementById(`status-${step}`).textContent = message;

        // 프로그레스 바 업데이트
        if (data && data.total && (step === 'images' || step === 'tts')) {
            const barEl = document.getElementById(`bar-${step}`);
            const fillEl = document.getElementById(`fill-${step}`);
            barEl.style.display = 'block';
            const pct = Math.round((data.current / data.total) * 100);
            fillEl.style.width = pct + '%';
        }
    }
    else if (status === 'done') {
        setStepState(step, 'done');
        document.getElementById(`status-${step}`).textContent = message;
    }
    else if (status === 'ok') {
        // init 같은 일반 메시지
    }

    addLog(message, status === 'done' ? 'ok' : '');
}


function setStepState(step, state) {
    const el = document.getElementById(`step-${step}`);
    if (!el) return;
    el.className = `step ${state}`;
}


function addLog(msg, cls = '') {
    const box = document.getElementById('logBox');
    const entry = document.createElement('div');
    entry.className = `log-entry ${cls ? 'log-' + cls : ''}`;
    const time = new Date().toLocaleTimeString('ko-KR');
    entry.textContent = `[${time}] ${msg}`;
    box.appendChild(entry);
    box.scrollTop = box.scrollHeight;
}


// ── 결과 표시 ──
function showResult(d) {
    document.getElementById('progressPanel').style.display = 'none';
    document.getElementById('resultPanel').style.display = 'block';

    // 영상
    const video = document.getElementById('resultVideo');
    video.src = d.video_url;

    // 썸네일
    document.getElementById('resultThumb').src = d.thumbnail_url;

    // 제목
    const titleList = document.getElementById('resultTitles');
    titleList.innerHTML = '';
    (d.metadata.titles || []).forEach(t => {
        const li = document.createElement('li');
        li.textContent = t;
        li.onclick = () => { navigator.clipboard.writeText(t); li.style.borderColor = '#10b981'; };
        titleList.appendChild(li);
    });

    // 해시태그
    const tagCloud = document.getElementById('resultHashtags');
    tagCloud.innerHTML = '';
    (d.metadata.hashtags || []).forEach(tag => {
        const span = document.createElement('span');
        span.textContent = tag;
        span.onclick = () => navigator.clipboard.writeText(tag);
        tagCloud.appendChild(span);
    });

    // 설명란
    document.getElementById('resultDesc').value = d.metadata.description || '';

    // 다운로드 링크
    document.getElementById('dlVideo').href = d.video_url;
    document.getElementById('dlThumb').href = d.thumbnail_url;
    document.getElementById('dlSrt').href = d.srt_url;

    document.getElementById('startBtn').disabled = false;
}


// ── 유틸 ──
function copyText(id) {
    const el = document.getElementById(id);
    navigator.clipboard.writeText(el.value);
    el.style.borderColor = '#10b981';
    setTimeout(() => { el.style.borderColor = ''; }, 1000);
}

function resetAll() {
    document.getElementById('inputPanel').style.display = 'block';
    document.getElementById('progressPanel').style.display = 'none';
    document.getElementById('resultPanel').style.display = 'none';
    document.getElementById('startBtn').disabled = false;
}