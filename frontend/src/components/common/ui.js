import { esc } from '../../utils/format.js';
import { ROLE } from '../../constants/enums.js';
import { store } from '../../stores/workspace.js';

const paths = {
  versions: '<rect x="3.5" y="4" width="17" height="16" rx="1"/><path d="M12 4v16M6.5 8h2.5m6 0h2.5M6.5 12h2.5m6 0h2.5"/>',
  pairs: '<rect x="4" y="4" width="16" height="16" rx="1"/><path d="M4 9h16M4 14h16M10 9v11"/>',
  runs: '<path d="M4 5v15h16M8 15l4-5 3 2 5-6"/><circle cx="20" cy="6" r="1.5"/>',
  review: '<path d="M14 3H6v18h12V7zM14 3v4h4M8.5 14l2.5 2.5 4.5-5"/>',
  export: '<path d="M12 3v12m-4-4 4 4 4-4M5 16v4h14v-4"/>',
  arrow: '<path d="M4 12h15m-5-5 5 5-5 5"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  logout: '<path d="M12 4H5v16h7m-2-8h10m-4-4 4 4-4 4"/>',
};

export const icon = name => `<svg aria-hidden="true" class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.55" stroke-linecap="round" stroke-linejoin="round">${paths[name] || ''}</svg>`;
export const seal = () => '<span class="seal" aria-hidden="true">平渡</span>';
export const chip = (text, style = '') => `<span class="chip ${style}">${esc(text)}</span>`;
export const heading = (kicker, title, description, actions = '') => `<header class="page-heading"><div>
  <p class="eyebrow">${esc(kicker)}</p><h1>${esc(title)}</h1><p class="lede">${esc(description)}</p>
  </div>${actions ? `<div class="actions">${actions}</div>` : ''}</header>`;
export const empty = (title, text) => `<div class="empty"><h3>${esc(title)}</h3><p>${esc(text)}</p></div>`;
export const formError = '<p class="form-error" data-form-error role="alert" hidden></p>';
export const formFooter = (label, cancel = true) => `<div class="form-actions">${cancel ? '<button type="button" data-close>取消</button>' : ''}<button class="primary" type="submit">${label}</button></div>`;

const navigation = { versions: '版本对照', pairs: '配对记录', runs: '复验分析', review: '印前会签' };

export function layout(page, content) {
  const { user, studies, studyId, study } = store;
  const selected = page === 'result' ? 'runs' : page;
  const options = studies.map(row => `<option value="${row.id}" ${row.id === studyId ? 'selected' : ''}>${esc(row.code)} · ${esc(row.title)}</option>`).join('');
  return `<div class="desk">
    <aside class="rail">
      <a href="#versions" class="brand">${seal()}<span><b>平渡展陈</b><small>易读展签复验</small></span></a>
      <div class="rail-nav"><p class="eyebrow">工作台</p><nav aria-label="工作台">${Object.entries(navigation).map(([key, text]) => `<a href="#${key}" ${selected === key ? 'aria-current="page"' : ''}>${icon(key)}<span>${text}</span></a>`).join('')}</nav></div>
      <div class="rail-foot"><span class="avatar">${esc(user.display_name[0])}</span><span><b>${esc(user.display_name)}</b><small>${ROLE[user.role]}</small></span><button type="button" class="icon-button" id="logout" aria-label="退出登录" title="退出登录">${icon('logout')}</button></div>
    </aside>
    <div class="workbench">
      <div class="context-bar"><div><span class="edition-dot"></span>${esc(study?.station || '展陈工作台')}</div><label><span class="sr-only">复验批次</span><select id="study-select" ${!options ? 'disabled' : ''}>${options || '<option>暂无复验批次</option>'}</select></label></div>
      <main id="workspace">${content}</main>
    </div>
    <dialog id="editor"></dialog>
  </div>`;
}
