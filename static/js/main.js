/**
 * Tim 学习助手 - 前端交互逻辑
 */

// 全局 fetch 拦截 — 自动显示/隐藏 loading
(function() {
    var _fetch = window.fetch;
    var pending = 0;
    window.fetch = function(url, opts) {
        opts = opts || {};
        var method = (opts.method || 'GET').toUpperCase();
        if (['POST', 'PUT', 'DELETE', 'PATCH'].includes(method)) {
            pending++;
            var loader = document.getElementById('global-loading');
            if (loader) loader.style.display = 'flex';
        }
        return _fetch.call(window, url, opts).finally(function() {
            if (['POST', 'PUT', 'DELETE', 'PATCH'].includes(method)) {
                pending--;
                if (pending <= 0) {
                    pending = 0;
                    var loader = document.getElementById('global-loading');
                    if (loader) loader.style.display = 'none';
                }
            }
        });
    };
})();

document.addEventListener('DOMContentLoaded', function () {
    // 初始化所有功能
    initDeleteConfirm();
    initImagePreview();
    initAutoDismissAlerts();
    initReviewTimer();
    initSearchFilter();
});

// ========== 删除确认 ==========
function initDeleteConfirm() {
    document.querySelectorAll('[data-confirm]').forEach(btn => {
        btn.addEventListener('click', function (e) {
            const message = this.getAttribute('data-confirm') || '确定要执行此操作吗？';
            if (!confirm(message)) {
                e.preventDefault();
            }
        });
    });
}

// ========== 图片上传预览 ==========
function initImagePreview() {
    const imageInputs = document.querySelectorAll('.image-upload-input');
    imageInputs.forEach(input => {
        input.addEventListener('change', function () {
            const container = this.closest('.image-upload-area').querySelector('.image-preview-container');
            if (!container) return;

            const files = Array.from(this.files);
            files.forEach(file => {
                if (!file.type.startsWith('image/')) return;

                const reader = new FileReader();
                reader.onload = function (e) {
                    const item = document.createElement('div');
                    item.className = 'image-preview-item';
                    item.innerHTML = `
                        <img src="${e.target.result}" alt="${file.name}">
                        <span class="delete-btn" title="移除">&times;</span>
                    `;
                    item.querySelector('.delete-btn').addEventListener('click', function () {
                        item.remove();
                    });
                    container.appendChild(item);
                };
                reader.readAsDataURL(file);
            });
        });
    });
}

// ========== 自动关闭提示 ==========
function initAutoDismissAlerts() {
    document.querySelectorAll('.alert-dismissible').forEach(alert => {
        setTimeout(() => {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 4000);
    });
}

// ========== 复习计时器 ==========
function initReviewTimer() {
    const reviewForm = document.getElementById('review-form');
    if (!reviewForm) return;

    let startTime = Date.now();

    reviewForm.addEventListener('submit', function () {
        const timeSpent = Math.round((Date.now() - startTime) / 1000);
        const timeInput = document.getElementById('review-time-spent');
        if (timeInput) {
            timeInput.value = timeSpent;
        }
    });

    // 重置计时器（切换到下一题时）
    document.addEventListener('review-next', function () {
        startTime = Date.now();
    });
}

// ========== 搜索过滤 ==========
function initSearchFilter() {
    const searchInput = document.getElementById('keyword-search');
    if (!searchInput) return;

    let debounceTimer;
    searchInput.addEventListener('input', function () {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            const form = this.closest('form');
            if (form) form.submit();
        }, 500);
    });
}

// ========== 图片删除（在编辑页面） ==========
function deleteQuestionImage(questionId, imageId) {
    if (!confirm('确定要删除这张图片吗？')) return;

    fetch(`/api/questions/${questionId}/image/${imageId}/delete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            const imgElement = document.getElementById(`image-${imageId}`);
            if (imgElement) imgElement.remove();
        } else {
            alert('删除失败');
        }
    })
    .catch(err => {
        console.error('删除图片错误:', err);
        alert('网络错误');
    });
}

// ========== 显示/隐藏答案（复习模式） ==========
function toggleAnswer(mistakeId) {
    const answerEl = document.getElementById(`answer-${mistakeId}`);
    if (answerEl) {
        if (answerEl.style.display === 'none' || answerEl.style.display === '') {
            answerEl.style.display = 'block';
            document.getElementById(`toggle-btn-${mistakeId}`).textContent = '隐藏答案';
        } else {
            answerEl.style.display = 'none';
            document.getElementById(`toggle-btn-${mistakeId}`).textContent = '显示答案';
        }
    }
}
