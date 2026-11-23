const escapes = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
export const esc = value => String(value ?? '').replace(/[&<>"']/g, char => escapes[char]);
export const percent = value => value == null ? '—' : `${(value * 100).toFixed(1)}%`;
export const points = value => value == null ? '—' : `${value > 0 ? '+' : ''}${value.toFixed(1)}`;
export const pValue = value => value == null ? '—' : value > 0 && value < .0001 ? value.toExponential(3) : value.toFixed(5);
export const timestamp = value => value ? new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Shanghai', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false,
}).format(new Date(value)) : '—';
