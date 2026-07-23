/**
 * Tim 学习助手 - 错题列表批量选择与操作
 */
(function () {
    'use strict';

    const selectAll = document.getElementById('select-all');
    const toolbar = document.getElementById('batch-toolbar');
    const selCount = document.getElementById('sel-count');
    const batchDeleteBtn = document.getElementById('batch-delete-btn');
    const batchAction = document.getElementById('batch-action');
    const totalCount = document.getElementById('total-count');

    const rowChecks = document.querySelectorAll('.row-select');
    if (rowChecks.length > 0 && selectAll) {
        selectAll.style.display = '';
    }

    function getCheckedIds() {
        return Array.from(document.querySelectorAll('.row-select:checked')).map(cb => parseInt(cb.value, 10));
    }

    function updateToolbar() {
        const n = getCheckedIds().length;
        if (selCount) selCount.textContent = n;
        if (selectAll) selectAll.checked = (n > 0 && n === rowChecks.length);
        if (toolbar) toolbar.style.display = n > 0 ? '' : 'none';
        if (batchDeleteBtn) batchDeleteBtn.disabled = n === 0;
        if (batchAction) batchAction.disabled = n === 0;
    }

    if (selectAll) {
        selectAll.addEventListener('change', function () {
            document.querySelectorAll('.row-select').forEach(cb => { cb.checked = this.checked; });
            updateToolbar();
        });
    }

    document.querySelectorAll('.row-select').forEach(cb => {
        cb.addEventListener('change', updateToolbar);
    });

    // 批量操作下拉
    if (batchAction) {
        batchAction.addEventListener('change', function () {
            const ids = getCheckedIds();
            const val = this.value;
            if (!val || ids.length === 0) return;

            let action, value, confirmMsg;
            if (val.startsWith('status:')) {
                action = 'status';
                value = val.split(':')[1];
                const label = {'active':'活跃','mastered':'已掌握','archived':'已归档'}[value] || value;
                confirmMsg = '确定将选中的 ' + ids.length + ' 道题标记为「' + label + '」？';
            } else if (val === 'next_review_at') {
                action = 'next_review_at';
                value = new Date().toISOString().slice(0, 16);
                confirmMsg = '确定将选中的 ' + ids.length + ' 道题的复习时间设为今天？';
            } else {
                return;
            }

            if (!confirm(confirmMsg)) { this.value = ''; return; }

            this.disabled = true;
            fetch('/api/questions/batch-update', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ids: ids, action: action, value: value })
            })
            .then(res => res.json())
            .then(data => {
                this.value = '';
                this.disabled = false;
                if (data.success) {
                    alert('已更新 ' + data.updated + ' 道题');
                    location.reload();
                } else {
                    alert('操作失败: ' + (data.message || '未知错误'));
                }
            })
            .catch(err => {
                this.value = '';
                this.disabled = false;
                alert('网络错误: ' + err.message);
            });
        });
    }

    window.batchDelete = function () {
        const ids = getCheckedIds();
        if (ids.length === 0) { alert('请先勾选要删除的错题'); return; }
        if (!confirm('确定要删除选中的 ' + ids.length + ' 道错题吗？此操作不可恢复。')) return;

        const btn = batchDeleteBtn;
        if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> 删除中...'; }

        fetch('/api/questions/batch-delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ids: ids })
        })
        .then(res => res.json())
        .then(data => {
            if (btn) { btn.disabled = false; btn.innerHTML = '<i class="bi bi-trash"></i> 批量删除'; }
            if (data.success) {
                ids.forEach(qid => {
                    const cb = document.querySelector('.row-select[value="' + qid + '"]');
                    if (cb) { const tr = cb.closest('tr'); if (tr) tr.remove(); }
                });
                if (totalCount) totalCount.textContent = document.querySelectorAll('.row-select').length;
                updateToolbar();
                if (document.querySelectorAll('.row-select').length === 0 && selectAll) selectAll.style.display = 'none';
                alert('成功删除 ' + data.deleted + ' 道错题');
            } else {
                alert('删除失败: ' + (data.message || '未知错误'));
            }
        })
        .catch(err => {
            if (btn) { btn.disabled = false; btn.innerHTML = '<i class="bi bi-trash"></i> 批量删除'; }
            alert('网络错误: ' + err.message);
        });
    };

    updateToolbar();
})();
