/* Pure helpers shared by app.js and the Node tests (tests/core.test.js). No DOM, no storage.
 * Loaded before app.js; exposed as window.NFCore in the browser and module.exports in Node.
 */
(function (root) {
  'use strict';

  /* An in-progress study session after some of its cards stopped existing (deleted in the doc or,
   * later, in the app). Drops just those cards instead of discarding the session.
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

  const NFCore = { pruneSession };
  if (typeof module !== 'undefined' && module.exports) module.exports = NFCore;
  else root.NFCore = NFCore;
})(typeof window !== 'undefined' ? window : this);
