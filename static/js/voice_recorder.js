/**
 * 语音笔记录音器 - Web Audio API + MediaRecorder
 */
let mediaRecorder = null;
let audioChunks = [];

async function toggleRecord() {
    const btn = document.getElementById('record-btn');
    const status = document.getElementById('record-status');
    const questionId = window.location.pathname.split('/').filter(Boolean).pop();

    if (mediaRecorder && mediaRecorder.state === 'recording') {
        mediaRecorder.stop();
        btn.classList.remove('btn-danger');
        btn.classList.add('btn-secondary');
        btn.querySelector('i').classList.replace('bi-stop-fill', 'bi-mic-fill');
        status.textContent = '正在保存...';
        return;
    }

    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];

        mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
        mediaRecorder.onstop = async () => {
            const blob = new Blob(audioChunks, { type: 'audio/webm' });
            const reader = new FileReader();
            reader.onloadend = async () => {
                const b64 = reader.result.split(',')[1];
                await fetch('/api/questions/' + questionId + '/voice', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ voice: b64 })
                });
                location.reload();
            };
            reader.readAsDataURL(blob);
            stream.getTracks().forEach(t => t.stop());
        };

        mediaRecorder.start();
        btn.querySelector('i').classList.replace('bi-mic-fill', 'bi-stop-fill');
        status.textContent = '录音中...';
    } catch (e) {
        alert('无法访问麦克风：' + e.message);
    }
}

async function deleteVoice(questionId) {
    if (!confirm('确定删除语音笔记？')) return;
    await fetch('/api/questions/' + questionId + '/voice', { method: 'DELETE' });
    location.reload();
}
