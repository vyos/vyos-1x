/* Version-scoped Pagefind loader. Derives its base from the current URL so the
 * same file works on production, canary, and /pr-<n>/ previews (§9). */
(function (window) {
  'use strict';

  function basePathFor(pathname) {
    var m = pathname.match(/^((\/pr-\d+)?\/[a-z]{2}(?:_[A-Z]{2})?\/[^/]+\/)/);
    if (!m) return null;
    return { base: m[1], prefix: m[2] || '' };
  }

  function prefixResultUrl(url, prefix) {
    return prefix ? prefix + url : url;
  }

  function assetUrlsFor(base) {
    return {
      css: base + 'pagefind/pagefind-ui.css',
      js: base + 'pagefind/pagefind-ui.js',
    };
  }

  function init() {
    var mount = document.getElementById('vyos-search');
    if (!mount) return;
    var ctx = basePathFor(window.location.pathname);
    if (!ctx) return;
    var assets = assetUrlsFor(ctx.base);
    /* Stylesheet first so the UI never renders unstyled. CSS load failure is
     * cosmetic only — no error handler on the link. */
    var l = document.createElement('link');
    l.rel = 'stylesheet';
    l.href = assets.css;
    document.head.appendChild(l);
    var s = document.createElement('script');
    s.src = assets.js;
    s.onerror = function () {
      /* Per-version Pagefind assets missing (index not built yet, preview
       * namespace, transient failure) — show a visible notice instead of
       * leaving #vyos-search a silent empty div. */
      var p = document.createElement('p');
      p.className = 'vyos-search-unavailable';
      p.textContent = 'Search is temporarily unavailable for this version.';
      mount.appendChild(p);
    };
    s.onload = function () {
      /* global PagefindUI */
      new window.PagefindUI({
        element: '#vyos-search',
        baseUrl: ctx.base,
        bundlePath: ctx.base + 'pagefind/',
        processResult: function (result) {
          result.url = prefixResultUrl(result.url, ctx.prefix);
          return result;
        },
      });
    };
    document.head.appendChild(s);
  }

  window.VyOSSearch = {
    basePathFor: basePathFor,
    prefixResultUrl: prefixResultUrl,
    assetUrlsFor: assetUrlsFor,
    init: init,
  };
  if (typeof document !== 'undefined' && document.addEventListener)
    document.addEventListener('DOMContentLoaded', init);
})(window);
