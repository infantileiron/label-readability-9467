import { chip, empty, formError, formFooter, heading, icon } from '../components/common/ui.js';
import { ORDER } from '../constants/enums.js';
import { store } from '../stores/workspace.js';
import { completePair } from '../types/records.js';
import { esc } from '../utils/format.js';

const outcome = value => value === null ? chip('缺测', 'amber') : value ? chip('成功', 'green') : chip('未成功');

export function pairsPage() {
  const { study, user, pairFilter } = store;
  const editable = user.role === 'analyst';
  const actions = study && editable ? `<button class="primary" data-edit="pair">${icon('plus')} 登记配对</button>` : '';
  const head = heading('观众测读', '配对记录', '每个匿名观众编号对应两次阅读，保留先后顺序以及缺测一侧。', actions);
  if (!study) return head + empty('暂无批次', '请在版本对照页创建复验批次。');
  const counts = study.summary;
  const filters = { all: ['全部', counts.total], complete: ['完整配对', counts.complete], missing: ['缺失对', counts.missing] };
  const visible = study.pairs.filter(row => pairFilter === 'all' || completePair(row) === (pairFilter === 'complete'));
  return `${head}<section class="study-banner"><div><p class="mono">${esc(study.code)} / 测读任务</p><p>${esc(study.reading_task)}</p></div>${chip(`样本修订 R${study.revision}`)}</section>
    <section class="sheet table-sheet"><div class="table-tools"><div class="tabs" aria-label="筛选配对状态">${Object.entries(filters).map(([key, [name, count]]) => `<button data-filter="${key}" aria-pressed="${pairFilter === key}">${name} <b>${count}</b></button>`).join('')}</div><input id="pair-search" aria-label="搜索观众编号" placeholder="搜索观众编号"></div>
    <div class="table-scroll pair-scroll"><table><thead><tr><th>观众编号</th><th>阅读顺序</th><th>旧版结果</th><th>样张结果</th><th>入组情况</th>${editable ? '<th class="right">操作</th>' : ''}</tr></thead><tbody>${visible.map(row => `<tr data-visitor="${esc(row.visitor_code)}"><td class="mono">${esc(row.visitor_code)}</td><td>${ORDER[row.reading_order]}</td><td>${outcome(row.old_ok)}</td><td>${outcome(row.new_ok)}</td><td>${completePair(row) ? '完整配对' : '缺失 · 未入组'}</td>${editable ? `<td class="right"><button class="text-button" data-edit="pair" data-code="${esc(row.visitor_code)}">编辑</button></td>` : ''}</tr>`).join('')}</tbody></table><p class="empty row-empty" id="pair-empty" ${visible.length ? 'hidden' : ''}>没有符合条件的配对记录。</p></div></section>`;
}

export function pairForm(code) {
  const row = store.study.pairs.find(pair => pair.visitor_code === code);
  const select = (name, caption) => `<label>${caption}<select name="${name}"><option value="" ${row?.[name] == null ? 'selected' : ''}>缺测</option><option value="true" ${row?.[name] === true ? 'selected' : ''}>成功</option><option value="false" ${row?.[name] === false ? 'selected' : ''}>未成功</option></select></label>`;
  return `<form data-form="pair"><h2>${row ? '编辑配对' : '登记配对'}</h2><p class="muted">未观察到的一侧请保留为「缺测」。</p>
    <div class="field-grid"><label>观众编号<input name="visitor_code" required maxlength="30" pattern="[A-Z0-9][A-Z0-9\\-]{1,29}" value="${esc(code)}" ${row ? 'readonly' : ''} placeholder="PD-37"></label><label>阅读顺序<select name="reading_order">${Object.entries(ORDER).map(([key, text]) => `<option value="${key}" ${row?.reading_order === key ? 'selected' : ''}>${text}</option>`).join('')}</select></label></div>
    <div class="field-grid">${select('old_ok', '旧版结果')}${select('new_ok', '样张结果')}</div>
    ${formError}${formFooter('保存配对')}</form>`;
}
