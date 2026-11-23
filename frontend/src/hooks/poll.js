export function pollWhile(check, onError, delay = 900) {
  let stopped = false;
  let timer;
  async function tick() {
    if (stopped) return;
    try {
      const again = await check(() => stopped);
      if (!stopped && again) timer = setTimeout(tick, delay);
    } catch (error) {
      if (!stopped) onError(error);
    }
  }
  timer = setTimeout(tick, delay);
  return () => { stopped = true; clearTimeout(timer); };
}
