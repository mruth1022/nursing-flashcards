/* Pure helpers shared by app.js and the Node tests (tests/core.test.js). No DOM, no storage.
 * Loaded before app.js; exposed as window.NFCore in the browser and module.exports in Node.
 *
 * Editing model: every change in the app is an "op" ({ t: 'edit' | 'add' | 'del' | ... }) kept on the
 * device until it is saved. Saving downloads the latest test file, re-applies the ops to it
 * (applyOps) and commits the result, so edits made on two devices combine instead of overwriting.
 */
(function (root) {
  'use strict';

  /* ---------------------------------------------------------------- sessions */

  /* An in-progress study session after some of its cards stopped existing (deleted in the doc or
   * in the app). Drops just those cards instead of discarding the session.
   * Returns the same object when nothing is missing, a new session otherwise, or null when no
   * cards are left. Undo history is cleared when anything is dropped, because it stores queue
   * positions that no longer line up. */
  function pruneSession(s, exists) {
    if (!s) return null;
    const lists = [s.queue, s.roundYes || [], s.roundNo || [], s.seen || []];
    if (lists.every(l => l.every(exists))) return s;

    let index = s.index;
    const queue = [];
    s.queue.forEach((id, i) => { if (exists(id)) queue.push(id); else if (i < s.index) index--; });
    if (!queue.length) return null;

    const seen = (s.seen || []).filter(exists);
    const firstAnswer = new Map();
    for (const a of s.answers || []) if (!firstAnswer.has(a.id)) firstAnswer.set(a.id, a.yes);
    const out = {
      ...s, queue, index, seen, answers: [],
      roundYes: (s.roundYes || []).filter(exists), roundNo: (s.roundNo || []).filter(exists),
      firstYes: seen.filter(id => firstAnswer.get(id) === true).length,
      firstNo: seen.filter(id => firstAnswer.get(id) === false).length,
    };
    if (index >= queue.length) { out.index = queue.length; out.phase = 'summary'; out.flipped = false; }
    else if (s.index < s.queue.length && !exists(s.queue[s.index])) out.flipped = false; // the card on screen went away
    return out;
  }

  /* ---------------------------------------------------------------- HTML */

  const ENTITY = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: '\u00a0', '#39': "'" };
  function decodeEntities(s) {
    return s.replace(/&(#x[0-9a-f]+|#\d+|[a-z]+\d*);/gi, (m, e) => {
      if (e[0] === '#') { const n = e[1] === 'x' || e[1] === 'X' ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10); return n > 0 && n < 0x110000 ? String.fromCodePoint(n) : ''; }
      return ENTITY[e.toLowerCase()] ?? m;
    });
  }
  const escText = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

  /* Plain text of a card's HTML (used for the prompt text that search and lists show). */
  function htmlToText(html) {
    const t = String(html || '')
      .replace(/<(script|style)[\s\S]*?<\/\1>/gi, '')
      .replace(/<br\s*\/?>|<\/(p|div|li|h\d)>/gi, ' ')
      .replace(/<img[^>]*>/gi, ' ')
      .replace(/<[^>]+>/g, '');
    return decodeEntities(t).replace(/[\s\u00a0]+/g, ' ').trim();
  }

  // colours that just mean "default", e.g. from Google Docs or the editor's own text colour
  const DEFAULT_TEXT = new Set(['#000000', '#1b1f2a', '#1f1f1f', '#222222', '#202124']);
  const DEFAULT_BG = new Set(['#ffffff', '#fefefe']);
  function normColor(v) {
    v = String(v || '').trim().toLowerCase();
    let m;
    if ((m = v.match(/^#([0-9a-f]{3})$/))) return '#' + m[1].split('').map(c => c + c).join('');
    if (/^#[0-9a-f]{6}$/.test(v)) return v;
    if ((m = v.match(/^rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*(?:,\s*([\d.]+)\s*)?\)$/))) {
      if (m[4] !== undefined && parseFloat(m[4]) === 0) return null;
      return '#' + [m[1], m[2], m[3]].map(n => Math.min(255, +n).toString(16).padStart(2, '0')).join('');
    }
    const named = { red: '#ff0000', yellow: '#ffff00', cyan: '#00ffff', aqua: '#00ffff', lime: '#00ff00', blue: '#0000ff', magenta: '#ff00ff', fuchsia: '#ff00ff', orange: '#ffa500', black: '#000000', white: '#ffffff' };
    return named[v] || null;
  }
  function parseStyle(attrs) {
    const m = attrs.match(/\bstyle\s*=\s*("([^"]*)"|'([^']*)')/i);
    const out = {};
    if (!m) return out;
    for (const decl of decodeEntities(m[2] ?? m[3]).split(';')) {
      const i = decl.indexOf(':'); if (i < 0) continue;
      out[decl.slice(0, i).trim().toLowerCase()] = decl.slice(i + 1).trim().toLowerCase();
    }
    return out;
  }
  function attr(attrs, name) {
    const m = attrs.match(new RegExp('(?:^|\\s)' + name + '\\s*=\\s*("([^"]*)"|\'([^\']*)\'|([^\\s>]+))', 'i'));
    return m ? decodeEntities(m[2] ?? m[3] ?? m[4] ?? '') : null;
  }

  const BLOCK = { p: 'p', div: 'p', h1: 'p', h2: 'p', h3: 'p', h4: 'p', h5: 'p', h6: 'p', li: 'li', ul: 'ul', ol: 'ol' };
  const DROP_WITH_CONTENT = new Set(['script', 'style', 'head', 'title', 'meta', 'xml', 'template', 'iframe', 'object', 'noscript', 'svg', 'math']);
  const VOID = new Set(['br', 'img', 'hr', 'meta', 'link', 'input', 'col', 'wbr', 'source']);

  /* Make card HTML safe and consistent: keeps paragraphs, line breaks, lists (with the l0–l3 indent
   * classes the importer uses), bold/italic/underline/strike/sup/sub, highlight (<mark>) and text
   * colour (<span>) as hex colours, and images already stored in img/. Everything else is reduced
   * to its text. Handles Google Docs paste (styles on spans, the font-weight:normal <b> wrapper). */
  function sanitizeHtml(input) {
    let src = String(input || '').replace(/<!--[\s\S]*?-->/g, '').replace(/<!\[CDATA\[[\s\S]*?\]\]>/g, '').replace(/<!doctype[^>]*>/gi, '');
    src = src.replace(/<(script|style|head|title|template|iframe|object|noscript|svg|math|xml)\b[\s\S]*?<\/\1\s*>/gi, '');
    const out = [];
    const stack = [];            // { tag, emitted: [closing tags in order] }
    const open = (tag) => stack.some(f => f.emitted.includes(tag)); // by what was output, not the source tag
    const tokenRe = /<(\/?)([a-zA-Z][a-zA-Z0-9]*)((?:[^>"']|"[^"]*"|'[^']*')*)>|([^<]+)|(<)/g;
    let m;
    while ((m = tokenRe.exec(src))) {
      if (m[4] !== undefined) { out.push(escText(decodeEntities(m[4]))); continue; }
      if (m[5] !== undefined) { out.push('&lt;'); continue; }
      const closing = m[1] === '/'; const tag = m[2].toLowerCase(); const attrs = m[3] || '';
      if (DROP_WITH_CONTENT.has(tag)) continue;
      if (closing) {
        const i = stack.map(f => f.tag).lastIndexOf(tag);
        if (i < 0) continue;
        while (stack.length > i) { const f = stack.pop(); for (const c of f.emitted) out.push('</' + c + '>'); }
        continue;
      }
      if (tag === 'br') { out.push('<br>'); continue; }
      if (tag === 'img') {
        const s = attr(attrs, 'src');
        if (s && /^img\/[A-Za-z0-9_.-]+$/.test(s)) out.push('<img src="' + s + '" alt="" loading="lazy">');
        continue;
      }
      if (VOID.has(tag)) continue;
      const emitted = [];
      const block = BLOCK[tag];
      if (block === 'ul' || block === 'ol') {
        const cls = (attr(attrs, 'class') || '').split(/\s+/).find(c => /^l[0-3]$/.test(c));
        const start = block === 'ol' ? attr(attrs, 'start') : null;
        out.push('<' + block + (cls ? ' class="' + cls + '"' : '') + (start && /^\d{1,4}$/.test(start) ? ' start="' + start + '"' : '') + '>');
        emitted.push(block);
      } else if (block === 'li') {
        out.push('<li>'); emitted.push('li');
      } else if (block === 'p') {
        if (!open('p') && !open('li')) { out.push('<p>'); emitted.push('p'); }
      }
      // inline formatting from the tag itself and from its style attribute
      const st = parseStyle(attrs);
      const fw = st['font-weight'];
      let bold = ['b', 'strong'].includes(tag) || /^h[1-6]$/.test(tag);
      if (fw) bold = fw === 'bold' || fw === 'bolder' || (/^\d+$/.test(fw) && +fw >= 600) ? true : (fw === 'normal' || /^\d+$/.test(fw) ? false : bold);
      const italic = ['i', 'em'].includes(tag) || st['font-style'] === 'italic';
      const deco = (st['text-decoration'] || '') + ' ' + (st['text-decoration-line'] || '');
      const underline = tag === 'u' || /underline/.test(deco);
      const strike = ['s', 'strike', 'del'].includes(tag) || /line-through/.test(deco);
      const va = st['vertical-align'];
      const sup = tag === 'sup' || va === 'super';
      const sub = tag === 'sub' || va === 'sub';
      let color = normColor(st.color || (tag === 'font' ? attr(attrs, 'color') : null));
      if (color && DEFAULT_TEXT.has(color)) color = null;
      let bg = normColor(st['background-color'] || st.background || (tag === 'mark' ? '#ffff00' : null));
      if (bg && DEFAULT_BG.has(bg)) bg = null;
      if (bg) { out.push('<mark style="background-color:' + bg + '">'); emitted.push('mark'); }
      if (color) { out.push('<span style="color:' + color + '">'); emitted.push('span'); }
      if (bold && !open('b')) { out.push('<b>'); emitted.push('b'); }
      if (italic && !open('i')) { out.push('<i>'); emitted.push('i'); }
      if (underline && !open('u')) { out.push('<u>'); emitted.push('u'); }
      if (strike && !open('s')) { out.push('<s>'); emitted.push('s'); }
      if (sup) { out.push('<sup>'); emitted.push('sup'); } else if (sub) { out.push('<sub>'); emitted.push('sub'); }
      stack.push({ tag, emitted: emitted.reverse() });
    }
    while (stack.length) { const f = stack.pop(); for (const c of f.emitted) out.push('</' + c + '>'); }
    let html = out.join('');
    // tidy: empty wrappers, stray breaks
    let prev;
    do {
      prev = html;
      html = html.replace(/<(b|i|u|s|sup|sub|mark|span)(?: [^>]*)?>(\s*)<\/\1>/g, '$2')
        .replace(/<(p|li)>(?:\s|<br>|&nbsp;|\u00a0)*<\/\1>/g, '')
        .replace(/<(ul|ol)(?: [^>]*)?>\s*<\/\1>/g, '')
        .replace(/<br>(\s*)<\/p>/g, '$1</p>');
    } while (html !== prev);
    return html.replace(/^(\s|<br>)+|(\s|<br>)+$/g, '').trim();
  }

  /* ---------------------------------------------------------------- edit ops */

  const SEP = '\u241f';
  const secKey = (s) => (s.group ? s.group + SEP + s.name : s.name);
  const clone = (o) => JSON.parse(JSON.stringify(o));
  function newId(rand) {
    const bytes = rand ? rand(5) : Array.from({ length: 5 }, () => Math.floor(Math.random() * 256));
    return 'n' + Array.from(bytes, b => b.toString(16).padStart(2, '0')).join('');
  }
  function findCard(deck, id) {
    for (const s of deck.sections) { const i = s.cards.findIndex(c => c.id === id); if (i >= 0) return { sec: s, i, card: s.cards[i] }; }
    return null;
  }
  const findSec = (deck, key) => deck.sections.find(s => secKey(s) === key) || null;
  function cardFrom(op) {
    const c = { id: op.id, prompt: htmlToText(op.promptHtml) || '(untitled)', promptHtml: op.promptHtml || '', answerHtml: op.answerHtml || '' };
    if (op.label) c.label = op.label;
    return c;
  }
  function insertAt(list, item, beforeId) {
    const i = beforeId == null ? -1 : list.findIndex(x => x.id === beforeId);
    if (i < 0) list.push(item); else list.splice(i, 0, item);
  }

  /* Apply one op in place. Returns true if it changed the deck, false if it no longer applies
   * (e.g. editing a card that was deleted on another device). */
  function applyOp(deck, op) {
    switch (op.t) {
      case 'edit': {
        const f = findCard(deck, op.id); if (!f) return false;
        const c = f.card;
        if ('promptHtml' in op) { c.promptHtml = op.promptHtml; c.prompt = htmlToText(op.promptHtml) || '(untitled)'; delete c.imagePrompt; }
        if ('answerHtml' in op) c.answerHtml = op.answerHtml;
        if ('label' in op) { if (op.label) c.label = op.label; else delete c.label; }
        return true;
      }
      case 'add': {
        if (findCard(deck, op.id)) return false;
        let sec = findSec(deck, op.sec);
        if (!sec) { if (!op.secName) return false; sec = { name: op.secName, cards: [] }; if (op.group) sec.group = op.group; deck.sections.push(sec); }
        insertAt(sec.cards, cardFrom(op), op.before);
        return true;
      }
      case 'del': {
        const f = findCard(deck, op.id); if (!f) return false;
        f.sec.cards.splice(f.i, 1);
        deck.trash = deck.trash || [];
        deck.trash.unshift({ card: f.card, sec: secKey(f.sec), group: f.sec.group || '', name: f.sec.name, index: f.i, at: op.at || 0 });
        if (deck.trash.length > 200) deck.trash.length = 200;
        return true;
      }
      case 'restore': {
        const ti = (deck.trash || []).findIndex(x => x.card.id === op.id); if (ti < 0 || findCard(deck, op.id)) return false;
        const [t] = deck.trash.splice(ti, 1);
        let sec = findSec(deck, t.sec);
        if (!sec) { sec = { name: t.name, cards: [] }; if (t.group) sec.group = t.group; deck.sections.push(sec); }
        sec.cards.splice(Math.min(t.index, sec.cards.length), 0, t.card);
        return true;
      }
      case 'purge': {
        const ti = (deck.trash || []).findIndex(x => x.card.id === op.id); if (ti < 0) return false;
        deck.trash.splice(ti, 1); return true;
      }
      case 'move': {
        const f = findCard(deck, op.id); const to = findSec(deck, op.sec); if (!f || !to || op.before === op.id) return false;
        f.sec.cards.splice(f.i, 1);
        insertAt(to.cards, f.card, op.before);
        return true;
      }
      case 'addSec': {
        const s = { name: op.name, cards: [] }; if (op.group) s.group = op.group;
        if (!op.name || findSec(deck, secKey(s))) return false;
        const i = op.after == null ? -1 : deck.sections.findIndex(x => secKey(x) === op.after);
        if (i < 0) deck.sections.push(s); else deck.sections.splice(i + 1, 0, s);
        return true;
      }
      case 'renameSec': {
        const s = findSec(deck, op.sec); if (!s || !op.name) return false;
        const k = secKey({ group: s.group, name: op.name });
        if (k !== op.sec && findSec(deck, k)) return false;
        s.name = op.name;
        for (const t of deck.trash || []) if (t.sec === op.sec) { t.sec = k; t.name = op.name; } // deleted cards follow
        return true;
      }
      case 'renameGroup': {
        if (!op.to || op.to === op.group) return false;
        const secs = deck.sections.filter(s => (s.group || '') === op.group); if (!secs.length) return false;
        if (deck.sections.some(s => s.group === op.to)) return false;
        const rename = (g, n) => ({ group: op.to, name: n === g ? op.to : n });
        // the unit's own section ("General") takes the new name too, so it must not clash with a sibling
        const keys = secs.map(s => secKey(rename(s.group, s.name)));
        if (new Set(keys).size !== keys.length) return false;
        for (const s of secs) Object.assign(s, rename(s.group, s.name));
        for (const t of deck.trash || []) if ((t.group || '') === op.group) { Object.assign(t, rename(t.group, t.name)); t.sec = secKey(t); }
        return true;
      }
      case 'moveSec': {
        const i = deck.sections.findIndex(x => secKey(x) === op.sec); if (i < 0 || op.before === op.sec) return false;
        const [s] = deck.sections.splice(i, 1);
        const j = op.before == null ? -1 : deck.sections.findIndex(x => secKey(x) === op.before);
        if (j < 0) deck.sections.push(s); else deck.sections.splice(j, 0, s);
        return true;
      }
      case 'delSec': {
        const i = deck.sections.findIndex(x => secKey(x) === op.sec); if (i < 0 || deck.sections[i].cards.length) return false;
        deck.sections.splice(i, 1); return true;
      }
      default: return false;
    }
  }

  /* A new deck with the ops applied (the input is not changed), plus the ops that no longer applied. */
  function applyOps(deck, ops) {
    const d = clone(deck);
    const skipped = [];
    let changed = false;
    for (const op of ops || []) { if (applyOp(d, op)) changed = true; else skipped.push(op); }
    if (changed) d.editedInApp = true;
    d.cardCount = d.sections.reduce((n, s) => n + s.cards.length, 0);
    return { deck: d, skipped };
  }

  /* One line for a commit message: "edit 2 cards, add 1 card, move 3 cards". */
  function describeOps(ops) {
    const names = { edit: 'edit', add: 'add', del: 'delete', restore: 'restore', purge: 'purge', move: 'move', addSec: 'add section', renameSec: 'rename section', renameGroup: 'rename unit', moveSec: 'move section', delSec: 'delete section' };
    const cardOps = new Set(['edit', 'add', 'del', 'restore', 'purge', 'move']);
    const counts = new Map();
    for (const op of ops) { const k = op.t; counts.set(k, (counts.get(k) || new Set()).add(op.id || op.sec || op.group || op.name)); }
    return [...counts].map(([t, s]) => cardOps.has(t) ? `${names[t] || t} ${s.size} card${s.size === 1 ? '' : 's'}` : `${names[t] || t}${s.size > 1 ? ' ×' + s.size : ''}`).join(', ');
  }

  /* ---------------------------------------------------------------- GitHub save */

  function utf8ToB64(str) {
    const bytes = new TextEncoder().encode(str);
    let bin = ''; for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
    return btoa(bin);
  }
  function b64ToUtf8(b64) {
    const bin = atob(String(b64).replace(/\s+/g, ''));
    const bytes = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return new TextDecoder().decode(bytes);
  }

  class SaveError extends Error {
    constructor(kind, message, status) { super(message); this.kind = kind; this.status = status; }
  }

  /* Save queued ops for one test file: read the latest file from GitHub, apply the ops, write it back
   * with the sha it was read at. If someone else saved in between (409/422), read again and retry.
   * cfg: { fetch, api, owner, repo, branch, token, path, ops, message }
   * Returns { deck, skipped, commit }. Throws SaveError with kind 'auth' | 'offline' | 'conflict' | 'http'. */
  async function saveToGitHub(cfg) {
    const base = `${cfg.api}/repos/${cfg.owner}/${cfg.repo}/contents/${cfg.path.split('/').map(encodeURIComponent).join('/')}`;
    const headers = { Accept: 'application/vnd.github+json', Authorization: 'Bearer ' + cfg.token, 'X-GitHub-Api-Version': '2022-11-28' };
    const call = async (url, opts) => {
      let res;
      try { res = await cfg.fetch(url, { cache: 'no-store', ...opts, headers: { ...headers, ...(opts && opts.headers) } }); }
      catch (e) { throw new SaveError('offline', 'Network error: ' + e.message); }
      const hdr = (k) => (res.headers && res.headers.get ? res.headers.get(k) : null);
      if ((res.status === 403 || res.status === 429) && (hdr('x-ratelimit-remaining') === '0' || hdr('retry-after'))) throw new SaveError('rate', 'GitHub rate limit; will retry later', res.status);
      if (res.status === 401 || res.status === 403) throw new SaveError('auth', 'GitHub refused the token (' + res.status + ')', res.status);
      return res;
    };
    for (let attempt = 1; attempt <= 4; attempt++) {
      const got = await call(base + '?ref=' + encodeURIComponent(cfg.branch) + '&t=' + Date.now());
      if (!got.ok) throw new SaveError('http', 'Could not read ' + cfg.path + ' (' + got.status + ')', got.status);
      const meta = await got.json();
      if (!meta.content) throw new SaveError('http', cfg.path + ' is too large to save through the GitHub API (over 1 MB)');
      const remote = JSON.parse(b64ToUtf8(meta.content));
      const { deck, skipped } = applyOps(remote, cfg.ops);
      deck.rev = (remote.rev || 0) + 1;
      deck.editedAt = new Date(cfg.now ? cfg.now() : Date.now()).toISOString().replace(/\.\d+Z$/, 'Z');
      const put = await call(base, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: cfg.message, content: utf8ToB64(JSON.stringify(deck, null, 1)), sha: meta.sha, branch: cfg.branch }),
      });
      if (put.status === 409) continue; // the file changed since we read it: re-read and re-apply
      if (put.status === 422) {
        const msg = await put.json().then(j => j.message || '', () => '');
        if (/sha/i.test(msg)) continue;
        throw new SaveError('http', 'GitHub rejected the save (422: ' + msg + ')', 422);
      }
      if (!put.ok) throw new SaveError('http', 'Could not save ' + cfg.path + ' (' + put.status + ')', put.status);
      const body = await put.json();
      return { deck, skipped, commit: body.commit && body.commit.sha };
    }
    throw new SaveError('conflict', 'The file kept changing while saving; will try again');
  }

  /* Which copy of a test to show: the one from the website, or the copy this device saved last if
   * the website hasn't caught up with it yet (GitHub Pages can lag a few minutes). */
  function newerDeck(fetched, saved) {
    if (saved && fetched && saved.key === fetched.key && (saved.rev || 0) > (fetched.rev || 0)) return saved;
    return fetched;
  }

  /* ---------------------------------------------------------------- export */

  /* The test as an HTML document in the shape of a Google Docs export, so tools/import_doc.py reads
   * it back (and Google Docs opens it): tables of prompt | answer | label rows, Heading 1 rows for
   * units, Heading 2 rows for sections, inline colours moved into CSS classes. A run of sections
   * without a unit gets its own table. base: the site URL (ending in /) to make image links absolute. */
  function exportHtml(deck, base) {
    const classes = new Map();
    const classify = (html) => String(html || '')
      .replace(/<mark\b/g, '<span').replace(/<\/mark>/g, '</span>') // Google Docs marks highlights as styled spans
      .replace(/ src="img\//g, ` src="${base || ''}img/`)              // full URLs so images load from a downloaded file
      .replace(/<(ul|ol) class="l(\d)"/g, '<$1 class="lst-kix_export-$2"')  // list level, as Google Docs names it
      .replace(/ style="([^"]*)"/g, (m, css) => {
      if (!classes.has(css)) classes.set(css, 'c' + (classes.size + 1));
      return ` class="${classes.get(css)}"`;
    });
    const tables = [];
    let rows = null, group;
    for (const s of deck.sections) {
      const g = s.group || '';
      if (!rows || g !== group) {
        rows = []; tables.push(rows); group = g;
        if (g) rows.push(`<tr><td><h1>${escText(g)}</h1></td><td></td></tr>`);
      }
      rows.push(`<tr><td><h2>${escText(s.name)}</h2></td><td></td></tr>`);
      for (const c of s.cards) rows.push(`<tr><td>${classify(c.promptHtml || escText(c.prompt))}</td><td>${classify(c.answerHtml)}</td>${c.label ? `<td>${escText(c.label)}</td>` : ''}</tr>`);
    }
    const css = [...classes].map(([decl, cls]) => `.${cls}{${decl}}`).join('\n');
    return `<!doctype html><html><head><meta charset="utf-8"><title>${escText(deck.title)}</title>
<style>table{border-collapse:collapse}td{border:1px solid #ccc;padding:6px;vertical-align:top}h1,h2{margin:0}
${css}</style></head>
<body>${tables.map(r => `<table>\n${r.join('\n')}\n</table>`).join('\n<p></p>\n')}</body></html>`;
  }

  const NFCore = {
    pruneSession, sanitizeHtml, htmlToText, applyOp, applyOps, describeOps, newId, secKey,
    saveToGitHub, SaveError, newerDeck, utf8ToB64, b64ToUtf8, exportHtml,
  };
  if (typeof module !== 'undefined' && module.exports) module.exports = NFCore;
  else root.NFCore = NFCore;
})(typeof window !== 'undefined' ? window : this);
