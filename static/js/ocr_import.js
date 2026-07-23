/**
 * Tim 学习助手 - OCR 图片导入前端（上传/拖拽/轮询）
 * 结果渲染与保存共享逻辑见 ocr_result.js
 */

let selectedFiles = [];
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
            handleFiles(e.dataTransfer.files);
        });
        dropZone.addEventListener('click', function (e) {
            if (e.target.tagName !== 'BUTTON' && fileInput) {
                fileInput.click();
            }
        });
    }

    if (fileInput) {
        fileInput.addEventListener('change', function () {
            handleFiles(this.files);
        });
    }
});

// ========== 文件处理 ==========
function handleFiles(files) {
    const validFiles = [];
    for (const file of files) {
        if (file.type.startsWith('image/')) {
            validFiles.push(file);
        }
    }
    if (validFiles.length === 0) {
        alert('请选择有效的图片文件（PNG、JPG）');
        return;
    }
    selectedFiles = validFiles;
    updatePreview();
    updateStartButton();
}

function updatePreview() {
    const container = document.getElementById('preview-container');
    const grid = document.getElementById('image-preview-grid');
    const count = document.getElementById('preview-count');
    if (!container) return;
    container.innerHTML = '';
    if (count) count.textContent = selectedFiles.length;
    selectedFiles.forEach((file, index) => {
        const reader = new FileReader();
        reader.onload = function (e) {
            const item = document.createElement('div');
            item.className = 'ocr-preview-item';
            item.innerHTML =
                '<img src="' + e.target.result + '" alt="' + file.name + '">' +
                '<span class="remove-btn" onclick="removeImage(' + index + ')">&times;</span>';
            container.appendChild(item);
        };
        reader.readAsDataURL(file);
    });
    if (grid) grid.style.display = selectedFiles.length > 0 ? 'block' : 'none';
}

function removeImage(index) {
    selectedFiles.splice(index, 1);
    updatePreview();
    updateStartButton();
}

function clearImages() {
    selectedFiles = [];
    const fi = document.getElementById('file-input');
    if (fi) fi.value = '';
    updatePreview();
    updateStartButton();
    const grid = document.getElementById('image-preview-grid');
    if (grid) grid.style.display = 'none';
}

function updateStartButton() {
    const btn = document.getElementById('start-ocr-btn');
    if (btn) btn.disabled = selectedFiles.length === 0;
}

// ========== OCR 识别流程 ==========
function startOCR() {
    if (selectedFiles.length === 0) return;

    document.getElementById('upload-section').style.display = 'none';
    document.getElementById('result-section').style.display = 'none';
    document.getElementById('error-section').style.display = 'none';
    document.getElementById('progress-section').style.display = 'block';

    document.querySelectorAll('.progress-step').forEach(s => s.classList.remove('active', 'done'));
    document.querySelectorAll('.progress-line').forEach(l => l.classList.remove('done'));
    document.getElementById('progress-bar').style.width = '0%';
    document.getElementById('progress-message').textContent = '正在上传图片...';

    const formData = new FormData();
    selectedFiles.forEach(file => formData.append('images', file));

    fetch('/api/ocr/upload', { method: 'POST', body: formData })
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
        fetch('/api/ocr/status/' + currentTaskId)
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
                    showError(data.error || '识别失败');
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
        if (data.status === 'done' || (data.status === 'done' && i <= stageIndex)) step.classList.add('done');
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

function retryOCR() {
    document.getElementById('error-section').style.display = 'none';
    document.getElementById('result-section').style.display = 'none';
    document.getElementById('upload-section').style.display = 'block';
    document.getElementById('progress-section').style.display = 'none';
}

function resetToUpload() {
    document.getElementById('result-section').style.display = 'none';
    document.getElementById('error-section').style.display = 'none';
    document.getElementById('progress-section').style.display = 'none';
    document.getElementById('upload-section').style.display = 'block';
    clearImages();
}
