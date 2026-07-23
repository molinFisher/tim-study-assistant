/**
 * Tim 学习助手 - 复习卡片交互
 */
let reviewStartTime2 = Date.now();
let currentMistakeId2 = null;

document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.review-card-item').forEach(card => {
        card.addEventListener('click', function() {
            currentMistakeId2 = this.id.replace('review-card-', '');
            reviewStartTime2 = Date.now();
        });
    });
});

function submitReview(mistakeId, result) {
    const timeSpent = Math.round((Date.now() - reviewStartTime2) / 1000);
    const notesEl = document.getElementById('review-notes-' + mistakeId);
    const notes = notesEl ? notesEl.value : '';

    fetch('/api/review/' + mistakeId + '/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ result: result, time_spent: timeSpent, notes: notes })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            const card = document.getElementById('review-card-' + mistakeId);
            if (card) {
                card.style.transition = 'transform 0.4s ease, opacity 0.4s ease';
                card.style.transform = 'translateX(120px)';
                card.style.opacity = '0';
                setTimeout(() => {
                    card.remove();
                    if (document.querySelectorAll('.review-card-item').length === 0) showReviewComplete();
                }, 400);
            }
            const rb = document.getElementById('reviewed-count');
            const rm = document.getElementById('remaining-count');
            if (rb) rb.textContent = parseInt(rb.textContent) + 1;
            if (rm) rm.textContent = Math.max(0, parseInt(rm.textContent) - 1);
            reviewStartTime2 = Date.now();
        } else {
            alert('提交失败: ' + (data.message || '未知错误'));
        }
    })
    .catch(err => { console.error('复习提交错误:', err); alert('网络错误'); });
}

function showReviewComplete() {
    fetch('/api/review/today-stats').then(r=>r.json()).then(s=>{
        var c = document.getElementById('review-cards-container');
        if (c) c.innerHTML = '<div class="text-center py-5"><i class="bi bi-trophy-fill text-warning" style="font-size:4rem;"></i><h3 class="mt-3">🎉 今日复习完成！</h3><p class="text-muted">今日复习 '+s.total+' 题，正确率 '+s.rate+'%，🔥 连击 '+s.streak+' 天</p><div class="mt-3"><a href="/" class="btn btn-primary me-2"><i class="bi bi-house-door"></i> 返回首页</a><a href="/statistics" class="btn btn-outline-success"><i class="bi bi-bar-chart"></i> 查看统计</a></div></div>';
    });
}

function toggleAnswer(mistakeId) {
    const el = document.getElementById('answer-' + mistakeId);
    const btn = document.getElementById('toggle-btn-' + mistakeId);
    if (el) {
        const show = el.style.display === 'none' || el.style.display === '';
        el.style.display = show ? 'block' : 'none';
        if (btn) btn.innerHTML = show ? '<i class="bi bi-eye-slash"></i> 隐藏答案' : '<i class="bi bi-eye"></i> 显示答案';
    }
}

function addAllToReview() {
    if (!confirm('将把所有未排期的活跃错题及已过期的错题加入今日复习，确定吗？')) return;
    fetch('/api/review/add-all', { method: 'POST' })
        .then(res => res.json())
        .then(data => {
            if (data.success) { alert(data.message); location.reload(); }
            else { alert('操作失败: ' + (data.message || data.error)); }
        })
        .catch(err => alert('网络错误: ' + err.message));
}
