import { chip, empty, formError, heading } from '../components/common/ui.js';
import { store } from '../stores/workspace.js';
import { esc, pValue, timestamp } from '../utils/format.js';

const STATUS = {
  ready: ['可评估', 'green'], enrolling: ['等待入组', 'amber'], blocked: ['配对未齐', 'amber'],
  evaluated: ['已评估', ''], unfunded: ['额度不足', 'amber'],
};
const ACTIONS = {
  no_plan: ['未登记计划', 'amber'], unlocked: ['待锁定', 'amber'], wait: ['继续等待', 'amber'],
  continue: ['继续入组', ''], stop: ['建议提前收样', 'green'], finish: ['可以收样', 'green'],
  budget: ['额度已用完', 'amber'], complete: ['各看点已评估', ''],
};

const level = value => value == null ? '—' : `${(value * 100).toFixed(3)}%`;

function planForm(monitor) {
  const plan = monitor.plan;
  const ns = monitor.looks?.map(look => look.cumulative_n).join(', ') || '';
  return `<section class="sheet settings monitor-plan"><div class="section-title"><h2>监看计划</h2>${chip('开测前登记', 'amber')}</div>
    <p class="muted">开测前定好每个看点的累计人数和整批检验额度，锁定后不再修改。每次评估消耗一次额度，更正已用样本后旧结论失效，重算再消耗一次。</p>
    <form data-form="monitor-plan">
      <div class="field-grid"><label>整批检验额度（次）<input name="test_quota" type="number" min="1" max="50" required value="${plan?.test_quota ?? 4}"></label>
      <label>单侧显著性额度 α<input name="alpha_one_sided" type="number" min="0.0001" max="0.5" step="0.0001" required value="${plan?.alpha_one_sided ?? 0.05}"></label></div>
      <label>各看点累计人数（逗号分隔，严格递增）<input name="cumulative_ns" required value="${esc(ns || '12, 24, 36')}" placeholder="12, 24, 36"></label>
      <p class="muted">每个看点的判定门槛按 O'Brien–Fleming 消耗函数分配，各门槛之和等于单侧额度 α。</p>
      ${formError}<div class="form-actions"><button type="submit">${plan ? '更新计划' : '保存计划'}</button>${plan ? '<button type="button" class="primary" data-lock-plan>锁定计划并开测</button>' : ''}</div>
    </form></section>`;
}

function budgetStrip(monitor) {
  const { budget, recommendation } = monitor;
  const [label, style] = ACTIONS[recommendation.action] || [recommendation.action, ''];
  return `<section class="result-strip monitor-strip" aria-label="监看摘要"><div class="delta"><span>现在该收样吗</span><b>${esc(label)}</b><small>${recommendation.ordinal ? `第 ${recommendation.ordinal} 个看点` : '计划锁定后按看点判断'}</small></div>
    <div><span>整批额度</span><b class="mono">${budget.quota}</b><small>次评估</small></div>
    <div><span>已用 / 剩余</span><b class="mono">${budget.spent} / ${budget.remaining}</b><small>${budget.exhausted ? '额度已用完' : '并发或重试不重复扣'}</small></div>
    <div><span>单侧 α</span><b class="mono">${level(budget.alpha_one_sided)}</b><small>各看点门槛之和</small></div></section>
    <p class="monitor-reason"><b>判断依据</b>${esc(recommendation.reason)}</p>`;
}

function looksTable(monitor) {
  const editable = store.user.role === 'analyst';
  const locked = monitor.plan.locked;
  return `<section class="sheet details-sheet monitor-looks"><div class="section-title"><h2>看点顺序</h2>${chip(`${monitor.looks.length} 个看点`)}</div>
    <div class="table-scroll"><table><thead><tr><th>看点</th><th>累计人数</th><th>最早入组头段</th><th>显著性门槛</th><th>状态</th><th>判定</th>${editable ? '<th class="right">操作</th>' : ''}</tr></thead><tbody>
    ${monitor.looks.map(look => {
      const [text, style] = STATUS[look.status];
      const detail = look.status === 'blocked' ? `缺测 ${esc(look.missing.join('、'))}`
        : look.status === 'enrolling' ? `已入组 ${look.enrolled}，还差 ${look.need}` : `已入组 ${look.enrolled}`;
      return `<tr><td class="mono">第 ${look.ordinal} 个</td><td class="mono">${look.cumulative_n}</td><td>${detail}</td><td class="mono">${level(look.alpha_threshold)}</td><td>${chip(text, style)}</td><td>${look.decision ? (look.decision === 'stop' ? chip('样张显著更好', 'green') : chip('尚不显著')) : '—'}${look.p_value != null ? `<small class="p-value">p = ${pValue(look.p_value)}</small>` : ''}</td>${editable ? `<td class="right">${locked && look.status === 'ready' ? `<button class="text-button" data-evaluate="${look.id}">评估</button>` : '—'}</td>` : ''}</tr>`;
    }).join('')}</tbody></table></div>
    ${!locked ? '<p class="muted">锁定计划后才能评估看点。</p>' : ''}</section>`;
}

function evidenceTable(monitor) {
  const rows = [...monitor.evaluations].reverse();
  return `<section class="sheet details-sheet monitor-evidence"><div class="section-title"><h2>每次判断的依据</h2>${chip(`${rows.length} 次评估`)}</div>
    ${rows.length ? `<div class="missing-scroll evidence-scroll"><table><thead><tr><th>序号</th><th>看点</th><th>人数</th><th>样本头段</th><th>单侧 p</th><th>门槛</th><th>判定</th><th>额度</th><th>评估人 / 时间</th><th>状态</th></tr></thead><tbody>
    ${rows.map(e => `<tr class="${e.invalidated_at ? 'voided' : ''}"><td class="mono">#${e.id}</td><td class="mono">第 ${e.ordinal} 个</td><td class="mono">${e.cumulative_n}</td><td class="mono cohort-codes" title="${esc(e.cohort_codes.join('、'))}">${esc(e.cohort_codes[0])} … ${esc(e.cohort_codes[e.cohort_codes.length - 1])}</td><td class="mono">${pValue(e.result.p_value_one_sided)}</td><td class="mono">${level(e.alpha_threshold)}</td><td>${e.result.decision === 'stop' ? chip('样张显著更好', 'green') : chip('尚不显著')}</td><td class="mono">${e.quota_before} → ${e.quota_after}</td><td>${esc(e.evaluated_by)}<small>${timestamp(e.created_at)}</small></td><td>${e.invalidated_at ? chip(e.invalidated_reason || '已失效', 'amber') : chip('有效', 'green')}</td></tr>`).join('')}</tbody></table></div>` : '<p class="muted">尚未评估任何看点。评估后这里保留每次的样本头段、p 值、门槛与额度扣减。</p>'}</section>`;
}

export function monitorPage() {
  const { study, user } = store;
  const head = heading('序贯监看', '监看与收样', '按预登记的累计人数逐个评估配对样本，控制整批检验额度，并显示现在是否该收样。');
  if (!study) return head + empty('暂无复验批次', '请先登记展签与配对记录。');
  const monitor = study.monitor;
  if (!monitor || !monitor.plan) {
    if (user.role !== 'analyst') return head + empty('尚未登记监看计划', '由分析员在开测前登记累计人数与整批额度。');
    return head + `<div class="run-grid">${planForm({ plan: null, looks: [] })}<section class="sheet history"><div class="section-title"><h2>说明</h2></div><p class="muted">登记计划后由分析员锁定，锁定后累计人数与整批额度不再修改。每个看点取最早入组的对应人数，配对没齐就等。</p></section></div>`;
  }
  const planBlock = monitor.plan.locked ? `<section class="sheet settings monitor-plan locked"><div class="section-title"><h2>监看计划</h2>${chip('已锁定', 'green')}</div>
    <dl class="facts"><div><dt>整批检验额度</dt><dd class="mono">${monitor.plan.test_quota} 次</dd></div><div><dt>单侧 α</dt><dd class="mono">${level(monitor.plan.alpha_one_sided)}</dd></div><div><dt>累计人数</dt><dd class="mono">${monitor.looks.map(look => look.cumulative_n).join(' / ')}</dd></div><div><dt>锁定人</dt><dd>${esc(monitor.plan.locked_by || '—')} · ${timestamp(monitor.plan.locked_at)}</dd></div></dl>
    <p class="muted">开测后锁定。新增观众不影响旧看点；更正已用样本会让相关结论失效，重算另扣一次额度。</p></section>`
    : (user.role === 'analyst' ? planForm(monitor) : `<section class="sheet settings monitor-plan"><div class="section-title"><h2>监看计划</h2>${chip('待锁定', 'amber')}</div><p class="muted">分析员尚需锁定计划才能开测。</p></section>`);
  return `${head}${budgetStrip(monitor)}<div class="monitor-grid">${planBlock}</div>${looksTable(monitor)}${evidenceTable(monitor)}`;
}
