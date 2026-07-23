/**
 * Tim 学习助手 - 文档导入前端（PDF / DOCX 上传/轮询）
 * 结果渲染与保存共享逻辑见 ocr_result.js
 */

let selectedFile = null;
let currentTaskId = null;
let pollTimer = null;

// ========== 初始化 ==========
document.addEventListener('DOMContentLoaded', function () {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');

    if (dropZone) {
        dropZone.addEventListener('dragover', function (e) {
            e.preventDefault();
            dropZone.classList.add('drag-over');
        });
        dropZone.addEventListener('dragleave', function () {
            dropZone.classList.remove('drag-over');
        });
        dropZone.addEventListener('drop', function (e) {
            e.preventDefault();
            dropZone.classList.remove('drag-over');
            if (e.dataTransfer.files.length > 0) {
                handleFile(e.dataTransfer.files[0]);
            }
        });
        dropZone.addEventListener('click', function (e) {
            if (e.target.tagName !== 'BUTTON' && fileInput) {
                fileInput.click();
            }
        });
    }

    if (fileInput) {
        fileInput.addEventListener('change', function () {
            if (this.files.length > 0) {
                handleFile(this.files[0]);
            }
        });
    }
});

// ========== 文件处理 ==========
function handleFile(file) {
    const ext = file.name.split('.').pop().toLowerCase();
    if (ext !== 'pdf' && ext !== 'docx') {
        alert('仅支持 PDF 和 DOCX 格式');
        return;
    }
    selectedFile = file;

    const preview = document.getElementById('file-preview');
    const filename = document.getElementById('preview-filename');
    if (preview) preview.style.display = 'block';
    if (filename) filename.textContent = file.name + ' (' + (file.size / 1024).toFixed(0) + ' KB)';

    const btn = document.getElementById('start-btn');
    if (btn) btn.disabled = false;
}

function clearFile() {
    selectedFile = null;
    const fi = document.getElementById('file-input');
    if (fi) fi.value = '';
    const preview = document.getElementById('file-preview');
    if (preview) preview.style.display = 'none';
    const btn = document.getElementById('start-btn');
    if (btn) btn.disabled = true;
}

// ========== 导入流程 ==========
function startDocImport() {
    if (!selectedFile) return;

    document.getElementById('upload-section').style.display = 'none';
    document.getElementById('result-section').style.display = 'none';
    document.getElementById('error-section').style.display = 'none';
    document.getElementById('progress-section').style.display = 'block';

    document.querySelectorAll('.progress-step').forEach(s => s.classList.remove('active', 'done'));
    document.querySelectorAll('.progress-line').forEach(l => l.classList.remove('done'));
    document.getElementById('progress-bar').style.width = '0%';
    document.getElementById('progress-message').textContent = '正在上传文档...';

    const formData = new FormData();
    formData.append('doc', selectedFile);

    fetch('/api/doc/upload', { method: 'POST', body: formData })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                currentTaskId = data.task_id;
                document.getElementById('progress-message').textContent = data.message;
                startPolling();
            } else {
                showError(data.error || '上传失败');
            }
        })
        .catch(err => { showError('网络错误: ' + err.message); });
}

function startPolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(function () {
        fetch('/api/doc/status/' + currentTaskId)
            .then(res => res.json())
            .then(data => {
                updateProgress(data);
                if (data.status === 'done') {
                    clearInterval(pollTimer);
                    pollTimer = null;
                    showResult(data);
                } else if (data.status === 'error') {
                    clearInterval(pollTimer);
                    pollTimer = null;
                    showError(data.error || '解析失败');
                }
            })
            .catch(err => {
                clearInterval(pollTimer);
                pollTimer = null;
                showError('查询状态失败: ' + err.message);
            });
    }, 1000);
}

function updateProgress(data) {
    const stages = ['preprocess', 'ocr', 'parse', 'done'];
    const stageIndex = stages.indexOf(data.stage);
    document.querySelectorAll('.progress-step').forEach((step, i) => {
        step.classList.remove('active', 'done');
        if (i < stageIndex) step.classList.add('done');
        if (i === stageIndex && data.status !== 'done') step.classList.add('active');
        if (data.status === 'done') step.classList.add('done');
    });
    document.querySelectorAll('.progress-line').forEach((line, i) => {
        line.classList.toggle('done', i < stageIndex);
    });
    document.getElementById('progress-bar').style.width = data.progress + '%';
    document.getElementById('progress-message').textContent = data.message;
}

// ========== 错误处理与重试 ==========
function showError(message) {
    document.getElementById('progress-section').style.display = 'none';
    document.getElementById('result-section').style.display = 'none';
    document.getElementById('error-section').style.display = 'block';
    document.getElementById('error-message').textContent = message;
}

function retryImport() {
    document.getElementById('error-section').style.display = 'none';
    document.getElementById('result-section').style.display = 'none';
    document.getElementById('upload-section').style.display = 'block';
    document.getElementById('progress-section').style.display = 'none';
    clearFile();
}

function resetToUpload() {
    retryImport();
}
