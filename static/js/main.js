/**
 * Tim 学习助手 - 前端交互逻辑
 */

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

// ========== 复习卡片交互 ==========
function submitReview(mistakeId, result) {
    const timeSpent = document.getElementById('review-time-spent');
    const notes = document.getElementById('review-notes');

    fetch(`/api/review/${mistakeId}/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            result: result,
            time_spent: timeSpent ? parseInt(timeSpent.value) || 0 : 0,
            notes: notes ? notes.value : ''
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            // 显示结果
            const card = document.getElementById(`review-card-${mistakeId}`);
            if (card) {
                card.style.transition = 'transform 0.3s, opacity 0.3s';
                card.style.transform = 'translateX(100px)';
                card.style.opacity = '0';
                setTimeout(() => {
                    card.remove();
                    // 检查是否还有待复习的卡片
                    const remaining = document.querySelectorAll('.review-card-item');
                    if (remaining.length === 0) {
                        showReviewComplete();
                    }
                }, 300);
            }

            // 更新计数
            const reviewedBadge = document.getElementById('reviewed-count');
            const remainingBadge = document.getElementById('remaining-count');
            if (reviewedBadge) {
                reviewedBadge.textContent = parseInt(reviewedBadge.textContent) + 1;
            }
            if (remainingBadge) {
                const rem = parseInt(remainingBadge.textContent) - 1;
                remainingBadge.textContent = Math.max(0, rem);
            }
        } else {
            alert('提交失败: ' + (data.message || '未知错误'));
        }
    })
    .catch(err => {
        console.error('复习提交错误:', err);
        alert('网络错误，请重试');
    });
}

function showReviewComplete() {
    const container = document.getElementById('review-cards-container');
    if (container) {
        container.innerHTML = `
            <div class="text-center py-5">
                <i class="bi bi-check-circle-fill text-success" style="font-size: 4rem;"></i>
                <h3 class="mt-3">今日复习完成！</h3>
                <p class="text-muted">你已经完成了今天所有的复习任务，太棒了！</p>
                <a href="/" class="btn btn-primary mt-2">
                    <i class="bi bi-house-door"></i> 返回首页
                </a>
            </div>
        `;
    }
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
