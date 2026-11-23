const pages = new Set(['versions', 'pairs', 'runs', 'result', 'review']);

export function locationPage() {
  const [key, id] = location.hash.slice(1).split('/');
  return { page: pages.has(key) ? key : 'versions', id: /^\d+$/.test(id || '') ? Number(id) : null };
}

export function navigate(page, id) {
  location.hash = `${page}${id ? `/${id}` : ''}`;
}
