/* VyOS docs version picker + status banner + language scaffold.
 * Vanilla JS, no dependencies, no build step. Degrades silently when
 * /versions.json is unreachable (docs stay fully readable). */
(function (window) {
  'use strict';

  // Deliberately does not match /pr-<n>/ preview prefixes — previews are single-version,
  // so the picker has nothing to switch between and stays hidden there by design.
  // The (?!\.\.?\/) guard rejects the dot-segments "." and ".." as slugs, which would
  // otherwise escape the /<lang>/<slug>/ tree once the browser normalizes the URL.
  function parseLocation(pathname) {
    var m = pathname.match(/^\/([a-z]{2}(?:_[A-Z]{2})?)\/(?!\.\.?\/)([A-Za-z0-9._-]+)\/(.*)$/);
    if (!m) return null;
    return { lang: m[1], slug: m[2], rest: m[3] };
  }

  // Contract: versions.json lists versions newest-first, so the first 'lts' entry found
  // here is the newest LTS — callers rely on that ordering rather than comparing versions.
  function newestLts(manifest) {
    for (var i = 0; i < manifest.versions.length; i++)
      if (manifest.versions[i].status === 'lts') return manifest.versions[i].slug;
    return null;
  }

  function bannerFor(slug, manifest) {
    var entry = null, i;
    for (i = 0; i < manifest.versions.length; i++)
      if (manifest.versions[i].slug === slug) entry = manifest.versions[i];
    if (!entry) return null;
    var newest = newestLts(manifest);
    if (entry.status === 'dev') return { kind: 'dev', newest: newest };
    if (entry.status === 'eol') return { kind: 'eol', newest: newest };
    if (entry.status === 'lts' && newest && newest !== slug)
      return { kind: 'newer-lts', newest: newest };
    return null;
  }

  /* Normalize one path segment: each well-formed %HH run is decoded and re-encoded on its
   * own — per run, not per segment, so one malformed escape cannot double-encode the valid
   * ones beside it (location.pathname hands escapes back verbatim, and blind re-encoding
   * would turn %2E into %252E and miss on the HEAD probe). Literal spans, including a bare
   * '%', always go through encodeURIComponent, so taint neutralization holds unconditionally;
   * a run decoding to invalid UTF-8 is kept verbatim, being already pure %HH text.
   * Decoding cannot resurrect a dot-segment: the URL parser resolves '.' / '..' and their
   * percent-encoded forms during navigation, so pathname never presents them. */
  function encodeSegment(seg) {
    var out = '';
    var re = /(?:%[0-9A-Fa-f]{2})+/g;
    var last = 0;
    var m;
    while ((m = re.exec(seg))) {
      out += encodeURIComponent(seg.slice(last, m.index));
      try { out += encodeURIComponent(decodeURIComponent(m[0])); } catch (e) { out += m[0]; }
      last = m.index + m[0].length;
    }
    return out + encodeURIComponent(seg.slice(last));
  }

  /* Percent-encode a multi-segment path one segment at a time, so the '/' separators
   * survive. Real docs paths are plain ASCII sphinx slugs (letters/digits/-/_/./html),
   * where this is a no-op — it exists to keep DOM-derived text (location.pathname,
   * select.value) from reaching a location.href sink unescaped. */
  function encodePath(rest) {
    return rest.split('/').map(function (seg) { return encodeSegment(seg); }).join('/');
  }

  function targetUrlFor(loc, targetSlug) {
    return '/' + encodeURIComponent(loc.lang) + '/' + encodeURIComponent(targetSlug) +
      '/' + encodePath(loc.rest);
  }

  /* Full navigation URL for a version switch: same path on the target version
   * with the current query string + fragment re-attached, so deep links
   * (?highlight=…, #section) survive the switch (§4 URL-stability contract). */
  function navUrlFor(loc, targetSlug, search, hash) {
    return targetUrlFor(loc, targetSlug) + (search || '') + (hash || '');
  }

  /* Mirror of targetUrlFor for the language switch: swaps the lang segment while
   * keeping the current version slug and path. */
  function langUrlFor(loc, langCode) {
    return '/' + encodeURIComponent(langCode) + '/' + encodeURIComponent(loc.slug) +
      '/' + encodePath(loc.rest);
  }

  /* ---- DOM layer (no execution at import time) ---- */
  function bannerText(b, manifest) {
    if (b.kind === 'dev') return 'You are reading the development (rolling) docs.';
    if (b.kind === 'eol') return 'This VyOS version is end-of-life; these docs are frozen. See the ' + b.newest + ' (LTS) docs.';
    return 'A newer LTS (' + b.newest + ') is available.';
  }

  function init() {
    var anchor = document.getElementById('vyos-version-picker');
    if (!anchor) return;
    var loc = parseLocation(window.location.pathname);
    if (!loc) return;

    fetch('/versions.json', { headers: { accept: 'application/json' } })
      .then(function (r) { if (!r.ok) throw new Error('versions.json ' + r.status); return r.json(); })
      .then(function (manifest) {
        renderPicker(anchor, loc, manifest);
        renderLang(anchor, loc, manifest);
        renderBanner(loc, manifest);
      })
      .catch(function () { /* silent degradation (§4) */ });
  }

  function renderPicker(anchor, loc, manifest) {
    var label = document.createElement('label');
    label.setAttribute('for', 'vyos-version-select');
    label.textContent = 'Version: ';
    var sel = document.createElement('select');
    sel.id = 'vyos-version-select';
    manifest.versions.forEach(function (v) {
      var o = document.createElement('option');
      o.value = v.slug; o.textContent = v.label; o.selected = v.slug === loc.slug;
      sel.appendChild(o);
    });
    sel.addEventListener('change', function () {
      var search = window.location.search, hash = window.location.hash;
      var target = navUrlFor(loc, sel.value, search, hash);
      var fallback = '/' + encodeURIComponent(loc.lang) + '/' + encodeURIComponent(sel.value) +
        '/' + (search || '') + (hash || '');
      fetch(targetUrlFor(loc, sel.value), { method: 'HEAD' })
        .then(function (r) {
          window.location.href = (r.status === 404) ? fallback : target;
        })
        .catch(function () { window.location.href = fallback; });
    });
    anchor.appendChild(label);
    anchor.appendChild(sel);

    var entry = manifest.versions.filter(function (v) { return v.slug === loc.slug; })[0];
    if (entry && entry.pdf) {
      var a = document.createElement('a');
      a.href = entry.pdf; a.className = 'vyos-pdf-link'; a.textContent = 'PDF';
      anchor.appendChild(a);
    }
  }

  function renderLang(anchor, loc, manifest) {
    if (!manifest.languages || manifest.languages.length <= 1) return; // scaffold: hidden while en-only (§4)
    var sel = document.createElement('select');
    sel.id = 'vyos-lang-select';
    sel.setAttribute('aria-label', 'Language');
    manifest.languages.forEach(function (l) {
      var o = document.createElement('option');
      o.value = l.code; o.textContent = l.label; o.selected = l.code === loc.lang;
      sel.appendChild(o);
    });
    sel.addEventListener('change', function () {
      window.location.href = langUrlFor(loc, sel.value) +
        window.location.search + window.location.hash;
    });
    anchor.appendChild(sel);
  }

  function renderBanner(loc, manifest) {
    var b = bannerFor(loc.slug, manifest);
    if (!b) return;
    var key = 'vyos-banner-dismissed-' + loc.slug;
    try { if (window.localStorage.getItem(key)) return; } catch (e) { /* private mode */ }
    var div = document.createElement('div');
    div.className = 'vyos-version-banner vyos-banner-' + b.kind;
    div.setAttribute('role', b.kind === 'eol' ? 'alert' : 'note');
    var span = document.createElement('span');
    span.textContent = bannerText(b, manifest);
    div.appendChild(span);
    if (b.newest && b.kind !== 'dev') {
      var link = document.createElement('a');
      link.href = '/' + loc.lang + '/' + b.newest + '/';
      link.textContent = ' Switch to ' + b.newest + '.';
      div.appendChild(link);
    }
    var x = document.createElement('button');
    x.textContent = '×'; x.className = 'vyos-banner-dismiss';
    x.setAttribute('aria-label', 'Dismiss');
    x.addEventListener('click', function () {
      try { window.localStorage.setItem(key, '1'); } catch (e) { /* ignore */ }
      div.remove();
    });
    div.appendChild(x);
    document.body.insertBefore(div, document.body.firstChild);
  }

  window.VyOSVersionPicker = {
    parseLocation: parseLocation, bannerFor: bannerFor, encodePath: encodePath,
    targetUrlFor: targetUrlFor, navUrlFor: navUrlFor, langUrlFor: langUrlFor, init: init,
  };
  if (typeof document !== 'undefined' && document.addEventListener)
    document.addEventListener('DOMContentLoaded', init);
})(window);
