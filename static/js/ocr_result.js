/**
 * Tim 学习助手 - OCR/文档导入结果共享渲染与保存
 * 由 ocr_import.js 与 doc_import.js 共同引用。
 */

// ---------- 常量 ----------
const OCR_SUBJECTS = ['数学', '物理', '道法', '语文'];
const OCR_DIFFICULTIES = [
    { value: 1, label: '1 - 非常简单' },
    { value: 2, label: '2 - 较简单' },
    { value: 3, label: '3 - 中等' },
    { value: 4, label: '4 - 较难' },
    { value: 5, label: '5 - 很难' },
];

// ---------- 工具 ----------
function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function getConfidenceClass(confidence) {
    if (confidence >= 0.7) return 'confidence-high';
    if (confidence >= 0.4) return 'confidence-medium';
    return 'confidence-low';
}

// ---------- 结果展示 ----------
function showResult(data) {
    const progressSection = document.getElementById('progress-section');
    const resultSection = document.getElementById('result-section');
    if (progressSection) progressSection.style.display = 'none';
    if (resultSection) resultSection.style.display = 'block';

    const questions = data.questions || [];
    const container = document.getElementById('question-cards-container');
    const countEl = document.getElementById('question-count');
    const rawTextEl = document.getElementById('raw-ocr-text');

    if (countEl) countEl.textContent = questions.length;
    if (rawTextEl) rawTextEl.textContent = data.raw_ocr_text || '(无)';

    if (!container) return;

    if (questions.length === 0) {
        container.innerHTML = '<div class="alert alert-warning">未能从文档中识别出题目，请确认文件内容包含文字或尝试其他文件。</div>';
        return;
    }

    container.innerHTML = '';
    questions.forEach((q, i) => {
        container.appendChild(buildQuestionCard(q, i));
    });
}

function buildQuestionCard(q, index) {
    const conf = q.confidence || 0;
    const confPct = Math.round(conf * 100);
    const fc = q.field_confidences || {};
    const formulaFixed = fc.formula_fixed ? '<span class="badge bg-info ms-1" title="已对数学公式进行智能修复">公式已优化</span>' : '';
    const confLabel = confPct >= 70 ? '高置信' : (confPct >= 40 ? '中等' : '偏低');

    const subjectOptions = OCR_SUBJECTS.map(s =>
        '<option value="' + s + '" ' + (s === q.xueke ? 'selected' : '') + '>' + s + '</option>'
    ).join('');

    const difficulty = q.difficulty || 3;
    const difficultyOptions = OCR_DIFFICULTIES.map(d =>
        '<option value="' + d.value + '" ' + (d.value === difficulty ? 'selected' : '') + '>' + d.label + '</option>'
    ).join('');

    const card = document.createElement('div');
    card.className = 'question-card card mb-3';
    card.dataset.qindex = index;
    card.innerHTML =
        '<div class="card-header d-flex justify-content-between align-items-center flex-wrap gap-2">' +
            '<div class="d-flex align-items-center gap-2">' +
                '<input type="checkbox" class="form-check-input q-select" checked aria-label="选择此题">' +
                '<span class="fw-bold">第 ' + (index + 1) + ' 题</span>' +
                '<span class="badge ' + getConfidenceClass(conf) + '">识别 ' + confLabel + ' ' + confPct + '%</span>' +
                formulaFixed +
            '</div>' +
            '<button type="button" class="btn btn-outline-danger btn-sm" onclick="removeQuestionCard(this)">' +
                '<i class="bi bi-trash"></i> 删除' +
            '</button>' +
        '</div>' +
        '<div class="card-body">' +
            '<div class="row g-2 mb-2">' +
                '<div class="col-6 col-md-4">' +
                    '<label class="form-label small mb-1">学科</label>' +
                    '<select class="form-select form-select-sm q-field q-xueke ocr-field">' + subjectOptions + '</select>' +
                '</div>' +
                '<div class="col-6 col-md-4">' +
                    '<label class="form-label small mb-1">难度</label>' +
                    '<select class="form-select form-select-sm q-field q-difficulty">' + difficultyOptions + '</select>' +
                '</div>' +
                '<div class="col-12 col-md-4 d-flex align-items-end">' +
                    '<span class="form-text text-muted small">识别结果可逐项修改，确认无误后保存</span>' +
                '</div>' +
            '</div>' +
            '<div class="mb-2">' +
                '<label class="form-label small mb-1">题目</label>' +
                '<textarea class="form-control form-control-sm q-field q-timu ocr-field" rows="3" placeholder="题目内容">' + escapeHtml(q.timu) + '</textarea>' +
            '</div>' +
            '<div class="row g-2 mb-2">' +
                '<div class="col-md-6">' +
                    '<label class="form-label small mb-1">学生答案</label>' +
                    '<textarea class="form-control form-control-sm q-field q-xueshengdaan ocr-field" rows="2" placeholder="学生答案">' + escapeHtml(q.xueshengdaan) + '</textarea>' +
                '</div>' +
                '<div class="col-md-6">' +
                    '<label class="form-label small mb-1">正确答案</label>' +
                    '<textarea class="form-control form-control-sm q-field q-zhengquedaan ocr-field" rows="2" placeholder="正确答案">' + escapeHtml(q.zhengquedaan) + '</textarea>' +
                '</div>' +
            '</div>' +
            '<div class="row g-2">' +
                '<div class="col-md-6">' +
                    '<label class="form-label small mb-1">错误分析</label>' +
                    '<textarea class="form-control form-control-sm q-field q-cuowufenxi ocr-field" rows="2" placeholder="错误分析">' + escapeHtml(q.cuowufenxi) + '</textarea>' +
                '</div>' +
                '<div class="col-md-6">' +
                    '<label class="form-label small mb-1">知识点</label>' +
                    '<textarea class="form-control form-control-sm q-field q-zhishidian ocr-field" rows="2" placeholder="知识点">' + escapeHtml(q.zhishidian) + '</textarea>' +
                '</div>' +
            '</div>' +
        '</div>';
    return card;
}

function removeQuestionCard(btn) {
    const card = btn.closest('.question-card');
    if (card) card.remove();
    const remaining = document.querySelectorAll('.question-card').length;
    const countEl = document.getElementById('question-count');
    if (countEl) countEl.textContent = remaining;
}

// ---------- 收集与保存 ----------
function collectQuestionData(card) {
    return {
        xueke: (card.querySelector('.q-xueke').value || '').trim(),
        timu: (card.querySelector('.q-timu').value || '').trim(),
        xueshengdaan: (card.querySelector('.q-xueshengdaan').value || '').trim(),
        zhengquedaan: (card.querySelector('.q-zhengquedaan').value || '').trim(),
        cuowufenxi: (card.querySelector('.q-cuowufenxi').value || '').trim(),
        zhishidian: (card.querySelector('.q-zhishidian').value || '').trim(),
        difficulty: parseInt(card.querySelector('.q-difficulty').value || '3', 10),
    };
}

function getCardsForSave(selectedOnly) {
    const cards = document.querySelectorAll('.question-card');
    const result = [];
    cards.forEach(card => {
        const isChecked = card.querySelector('.q-select').checked;
        if (selectedOnly && !isChecked) return;
        result.push(card);
    });
    return result;
}

function saveSelectedQuestions() {
    const cards = getCardsForSave(true);
    submitBatch(cards, '保存选中');
}

function saveAllQuestions() {
    const cards = getCardsForSave(false);
    submitBatch(cards, '保存全部');
}

function submitBatch(cards, label) {
    if (cards.length === 0) {
        alert('没有可保存的题目，请先勾选题目或重新导入。');
        return;
    }

    const questions = [];
    cards.forEach(card => {
        const d = collectQuestionData(card);
        if (!d.xueke || !d.timu) return;
        questions.push(d);
    });

    if (questions.length === 0) {
        alert('所选题目的「学科」或「题目」为空，请补全后再保存。');
        return;
    }

    const btn = event && event.target ? event.target : null;
    if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> 保存中...'; }

    fetch('/api/ocr/save-batch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ questions: questions })
    })
    .then(res => res.json())
    .then(data => {
        if (btn) { btn.disabled = false; btn.innerHTML = label === '保存选中' ? '<i class="bi bi-check-all"></i> 保存选中' : '<i class="bi bi-save"></i> 保存全部'; }
        if (data.success) {
            let msg = '成功保存 ' + data.saved_count + ' 道题！';
            if (data.errors && data.errors.length > 0) {
                msg += '（' + data.errors.length + ' 道因内容不完整被跳过）';
            }
            showSaveSuccess(msg, data.saved_count);
        } else {
            alert('保存失败: ' + (data.error || '未知错误'));
        }
    })
    .catch(err => {
        if (btn) { btn.disabled = false; btn.innerHTML = label === '保存选中' ? '<i class="bi bi-check-all"></i> 保存选中' : '<i class="bi bi-save"></i> 保存全部'; }
        alert('网络错误: ' + err.message);
    });
}

function showSaveSuccess(message, count) {
    const container = document.getElementById('question-cards-container');
    const countEl = document.getElementById('question-count');
    if (countEl) countEl.textContent = '0';
    container.innerHTML =
        '<div class="alert alert-success d-flex flex-column align-items-start gap-2" role="alert">' +
            '<div><i class="bi bi-check-circle-fill me-2"></i><strong>' + escapeHtml(message) + '</strong></div>' +
            '<div class="d-flex gap-2">' +
                '<a href="/questions" class="btn btn-success btn-sm"><i class="bi bi-collection"></i> 查看错题本</a>' +
                '<button class="btn btn-outline-secondary btn-sm" onclick="resetToUpload()"><i class="bi bi-plus-circle"></i> 再导入一批</button>' +
            '</div>' +
        '</div>';
}

function toggleRawText() {
    const el = document.getElementById('raw-ocr-text');
    if (el) {
        el.style.display = el.style.display === 'none' ? '' : 'none';
    }
}
