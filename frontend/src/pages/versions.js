import { chip, empty, formError, formFooter, heading, icon } from '../components/common/ui.js';
import { store } from '../stores/workspace.js';
import { esc } from '../utils/format.js';

function specimen(version, kind) {
  const isNew = kind === 'new';
  return `<article class="specimen ${isNew ? 'specimen-new' : ''}"><header><span>${isNew ? '易读样张' : '旧版展签'}</span><span class="mono">${esc(version.code)}</span></header>
    <div class="label-proof" style="--label-size:${Number(version.type_pt)}px;--label-leading:${Number(version.line_height)}"><h2>${esc(version.exhibit)}</h2><p>${esc(version.body)}</p></div>
    <footer><span>${esc(version.title)}</span><span>${version.type_pt} pt · ${Number(version.line_height).toFixed(2)} 倍行距</span></footer></article>`;
}

export function versionsPage() {
  const { study, versions, user } = store;
  const controls = user.role === 'analyst' ? `<button type="button" data-edit="study">新建批次</button><button class="primary" type="button" data-edit="version">${icon('plus')} 登记展签</button>` : '';
  const head = heading('展签校样墙', '版本对照', '对照同一件展品的两份文案与排版，确认观众读到的展签。', controls);
  const current = study ? [versions.find(row => row.id === study.old_id), versions.find(row => row.id === study.new_id)] : [];
  const other = versions.filter(row => !current.includes(row));
  return `${head}${study ? `<section class="study-banner"><div><p class="mono">${esc(study.code)} / 测读任务</p><p>${esc(study.reading_task)}</p></div>${chip(`样本修订 R${study.revision}`)}</section>
    <div class="proof-wall">${specimen(current[0], 'old')}${specimen(current[1], 'new')}</div>
    <div class="foot-action"><span>展签版本登记后保留原文。改稿时请登记新版本。</span><a class="button" href="#pairs">前往配对记录 ${icon('arrow')}</a></div>` : empty('暂无复验批次', '登记同一展品的两个版本后即可发起复验。')}
    ${other.length ? `<section class="registry"><h2>其他已登记版本</h2><div class="version-register">${other.map(row => `<details><summary><b class="mono">${esc(row.code)}</b>　${esc(row.exhibit)} · ${esc(row.title)}</summary><p>${esc(row.body)}</p><small>${row.type_pt} pt · ${Number(row.line_height).toFixed(2)} 倍行距</small></details>`).join('')}</div></section>` : ''}`;
}

export function versionForm() {
  return `<form data-form="version"><h2>登记展签</h2><p class="muted">登记时保存当次实物校样的原文、字号与行距。</p>
    <div class="field-grid"><label>版本编号<input name="code" required maxlength="30" pattern="[A-Z0-9][A-Z0-9\\-]{1,29}" placeholder="YA-03"></label><label>版本标题<input name="title" required maxlength="60" placeholder="样张 · 第二次改写"></label></div>
    <label>展品名称<input name="exhibit" value="${esc(store.versions.find(row => row.id === store.study?.new_id)?.exhibit)}" required maxlength="60"></label>
    <label>展签原文<textarea name="body" required minlength="8" maxlength="500" rows="4"></textarea></label>
    <div class="field-grid"><label>字号（pt）<input name="type_pt" type="number" value="24" min="10" max="72" required></label><label>行距倍数<input name="line_height" type="number" value="1.6" min="1" max="3" step="0.01" required></label></div>
    ${formError}${formFooter('保存版本')}</form>`;
}

export function studyForm() {
  const options = store.versions.map(row => `<option value="${row.id}">${esc(row.code)} · ${esc(row.exhibit)} · ${esc(row.title)}</option>`).join('');
  return `<form data-form="study"><h2>新建复验批次</h2><p class="muted">选择同一展品的两个版本，并写明两次阅读共用的判定标准。</p>
    <div class="field-grid"><label>批次编号<input name="code" required maxlength="30" pattern="[A-Z0-9][A-Z0-9\\-]{1,29}" placeholder="PD-1122"></label><label>展厅／测读点<input name="station" required maxlength="60" placeholder="常设展 · 二厅"></label></div>
    <label>批次名称<input name="title" required maxlength="60"></label>
    <label>测读任务<textarea name="reading_task" required minlength="4" maxlength="240" rows="3"></textarea></label>
    <label>旧版展签<select name="old_id" required><option value="">请选择</option>${options}</select></label>
    <label>易读样张<select name="new_id" required><option value="">请选择</option>${options}</select></label>
    ${formError}${formFooter('创建批次')}</form>`;
}
