async ([times, delayMs]) => {
  if (!document.body) return;
  for (let i = 0; i < times; i++) {
    const lastHeight = document.body.scrollHeight;
    window.scrollTo(0, lastHeight);
    await new Promise(resolve => {
      let timeoutId;
      const observer = new MutationObserver(() => {
        if (document.body.scrollHeight > lastHeight) {
          clearTimeout(timeoutId);
          observer.disconnect();
          setTimeout(resolve, 100);
        }
      });
      observer.observe(document.body, { childList: true, subtree: true });
      timeoutId = setTimeout(() => { observer.disconnect(); resolve(null); }, delayMs);
    });
  }
}
