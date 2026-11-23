import { chip, empty, formError, heading, icon } from '../components/common/ui.js';
import { DECISION } from '../constants/enums.js';
import { store } from '../stores/workspace.js';
import { esc, points, pValue, timestamp } from '../utils/format.js';

export function reviewPage(run) {
  const { study, user } = store;
  const head = heading('付印审批', '印前会签', '展陈主管对固定的样本与运行结果签署发布或退回复测意见。');
  const available = study?.runs.filter(row => row.status === 'succeeded') || [];
  if (!run) return head + empty('暂无可会签的运行', '请先在复验分析中完成计算，或等待主管发布结论。');
  const stale = run.revision !== run.current_revision;
  const existingPublication = available.some(row => row.decision === 'publish' && row.revision === run.revision);
  const canPublish = run.result.complete > 0 && !existingPublication;
  return `${head}<div class="review-grid"><section class="sheet review-proof"><div class="section-title"><h2>会签依据</h2>${chip(`样本 R${run.revision}`)}</div>
    <label>复验运行<select id="review-select">${available.map(row => `<option value="${row.id}" ${row.id === run.id ? 'selected' : ''}>复验 #${row.id} · R${row.revision} · ${row.confidence}% 区间</option>`).join('')}</select></label>
    <dl class="facts"><div><dt>完整 / 缺失配对</dt><dd>${run.result.complete} / ${run.result.missing}</dd></div><div><dt>成功率变化（百分点）</dt><dd class="mono">${points(run.result.delta_pp)}</dd></div><div><dt>双侧精确 p 值</dt><dd class="mono">${pValue(run.result.p_value)}</dd></div></dl><a class="button" href="#result/${run.id}">查看分析详情 ${icon('arrow')}</a></section>
    <section class="sheet signoff"><div class="section-title"><h2>主管意见</h2>${chip(DECISION[run.decision] || '待会签', run.decision === 'publish' ? 'green' : 'amber')}</div>
    ${run.decision ? `<blockquote>${esc(run.note)}</blockquote><p class="signature">${esc(run.signed_by)} · ${timestamp(run.signed_at)}</p><div class="actions"><button data-download="json" data-run="${run.id}">${icon('export')} 导出会签结论</button></div>`
    : stale ? `<p class="warning">当前样本为 R${run.current_revision}，请重新运行后再会签。</p>`
    : user.role === 'curator' ? `<form data-form="review" data-run="${run.id}"><label>会签意见<textarea name="note" required minlength="6" maxlength="500" rows="5" placeholder="说明付印范围，或记录复测所需改动"></textarea></label>${formError}
      ${canPublish ? '' : `<p class="muted">${existingPublication ? '当前样本修订已有发布结论。' : '没有完整配对，仅可退回复测。'}</p>`}<div class="form-actions"><button type="submit" value="revise">退回复测</button><button type="submit" class="primary" value="publish" ${canPublish ? '' : 'disabled'}>签署并发布</button></div></form>`
    : '<p class="muted">等待展陈主管签署。</p>'}</section></div>`;
}
