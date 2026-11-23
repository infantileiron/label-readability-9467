import { chip, empty, formError, formFooter, heading, icon } from '../components/common/ui.js';
import { DECISION, ORDER, STATUS } from '../constants/enums.js';
import { store } from '../stores/workspace.js';
import { esc, percent, points, pValue, timestamp } from '../utils/format.js';

export const runState = run => chip(DECISION[run.decision] || STATUS[run.status],
  run.decision === 'publish' || run.status === 'succeeded' && !run.decision ? 'green' : 'amber');

export function runsPage() {
  const { user, study } = store;
  const head = heading('配对统计', '复验分析', '固定当前样本，运行精确 McNemar 检验并查看不一致对的方向。');
  if (!study) return head + empty('暂无复验批次', '请先登记展签与配对记录。');
  const { summary, revision, runs, worker_online } = study;
  return `${head}<div class="run-grid"><section class="sheet settings"><div class="section-title"><h2>分析参数</h2>${chip(worker_online ? 'Worker 就绪' : 'Worker 离线', worker_online ? 'green' : 'amber')}</div>
    <dl class="facts"><div><dt>方法</dt><dd>McNemar 双侧精确检验</dd></div><div><dt>方向区间</dt><dd>Clopper–Pearson</dd></div><div><dt>输入修订</dt><dd class="mono">R${revision}</dd></div><div><dt>完整 / 缺失</dt><dd><b class="mono">${summary.complete} / ${summary.missing}</b> 对</dd></div></dl>
    ${user.role === 'analyst' ? `<form data-form="run"><label>方向区间置信水平<select name="confidence"><option value="90">90%</option><option value="95" selected>95%</option><option value="99">99%</option></select></label>${formError}${summary.total ? formFooter('提交复验', false) : '<p class="muted">登记配对后可提交复验。</p>'}</form>` : '<p class="muted">由分析员提交复验。</p>'}</section>
    <section class="sheet history"><div class="section-title"><h2>${user.role === 'viewer' ? '已发布结论' : '运行记录'}</h2><span class="muted">${runs.length} 条</span></div>
    ${runs.length ? `<div class="run-list">${runs.map(run => `<a href="#result/${run.id}"><div><b class="mono">复验 #${run.id}</b><small>R${run.revision} · ${run.confidence}% 区间 · ${timestamp(run.created_at)}</small></div>${runState(run)}${icon('arrow')}</a>`).join('')}</div>` : empty('还没有可查看的运行', '分析完成后可以在此查看结果和输入快照。')}
    </section></div>`;
}

function direction(result, confidence) {
  const interval = result.direction_interval;
  return `<section class="sheet direction"><div class="section-title"><h2>不一致对方向</h2></div>
    <p class="muted">在 ${result.discordant} 个不一致对中，样张独胜 ${result.new_only} 对。</p>
    ${interval ? `<p class="direction-number">${percent(result.new_win_share)} <small>样张独胜比例</small></p>
      <div class="interval-chart" role="img" aria-label="${confidence}% 方向区间 ${percent(interval[0])} 至 ${percent(interval[1])}，估计值 ${percent(result.new_win_share)}"><span class="neutral-line"></span><span class="interval-range" style="left:${100 * interval[0]}%;right:${100 - 100 * interval[1]}%"></span><span class="interval-point" style="left:${100 * result.new_win_share}%"></span></div><div class="axis"><span>0%</span><span>50%</span><span>100%</span></div>
      <p class="interval-caption">${confidence}% 精确方向区间 <b>${percent(interval[0])}–${percent(interval[1])}</b></p>` : '<p class="unavailable">没有不一致对，方向区间不可估计。</p>'}</section>`;
}

export function resultPage(run) {
  const head = heading('复验分析 / 结果', `复验 #${run.id}`, `样本修订 R${run.revision} · ${run.confidence}% 方向区间 · ${run.method}`,
    '<a href="#runs" class="button">返回运行记录</a>');
  if (run.status === 'queued') return head + `<section class="sheet pending" aria-live="polite">${runState(run)}<h2>等待计算</h2><p>样本快照已固定，页面将自动更新。</p><code>${esc(run.checksum)}</code></section>`;
  if (run.status === 'failed') return head + empty('复验失败', run.error || '请返回复验分析并重新提交。');
  const r = run.result;
  return `${head}<section class="result-strip" aria-label="复验摘要"><div><span>旧版成功率</span><b>${percent(r.old_rate)}</b><small>${r.old_success} / ${r.complete} 对</small></div><div><span>易读样张成功率</span><b>${percent(r.new_rate)}</b><small>${r.new_success} / ${r.complete} 对</small></div><div class="delta"><span>配对成功率变化</span><b data-metric="delta">${points(r.delta_pp)} <em>${r.delta_pp == null ? '' : '百分点'}</em></b><small>差值按完整配对计算</small></div><div><span>双侧精确 p 值</span><b data-metric="p">${pValue(r.p_value)}</b><small>${r.complete} 对完整 · ${r.missing} 对缺失</small></div></section>
    ${run.revision !== run.current_revision ? `<p class="warning">这是 R${run.revision} 的历史快照。当前样本已更新至 R${run.current_revision}。</p>` : ''}
    ${!r.complete ? '<p class="warning">缺少完整配对，成功率、百分点变化和检验均不可估计。</p>' : ''}
    <div class="result-grid"><section class="sheet matrix"><div class="section-title"><h2>完整配对四格表</h2>${chip(`${r.complete} 对`)}</div><table><thead><tr><th scope="col">旧版 ＼ 样张</th><th scope="col">成功</th><th scope="col">未成功</th></tr></thead><tbody><tr><th scope="row">成功</th><td>${r.both_ok}</td><td class="discord">${r.old_only} <small>旧版独胜</small></td></tr><tr><th scope="row">未成功</th><td class="discord">${r.new_only} <small>样张独胜</small></td><td>${r.neither}</td></tr></tbody></table></section>${direction(r, run.confidence)}</div>
    <div class="result-grid evidence-grid"><section class="sheet details-sheet"><div class="section-title"><h2>阅读顺序诊断</h2></div><table><thead><tr><th>读序</th><th>登记</th><th>完整</th><th>缺失</th><th>变化（百分点）</th></tr></thead><tbody>${Object.entries(r.reading_orders).map(([key, row]) => `<tr><td>${ORDER[key]}</td><td>${row.total}</td><td>${row.complete}</td><td>${row.missing}</td><td class="mono">${points(row.delta_pp)}</td></tr>`).join('')}</tbody></table></section>
    <section class="sheet details-sheet"><div class="section-title"><h2>缺失配对</h2>${chip(`${r.missing} 对`, r.missing ? 'amber' : '')}</div>
    ${r.missing ? `<div class="missing-scroll"><table><thead><tr><th>观众编号</th><th>阅读顺序</th><th>缺测侧</th></tr></thead><tbody>${r.missing_pairs.map(row => `<tr><td class="mono">${esc(row.visitor_code)}</td><td>${ORDER[row.reading_order]}</td><td>${row.old_ok === null && row.new_ok === null ? '双侧' : row.old_ok === null ? '旧版' : '样张'}</td></tr>`).join('')}</tbody></table></div>` : '<p class="muted">所有登记观众均完成两次阅读。</p>'}</section></div>
    <div class="foot-action result-footer"><div><span>输入校验值</span><code title="${esc(run.checksum)}">${esc(run.checksum)}</code></div><div class="actions"><button data-download="json" data-run="${run.id}">${icon('export')} 结论 JSON</button><button data-download="csv" data-run="${run.id}">${icon('export')} 样本 CSV</button><a class="button primary" href="#review/${run.id}">查看会签 ${icon('arrow')}</a></div></div>`;
}
