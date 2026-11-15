// User-triggered URL/title detection only. Never reads inputs, forms, or account data.
chrome.runtime.onMessage.addListener((message, _sender, reply) => {
  if (message.action !== "detect-symbol") return;
  const candidates =
    (decodeURIComponent(location.pathname) + " " + document.title)
      .toUpperCase()
      .match(
        /\b(?:RELIANCE|HDFCBANK|ICICIBANK|INFY|TCS|ITC|SBIN|LT|BHARTIARTL|TATASTEEL|SUNPHARMA|MARUTI)\b/g,
      ) || [];
  reply({ symbol: candidates[0] || null });
});
