import { request, sessionKey } from '../api/client.js';

export const store = { user: null, versions: [], studies: [], study: null, studyId: null, pairFilter: 'all' };

export async function loadCatalog(preferred = store.studyId) {
  const { versions, studies } = await request('/catalog');
  Object.assign(store, { versions, studies });
  const id = studies.find(row => row.id === Number(preferred))?.id || studies[0]?.id;
  await selectStudy(id);
}

export async function selectStudy(id) {
  store.study = id ? await request(`/studies/${id}`) : null;
  store.studyId = id || null;
  if (id) sessionStorage.setItem('pingdu-study', id);
}

export async function authenticate(username, password) {
  const { token, user } = await request('/login', { method: 'POST', data: { username, password }, anonymous: true });
  sessionStorage.setItem(sessionKey, token);
  store.user = user;
  await loadCatalog(sessionStorage.getItem('pingdu-study'));
}

export function clearSession() {
  sessionStorage.removeItem(sessionKey);
  Object.assign(store, { user: null, versions: [], studies: [], studyId: null, study: null, pairFilter: 'all' });
}
