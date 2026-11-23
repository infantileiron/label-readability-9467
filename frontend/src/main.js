import { onExpired, request, sessionKey } from './api/client.js';
import { empty, layout } from './components/common/ui.js';
import { pollWhile } from './hooks/poll.js';
import { loginPage } from './pages/login.js';
import { pairForm, pairsPage } from './pages/pairs.js';
import { reviewPage } from './pages/review.js';
import { resultPage, runsPage } from './pages/runs.js';
import { studyForm, versionForm, versionsPage } from './pages/versions.js';
import { locationPage, navigate } from './router/location.js';
import { authenticate, clearSession, loadCatalog, selectStudy, store } from './stores/workspace.js';
import { notify, submitForm } from './utils/forms.js';

const root = document.querySelector('#app');
const editors = { study: studyForm, version: versionForm, pair: pairForm };
let cancelPoll = () => {};
let renderCount = 0;

async function render() {
  const count = ++renderCount;
  cancelPoll();
  if (!store.user) {
    root.innerHTML = loginPage();
    return;
  }
  const { page, id } = locationPage();
  const simple = { versions: versionsPage, pairs: pairsPage, runs: runsPage };
  try {
    if (simple[page]) {
      root.innerHTML = layout(page, simple[page]());
      if (page === 'runs' && store.study?.runs.some(run => run.status === 'queued')) {
        cancelPoll = pollWhile(async stopped => {
          const study = await request(`/studies/${store.studyId}`);
          if (stopped()) return false;
          store.study = study;
          const rows = document.querySelector('.history');
          const template = document.createElement('template');
          template.innerHTML = runsPage();
          rows.replaceWith(template.content.querySelector('.history'));
          return study.runs.some(run => run.status === 'queued');
        }, error => notify(error.message));
      }
      return;
    }
    const review = page === 'review';
    const available = store.study?.runs.filter(run => run.status === 'succeeded') || [];
    const runId = review && !id ? available[0]?.id : id;
    let run = runId ? await request(`/runs/${runId}`) : null;
    if (count !== renderCount) return;
    if (run && run.study_id !== store.studyId) {
      await selectStudy(run.study_id);
      if (count !== renderCount) return;
    }
    if (review && run?.status !== 'succeeded') run = null;
    if (review && run && !store.study.runs.some(row => row.id === run.id)) await selectStudy(run.study_id);
    if (count !== renderCount) return;
    root.innerHTML = layout(page, review ? reviewPage(run) : run ? resultPage(run) : empty('请选择运行记录', '在复验分析页选择一个运行。'));
    if (!review && run?.status === 'queued') {
      cancelPoll = pollWhile(async stopped => {
        const next = await request(`/runs/${run.id}`);
        if (stopped()) return false;
        if (next.status === 'queued') return true;
        await selectStudy(next.study_id);
        if (!stopped()) root.innerHTML = layout(page, resultPage(next));
        return false;
      }, error => notify(error.message));
    }
  } catch (error) {
    if (count !== renderCount || !store.user) return;
    root.innerHTML = layout(page, empty('无法打开页面', error.message));
  }
}

function go(page, id) {
  const hash = `#${page}${id ? `/${id}` : ''}`;
  if (location.hash === hash) render();
  else navigate(page, id);
}

const post = (path, data) => request(path, { method: 'POST', data });
const outcome = value => value === '' ? null : value === 'true';

const actions = {
  version: async data => {
    await post('/versions', { ...data, type_pt: Number(data.type_pt), line_height: Number(data.line_height) });
    await loadCatalog();
    await render();
    notify('展签版本已登记');
  },
  study: async data => {
    const created = await post('/studies', { ...data, old_id: Number(data.old_id), new_id: Number(data.new_id) });
    await loadCatalog(created.id);
    store.pairFilter = 'all';
    go('versions');
    notify('复验批次已创建');
  },
  pair: async ({ visitor_code, reading_order, old_ok, new_ok }) => {
    const { id, revision } = store.study;
    await request(`/studies/${id}/pairs/${encodeURIComponent(visitor_code)}?revision=${revision}`, {
      method: 'PUT', data: { reading_order, old_ok: outcome(old_ok), new_ok: outcome(new_ok) },
    });
    await selectStudy(id);
    store.pairFilter = 'all';
    await render();
    const saved = document.querySelector(`[data-visitor="${CSS.escape(visitor_code)}"]`);
    if (saved) saved.scrollIntoView({ block: 'nearest' });
    notify(`已保存 ${visitor_code} 的配对记录`);
  },
  run: async data => {
    const run = await post(`/studies/${store.studyId}/runs`, { confidence: Number(data.confidence) });
    await selectStudy(store.studyId);
    go('result', run.id);
  },
};

function logout() {
  clearSession();
  render();
}

onExpired(logout);
window.addEventListener('hashchange', () => { window.scrollTo(0, 0); render(); });

root.addEventListener('submit', event => {
  const { target, submitter } = event;
  if (target.id === 'login-form') {
    submitForm(event, async ({ username, password }) => {
      await authenticate(username.trim(), password);
      go('versions');
    });
  } else if (target.dataset.form === 'review') {
    submitForm(event, async ({ note }) => {
      const runId = target.dataset.run;
      await post(`/runs/${runId}/review`, { decision: submitter?.value || 'revise', note });
      await selectStudy(store.studyId);
      await render();
      notify('会签意见已保存');
    });
  } else if (actions[target.dataset.form]) {
    submitForm(event, actions[target.dataset.form]);
  }
});

root.addEventListener('click', async event => {
  const button = event.target.closest('button');
  if (!button) return;
  const { demo, edit, close, code, filter, download, run } = button.dataset;
  if (demo) {
    const form = document.querySelector('#login-form');
    form.elements.username.value = demo;
    form.elements.password.value = 'Proof5203!';
    form.requestSubmit(form.querySelector('button[type=submit]'));
  } else if (button.id === 'logout') {
    logout();
  } else if (edit) {
    const dialog = document.querySelector('#editor');
    dialog.innerHTML = editors[edit](code);
    dialog.showModal();
  } else if (close !== undefined) {
    document.querySelector('#editor').close();
  } else if (filter) {
    store.pairFilter = filter;
    render();
  } else if (download) {
    button.disabled = true;
    const file = download === 'csv' ? 'pairs.csv' : 'export.json';
    try {
      const blob = await request(`/runs/${run}/${file}`, { download: true });
      const url = URL.createObjectURL(blob);
      const anchor = Object.assign(document.createElement('a'), { href: url, download: `proof-${run}-${file}` });
      anchor.click();
      setTimeout(() => URL.revokeObjectURL(url), 3000);
      notify('已下载固定快照');
    } catch (error) {
      notify(error.message);
    } finally {
      button.disabled = false;
    }
  }
});

root.addEventListener('change', async ({ target }) => {
  if (target.id === 'study-select') {
    target.disabled = true;
    try {
      await selectStudy(Number(target.value));
      store.pairFilter = 'all';
      go('versions');
    } catch (error) {
      target.value = store.studyId;
      target.disabled = false;
      notify(error.message);
    }
  } else if (target.id === 'review-select') {
    go('review', Number(target.value));
  }
});

root.addEventListener('input', ({ target }) => {
  if (target.id !== 'pair-search') return;
  const query = target.value.trim().toUpperCase();
  const rows = [...document.querySelectorAll('[data-visitor]')];
  rows.forEach(row => { row.hidden = !row.dataset.visitor.includes(query); });
  document.querySelector('#pair-empty').hidden = rows.some(row => !row.hidden);
});

try {
  if (sessionStorage.getItem(sessionKey)) {
    store.user = await request('/me');
    await loadCatalog(sessionStorage.getItem('pingdu-study'));
  }
} catch (error) {
  clearSession();
  notify(error.message);
}
render();
