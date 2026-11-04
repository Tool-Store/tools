([maxMs, quietMs]) => new Promise(resolve => {
  if (!document.body) {
    setTimeout(() => resolve('nobody'), maxMs);
    return;
  }
  let timer = null;
  let cap = null;
  const done = (reason) => {
    clearTimeout(timer);
    clearTimeout(cap);
    obs.disconnect();
    resolve(reason);
  };
  const resetQuiet = () => {
    clearTimeout(timer);
    timer = setTimeout(() => done('quiet'), quietMs);
  };
  const obs = new MutationObserver(resetQuiet);
  obs.observe(document.body, { childList: true, subtree: true, attributes: true });
  resetQuiet();
  cap = setTimeout(() => done('capped'), maxMs);
})
