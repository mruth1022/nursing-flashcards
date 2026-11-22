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
