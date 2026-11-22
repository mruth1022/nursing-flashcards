// Run: node --test tests/
const test = require('node:test');
const assert = require('node:assert/strict');
const { pruneSession } = require('../docs/core.js');

const session = (over = {}) => ({
  config: { deck: 'd', mode: 'rounds' }, queue: ['a', 'b', 'c', 'd', 'e'], index: 2, round: 1, flipped: true,
  answers: [{ id: 'a', yes: true, round: 1, prev: null, reinserted: null }, { id: 'b', yes: false, round: 1, prev: null, reinserted: null }],
  roundYes: ['a'], roundNo: ['b'], seen: ['a', 'b'], firstYes: 1, firstNo: 1, startedAt: 1, ...over,
});
const without = (...gone) => (id) => !gone.includes(id);

test('nothing missing: same object back, untouched', () => {
  const s = session();
  assert.equal(pruneSession(s, () => true), s);
});

test('a card not reached yet is dropped; position, flip state and undo history of the rest are unchanged', () => {
  const s = session();
  const p = pruneSession(s, without('d'));
  assert.deepEqual(p.queue, ['a', 'b', 'c', 'e']);
  assert.equal(p.index, 2);
  assert.equal(p.flipped, true);
  assert.deepEqual(s.queue, ['a', 'b', 'c', 'd', 'e'], 'input not mutated');
});

test('an answered card is dropped: the index moves back, piles and first-answer counts follow, undo is cleared', () => {
  const p = pruneSession(session(), without('a'));
  assert.deepEqual(p.queue, ['b', 'c', 'd', 'e']);
  assert.equal(p.index, 1);
  assert.equal(p.queue[p.index], 'c', 'still on the same card');
  assert.deepEqual(p.roundYes, []);
  assert.deepEqual(p.seen, ['b']);
  assert.equal(p.firstYes, 0);
  assert.equal(p.firstNo, 1);
  assert.deepEqual(p.answers, []);
});

test('the card on screen is dropped: the next card shows, front side up', () => {
  const p = pruneSession(session(), without('c'));
  assert.equal(p.queue[p.index], 'd');
  assert.equal(p.flipped, false);
});

test('the last unanswered cards are dropped: the round ends on the summary', () => {
  const p = pruneSession(session(), without('c', 'd', 'e'));
  assert.deepEqual(p.queue, ['a', 'b']);
  assert.equal(p.index, 2);
  assert.equal(p.phase, 'summary');
});

test('every card is gone: no session', () => {
  assert.equal(pruneSession(session(), () => false), null);
  assert.equal(pruneSession(null, () => true), null);
});

test('a card reinserted later in the queue ("bring it back soon") is removed everywhere', () => {
  const s = session({ queue: ['a', 'b', 'c', 'b', 'e'], index: 2 });
  const p = pruneSession(s, without('b'));
  assert.deepEqual(p.queue, ['a', 'c', 'e']);
  assert.equal(p.queue[p.index], 'c');
  assert.deepEqual(p.roundNo, []);
});

// ---------------------------------------------------------------- sanitizer
const { sanitizeHtml, htmlToText, applyOps, describeOps, newId, saveToGitHub, newerDeck, utf8ToB64, b64ToUtf8, exportHtml } = require('../docs/core.js');

test('sanitizer keeps the formatting the importer produces, unchanged', () => {
  const html = '<p><mark style="background-color:#00ffff">1st Gen</mark> <span style="color:#ff0000"><b>EPS!</b></span></p><ul class="l0"><li>a</li></ul><ul class="l1"><li><i>b</i> <u>c</u></li></ul><ol class="l0" start="3"><li>d</li></ol><p>x<sup>2</sup> <s>old</s><br>next</p>';
  assert.equal(sanitizeHtml(html), html);
});

test('sanitizer removes scripts, event handlers, links and unknown attributes but keeps the text', () => {
  const out = sanitizeHtml('<p onclick="x()">Hi <a href="javascript:alert(1)">there</a><script>alert(1)</script><img src="x" onerror="alert(1)"><iframe src="//evil"></iframe></p><style>p{}</style>');
  assert.equal(out, '<p>Hi there</p>');
  assert.doesNotMatch(sanitizeHtml('<span style="color:red;background:url(javascript:alert(1))">t</span>'), /url|javascript/);
});

test('sanitizer turns Google Docs paste into the app format', () => {
  const gdocs = '<meta charset="utf-8"><b style="font-weight:normal;" id="docs-internal-guid-1"><p dir="ltr" style="line-height:1.38"><span style="font-size:11pt;color:#000000;background-color:transparent;font-weight:700;">Lithium</span><span style="font-size:11pt;color:#ff0000;background-color:#ffff00;font-weight:400;font-style:italic"> toxic</span></p><ul><li dir="ltr"><p dir="ltr"><span style="text-decoration:underline">tremor</span></p></li></ul></b>';
  assert.equal(sanitizeHtml(gdocs), '<p><b>Lithium</b><mark style="background-color:#ffff00"><span style="color:#ff0000"><i> toxic</i></span></mark></p><ul><li><u>tremor</u></li></ul>');
});

test('sanitizer: editor output (divs, rgb colours, nested lists, stray tags) is normalised', () => {
  assert.equal(sanitizeHtml('<div>one</div><div><br></div><div>two <span style="background-color: rgb(0, 255, 0);">hi</span></div>'), '<p>one</p><p>two <mark style="background-color:#00ff00">hi</mark></p>');
  assert.equal(sanitizeHtml('<ul><li>a<ul><li>b</li></ul></li></ul>'), '<ul><li>a<ul><li>b</li></ul></li></ul>');
  assert.equal(sanitizeHtml('<b>open <i>both'), '<b>open <i>both</i></b>');
  assert.equal(sanitizeHtml('a </i> b < c & d'), 'a  b &lt; c &amp; d');
  assert.equal(sanitizeHtml('<p><span style="color:#1b1f2a">plain</span> <span style="font-weight:bold">B</span></p>'), '<p>plain <b>B</b></p>');
});

test('sanitizer keeps only images already stored in img/', () => {
  assert.equal(sanitizeHtml('<img src="img/abc123.png" alt="x" onload="y"><img src="https://evil/x.png"><img src="img/../../x">'), '<img src="img/abc123.png" alt="" loading="lazy">');
});

test('htmlToText gives readable prompt text', () => {
  assert.equal(htmlToText('<p><b>Lithium</b> &amp; NSAIDs</p><ul><li>a</li><li>b</li></ul>'), 'Lithium & NSAIDs a b');
});

// ---------------------------------------------------------------- edit ops
const deck0 = () => ({
  key: 'k', title: 'T', rev: 3, cardCount: 4, sections: [
    { name: 'Meds', group: 'Unit 5', cards: [{ id: 'a', prompt: 'A', promptHtml: '<p>A</p>', answerHtml: '<p>1</p>' }, { id: 'b', prompt: 'B', promptHtml: '<p>B</p>', answerHtml: '<p>2</p>', label: 'verify' }] },
    { name: 'Unit 5', group: 'Unit 5', cards: [{ id: 'c', prompt: 'C', promptHtml: '<p>C</p>', answerHtml: '<p>3</p>' }] },
    { name: 'Dx', group: 'Unit 6', cards: [{ id: 'd', prompt: 'D', promptHtml: '<p>D</p>', answerHtml: '<p>4</p>' }] },
  ],
});
const ids = (d) => d.sections.map(s => `${s.group}|${s.name}:` + s.cards.map(c => c.id).join(','));

test('edit, add and delete; the input deck is not changed; count and editedInApp follow', () => {
  const d0 = deck0();
  const { deck, skipped } = applyOps(d0, [
    { t: 'edit', id: 'a', promptHtml: '<p><b>Akathisia</b> tx</p>', answerHtml: '<p>new</p>' },
    { t: 'edit', id: 'b', label: '' },
    { t: 'add', id: 'n1', sec: 'Unit 5␟Meds', before: 'b', promptHtml: '<p>New</p>', answerHtml: '<p>x</p>' },
    { t: 'del', id: 'c', at: 5 },
  ]);
  assert.deepEqual(skipped, []);
  assert.deepEqual(ids(deck), ['Unit 5|Meds:a,n1,b', 'Unit 5|Unit 5:', 'Unit 6|Dx:d']);
  assert.equal(deck.sections[0].cards[0].prompt, 'Akathisia tx');
  assert.equal(deck.sections[0].cards[2].label, undefined);
  assert.equal(deck.cardCount, 4);
  assert.equal(deck.editedInApp, true);
  assert.deepEqual(deck.trash.map(t => [t.card.id, t.sec, t.index]), [['c', 'Unit 5␟Unit 5', 0]]);
  assert.deepEqual(ids(d0), ['Unit 5|Meds:a,b', 'Unit 5|Unit 5:c', 'Unit 6|Dx:d']);
});

test('ops that no longer apply are skipped, not fatal (e.g. edited here, deleted on the other device)', () => {
  const { deck, skipped } = applyOps(deck0(), [{ t: 'del', id: 'a' }, { t: 'edit', id: 'a', answerHtml: 'x' }, { t: 'move', id: 'zz', sec: 'Unit 6␟Dx' }]);
  assert.equal(skipped.length, 2);
  assert.equal(deck.cardCount, 3);
});

test('no ops applied: editedInApp is not set', () => {
  assert.equal(applyOps(deck0(), [{ t: 'edit', id: 'nope', answerHtml: 'x' }]).deck.editedInApp, undefined);
});

test('restore puts a deleted card back where it was; purge removes it for good', () => {
  let d = applyOps(deck0(), [{ t: 'del', id: 'b' }, { t: 'del', id: 'a' }]).deck;
  d = applyOps(d, [{ t: 'restore', id: 'b' }]).deck;
  assert.deepEqual(ids(d)[0], 'Unit 5|Meds:b');
  d = applyOps(d, [{ t: 'purge', id: 'a' }]).deck;
  assert.deepEqual(d.trash, []);
  const again = applyOps(d, [{ t: 'restore', id: 'a' }]);
  assert.equal(again.skipped.length, 1);
});

test('regrouping: move cards, add/rename/move/delete sections, rename a unit', () => {
  let { deck, skipped } = applyOps(deck0(), [
    { t: 'move', id: 'd', sec: 'Unit 5␟Meds', before: 'a' },
    { t: 'move', id: 'b', sec: 'Unit 6␟Dx', before: null },
    { t: 'addSec', group: 'Unit 6', name: 'Meds 6', after: 'Unit 6␟Dx' },
    { t: 'renameSec', sec: 'Unit 6␟Dx', name: 'Diagnosis' },
    { t: 'moveSec', sec: 'Unit 6␟Meds 6', before: 'Unit 6␟Diagnosis' },
    { t: 'renameGroup', group: 'Unit 5', to: 'Unit 5 – Psychobiology' },
    { t: 'delSec', sec: 'Unit 5 – Psychobiology␟Unit 5 – Psychobiology' }, // was empty? no: holds c
  ]);
  assert.equal(skipped.length, 1);
  assert.equal(skipped[0].t, 'delSec');
  assert.deepEqual(ids(deck), ['Unit 5 – Psychobiology|Meds:d,a', 'Unit 5 – Psychobiology|Unit 5 – Psychobiology:c', 'Unit 6|Meds 6:', 'Unit 6|Diagnosis:b']);
  ({ deck, skipped } = applyOps(deck, [{ t: 'delSec', sec: 'Unit 6␟Meds 6' }, { t: 'renameSec', sec: 'Unit 6␟Diagnosis', name: 'Meds 6' }, { t: 'renameGroup', group: 'Unit 6', to: 'Unit 5 – Psychobiology' }]));
  assert.deepEqual(ids(deck).slice(2), ['Unit 6|Meds 6:b']);
  assert.equal(skipped.length, 1, 'renaming a unit onto an existing unit is refused');
});

test('describeOps summarises a batch for the commit message', () => {
  assert.equal(describeOps([{ t: 'edit', id: 'a' }, { t: 'edit', id: 'a' }, { t: 'edit', id: 'b' }, { t: 'move', id: 'c' }, { t: 'addSec', name: 'X' }]), 'edit 2 cards, move 1 card, add section');
});

test('newId is unique-looking and prefixed', () => {
  assert.match(newId(), /^n[0-9a-f]{10}$/);
  assert.equal(newId(() => [1, 2, 3, 4, 255]), 'n01020304ff');
});

// ---------------------------------------------------------------- GitHub save (fake API)
function fakeGitHub(initialDeck, { token = 'good', failPutTimes = 0, raceWith = null } = {}) {
  const gh = { content: JSON.stringify(initialDeck), sha: 'sha0', puts: [], races: 0 };
  let n = 0;
  gh.fetch = async (url, opts = {}) => {
    const auth = (opts.headers || {}).Authorization;
    const reply = (status, body) => ({ status, ok: status >= 200 && status < 300, json: async () => body });
    if (auth !== 'Bearer ' + token) return reply(401, { message: 'Bad credentials' });
    if (!opts.method || opts.method === 'GET') return reply(200, { sha: gh.sha, content: utf8ToB64(gh.content).replace(/(.{60})/g, '$1\n') });
    const body = JSON.parse(opts.body);
    if (raceWith && gh.races === 0) { gh.races++; gh.content = JSON.stringify(applyOps(JSON.parse(gh.content), raceWith).deck); gh.sha = 'sha-race'; }
    if (body.sha !== gh.sha || failPutTimes-- > 0) return reply(409, { message: 'sha mismatch' });
    gh.puts.push(body); gh.content = b64ToUtf8(body.content); gh.sha = 'sha' + (++n);
    return reply(200, { commit: { sha: 'c' + n } });
  };
  return gh;
}
const cfg = (gh, ops, extra = {}) => ({ fetch: gh.fetch, api: 'https://api.example', owner: 'o', repo: 'r', branch: 'main', token: 'good', path: 'docs/decks/k.json', ops, message: 'm', now: () => 0, ...extra });

test('save: reads, applies, writes with the sha it read; rev goes up; unicode survives', async () => {
  const gh = fakeGitHub(deck0());
  const r = await saveToGitHub(cfg(gh, [{ t: 'edit', id: 'a', answerHtml: '<p>Lithium – 1.5 mEq/L ↑ “toxic”</p>' }]));
  assert.equal(r.commit, 'c1');
  assert.equal(gh.puts.length, 1);
  assert.equal(gh.puts[0].sha, 'sha0');
  const saved = JSON.parse(gh.content);
  assert.equal(saved.rev, 4);
  assert.equal(saved.editedInApp, true);
  assert.equal(saved.sections[0].cards[0].answerHtml, '<p>Lithium – 1.5 mEq/L ↑ “toxic”</p>');
});

test('save: when the other device saved in between, both sets of changes end up in the file', async () => {
  const gh = fakeGitHub(deck0(), { raceWith: [{ t: 'edit', id: 'd', answerHtml: '<p>from laptop</p>' }] });
  await saveToGitHub(cfg(gh, [{ t: 'edit', id: 'a', answerHtml: '<p>from phone</p>' }]));
  const saved = JSON.parse(gh.content);
  assert.equal(saved.sections[0].cards[0].answerHtml, '<p>from phone</p>');
  assert.equal(saved.sections[2].cards[0].answerHtml, '<p>from laptop</p>');
});

test('save: a bad token is reported as auth, network failure as offline, endless conflicts as conflict', async () => {
  await assert.rejects(saveToGitHub(cfg(fakeGitHub(deck0()), [], { token: 'bad' })), e => e.kind === 'auth');
  await assert.rejects(saveToGitHub(cfg({ fetch: async () => { throw new TypeError('Failed to fetch'); } }, [])), e => e.kind === 'offline');
  await assert.rejects(saveToGitHub(cfg(fakeGitHub(deck0(), { failPutTimes: 99 }), [])), e => e.kind === 'conflict');
});

test('newerDeck prefers this device\'s saved copy only while the website is behind', () => {
  const site = { key: 'k', rev: 4 };
  assert.equal(newerDeck(site, { key: 'k', rev: 5 }).rev, 5);
  assert.equal(newerDeck(site, { key: 'k', rev: 4 }), site);
  assert.equal(newerDeck(site, null), site);
});

test('exportHtml writes heading rows and cards the importer can read back', () => {
  const html = exportHtml(deck0());
  assert.match(html, /<tr><td><h1>Unit 5<\/h1><\/td><td><\/td><\/tr>\n<tr><td><h2>Meds<\/h2><\/td><td><\/td><\/tr>\n<tr><td><p>A<\/p><\/td><td><p>1<\/p><\/td><\/tr>/);
  assert.match(html, /<td>verify<\/td>/);
});
