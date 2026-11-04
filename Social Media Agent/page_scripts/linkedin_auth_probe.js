(() => {
  const text = [
    window.location.href || '',
    document.title || '',
    document.body ? (document.body.innerText || '').slice(0, 4000) : '',
  ].join('\n');
  return /linkedin\.com\/(?:login|checkpoint|authwall|uas)/i.test(text)
    || /\b(sign in|log in|join linkedin|captcha|verification required)\b/i.test(text)
    || /(请登录|登录领英|安全验证)/.test(text);
})()
