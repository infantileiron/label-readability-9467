let expired = () => {};
export const sessionKey = 'pingdu-proof-session';
export const onExpired = handler => { expired = handler; };

export async function request(path, { method = 'GET', data, download = false, anonymous = false } = {}) {
  const headers = {};
  if (data) headers['Content-Type'] = 'application/json';
  if (!anonymous) headers.Authorization = `Bearer ${sessionStorage.getItem(sessionKey) || ''}`;
  const res = await fetch(`/api${path}`, { method, headers, body: data ? JSON.stringify(data) : undefined });
  if (!res.ok) {
    if (res.status === 401 && !anonymous) expired();
    const error = await res.json().catch(() => ({}));
    throw new Error(error.detail || `请求失败（${res.status}）`);
  }
  if (download) return res.blob();
  return res.json();
}
