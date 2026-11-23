# Nursing flashcards

A zero-server flashcard site. Cards come from a Google Doc table (prompt | answer), the site is
static HTML/JS hosted on GitHub Pages, and progress lives in each browser with a sync link to
move it between devices.

* Live site: https://mruth1022.github.io/nursing-flashcards/
* Repo: https://github.com/mruth1022/nursing-flashcards (public, Pages serves the `docs/` folder)

Everything below is run from a terminal inside this folder:

```bash
cd ~/dev/nursing-flashcards
```

Requirements: Python 3.9+ (macOS has it), `git`. The photo script also needs Pillow
(`python3 -m pip install pillow`) and macOS `sips` for HEIC files.

---

## 1. Update the cards after the doc changes

The doc must be shared as **Anyone with the link can view**. Pull first: edits made in the app are
commits on GitHub, and the import stops if this checkout is behind.

```bash
git pull
python3 tools/import_doc.py "https://docs.google.com/document/d/1dASQk4UBi9N3WojeGGZ-XcsBUPzvs01u0pl2h1urGf0/edit"
git add -A && git commit -m "Update cards" && git push
```

Once a test has been edited in the app, its Google Doc is retired: the import refuses to overwrite
it (see section 8).

The site updates about a minute after the push. The script prints the sections and card counts it
found plus any warnings (empty answers, merged rows). Hard-refresh the browser if the old deck
still shows.

## 2. Add a second test (another Google Doc)

Each doc becomes a separate **Test** in the app, named after the doc title (a trailing
"- Flashcards" is dropped). A Test picker appears at the top of Home, Stats and Browse once there
is more than one.

```bash
python3 tools/import_doc.py "https://docs.google.com/document/d/<OTHER_DOC_ID>/edit"
git add -A && git commit -m "Add <test name>" && git push
```

* Re-running the import for a doc **replaces** that test and keeps the others. Each test is its own
  file in `docs/decks/`, listed in `docs/decks/index.json`; each import raises the test's `rev`.
* A test that has been **edited in the app** is not re-imported (that would overwrite her edits);
  the import stops with a message. `--force` replaces it anyway.
* `--fresh` drops every other test and keeps only the one being imported (refused if that would
  delete a test edited in the app, unless `--force`).
* `--title "Exam 3"` overrides the title taken from the doc.
* `--label-duplicates` adds the section name to repeated prompts ("Panic Disorder (Anxiety Disorders)"), or the
  answer's pairing ("Interactions! (Antipsychotics + ?)") when the repeats share a section. Progress is kept, and the
  setting is remembered for that test on later re-imports (`--no-label-duplicates` turns it off).

## 3. How the doc is read

* Every table in the doc is a set of cards: column 1 = prompt, column 2 = answer. An optional
  column 3 becomes a small label on the card.
* **Units and sections come from heading rows.** In the doc, make the prompt cell of a row a
  Google Docs *Heading 1* to start a unit (e.g. "Unit 1") and a *Heading 2* to start a section
  (e.g. "Heart Failure"). Each runs until the next heading row or the end of that table. Leave the
  answer cell empty and the row is only a label; give it an answer and it is also a card. If a doc
  uses just one heading level, those rows are plain sections with no units.
* **A Heading 1 paragraph between tables also works as a unit.** If the table below it has its own
  Heading 2 rows, the paragraph becomes the unit and any rows before the first Heading 2 appear as
  "General" in it. A table with no heading rows of its own just becomes a plain section named after
  the paragraph above it.
* Cards that sit directly under a unit heading with no section heading show up as "General" in
  that unit. A table with no heading rows at all gets a name from `--sections` (one name per table
  in document order) or, failing that, "Part N".
* A first row like "Term | Definition" is skipped automatically. Force it with `--skip-header` or
  keep it with `--keep-header`.
* Prompt cells that contain only an image become "identify this" cards.
* Kept from the doc: bold, italic, underline, strikethrough, highlights, text colours, bullets,
  numbering, line breaks, links, images.
* Rows with both cells empty are ignored. A row with an empty prompt but an answer is appended to
  the previous card's answer.

Fallback if the doc can't be shared: in Google Docs choose **File ▸ Download ▸ Web page
(.html, zipped)** and pass the `.zip` or `.html` path instead of the URL.

## 4. Change the cheer-up messages or photos

**Messages** are in `docs/cheer/messages.json`: two lists, `balto` and `us`. Edit the text, then:

```bash
git add -A && git commit -m "Update cheer messages" && git push
```

**Photos** go through a script that converts HEIC, fixes rotation, resizes to 1400px and strips
all metadata (including GPS). Point it at files or a folder and say whose they are:

```bash
python3 tools/prepare_photos.py ~/Desktop/new-balto-photos --who balto
python3 tools/prepare_photos.py ~/Desktop/IMG_1234.HEIC ~/Desktop/IMG_1235.jpg --who us
git add -A && git commit -m "Add photos" && git push
```

Files land in `docs/cheer/img/` and `docs/cheer/manifest.json` is rebuilt from what is on disk.
To remove a photo, delete its file from `docs/cheer/img/`, re-run the script on any folder (or an
empty one) to rebuild the manifest, and push.

When it shows: a "Feeling discouraged? 💙" pill on Home and on round summaries, and a small nudge
in the study status line after three misses in a row (at most once every four minutes).

## 5. Run locally (optional)

```bash
python3 -m http.server 8765 --directory docs
```

Then open http://localhost:8765. Useful to preview an import before pushing.

## 6. Tests

```bash
python3 -m unittest discover tests
node --test tests/
```

The Node tests cover `docs/core.js`, the app logic that has no DOM (e.g. keeping a study session
going when some of its cards are deleted).

## 7. Glossary (underlined terms)

Terms from a glossary are underlined on cards (study and Browse) for the tests that use it; tap one
to see its definition. Home has an Underline / Off switch for tests with a glossary.

The psych glossary comes from the study guide's "Glossary of Key Terms" (`- **Term**: definition (source)`
lines). Rebuild it after the guide changes:

```bash
python3 tools/build_glossary.py ~/Desktop/logs/20261119-0015-psych-nursing-study-guide-v2.md --name psych --title "Psych glossary" --decks "Psych Units 5-12 Flashcards,Custom - Psych Exam 2 Flashcards"
```

* `--decks` lists the tests (by title) that get underlines. Other tests are untouched, and the app
  only downloads a glossary when one of its tests is open.
* `tools/glossary_overrides.json` turns off everyday words ("Mood", "Memory", …) and adds synonyms
  the script can't work out (e.g. "dysthymia" for Persistent depressive disorder).
* Matching: whole words, optional plural "s", longest term first, first occurrence per term on each
  side of a card. Acronyms (TD, EPS) must match the capitals exactly. On the front of a card, a term
  that is most of the prompt isn't underlined, so tapping it can't give the answer away.

## 8. Editing in the app

Browse ▸ **✎ Edit cards** turns on editing for the selected test:

* ✎ edits a card (prompt, answer, optional label) in a rich-text editor with bold, italic,
  underline, strikethrough, lists, indent, her highlight colours and text colours. Pasting from
  Google Docs keeps the formatting. The ✎ on the back of a card while studying opens the same editor.
* 🗑 deletes a card (Undo in the message, or ⋯ ▸ Recently deleted later). ↕ moves it up or down or
  into another section. **+ Card** adds one.
* ⋯ on a section renames it, moves it, adds a section below, renames or moves its unit, or deletes it
  once it is empty. **+ Add section** / **+ Add unit** are at the end of the list.
* ⋯ in the header: Recently deleted, History of this test (links to each save on GitHub), and
  Download as HTML (a backup that opens in Google Docs; `import_doc.py` reads it back).

**How saving works.** Each change is queued on the device and shown at once. A few seconds after the
last change (or when the page is hidden, or the connection returns) the app reads the test's file
from GitHub, re-applies the queued changes to it and commits it to `main`. If the other device saved
in between, it reads again and re-applies, so edits from the phone and the laptop combine. Pages
redeploys within a couple of minutes; until then the device shows the copy it saved. Card IDs never
change when a card is edited, so study progress is kept. The status chip says where things stand
(saved, waiting, offline, paused).

**Turning on saving for a device (once per device).**

1. Create a fine-grained token at https://github.com/settings/personal-access-tokens/new: Repository
   access ▸ Only select repositories ▸ `nursing-flashcards`; Permissions ▸ Contents ▸ Read and write;
   expiry up to a year.
2. Store it in the Keychain (it prompts for the token, so it stays out of the shell history):

   ```bash
   security add-generic-password -s nursing-flashcards-token -a "$USER" -w
   ```

3. Make the link and text it to her privately. She taps it once on her phone and once on her laptop,
   then can delete the message:

   ```bash
   python3 tools/make_setup_link.py
   ```

The link is `…/nursing-flashcards/#setup=<token>`; the part after `#` never reaches a server, and the
app removes it from the address bar immediately. Never commit the token or put it in the app's code:
the repo and the site are public. If a device is lost or the token expires, regenerate it on GitHub
and send a new link. Sync ▸ "Forget this device" removes the token from one device. Edits made
before a device is set up stay on it and are saved once it is.

**Doc imports after app edits.** `import_doc.py` refuses to re-import a test with `"editedInApp": true`
(it would overwrite her edits) unless given `--force`, and refuses to run on a checkout that is
behind GitHub. To restore an older version of a test, check out that file from an earlier commit
(History shows them) and push it.

**Testing saving locally** without a token: run `python3 tests/mock_github.py` (a stand-in for the
GitHub API on port 8766 that works on a temporary copy of `docs/decks/`), then in the browser console
of http://localhost:8765 run
`localStorage['nf.gh.dev'] = JSON.stringify({api: 'http://localhost:8766', owner: 'o', repo: 'r'}); location.hash = '#setup=test-token'`.
Saving is off on localhost unless `nf.gh.dev` is set.

## How progress and sync work

* Every answer is stored in the browser (`localStorage`). Nothing leaves the device.
* Sync ▸ "Copy sync link" (or Share…) produces a link with the compressed progress in the URL.
  Open it on another device and accept the merge. "Merge" keeps the newest answer per card from
  either device; "Replace" overwrites.
* Stats ▸ "Reset all progress" clears the device.
* Card identity is based on the prompt text when a doc is imported, so editing an answer in the doc
  keeps its progress and rewording a prompt makes it a new card. Edits made in the app never change
  a card's identity.

## Layout

```
docs/            GitHub Pages root: index.html, app.js, core.js, styles.css, img/, cheer/
docs/decks/      index.json (the tests, in order) + one <key>.json per test
docs/glossary/   index.json (which tests use which glossary) + one <name>.json per glossary
tools/           import_doc.py, build_glossary.py (+ glossary_overrides.json), make_setup_link.py,
                 prepare_photos.py, test sample
tests/           Python tests (importer, glossary, setup link, export round trip), Node tests (core.js),
                 mock_github.py (local stand-in for the GitHub API)
```

## If something goes wrong

* `Google returned HTTP 403/401`: the doc isn't shared as "Anyone with the link can view".
* `No cards found`: the content isn't in a two-column table.
* Site doesn't change after a push: wait a minute, then hard-refresh. Check
  https://github.com/mruth1022/nursing-flashcards/actions for a failed Pages build.
* `ModuleNotFoundError: PIL`: run `python3 -m pip install pillow`.
* `Not imported: GitHub has N newer commit(s)`: run `git pull`, then import again.
* `Not imported: '<test>' has been edited in the app`: that test's doc is retired; edit it in the app.
  `--force` replaces her edits with the doc.
* App says "Saving paused · ask Matt for a new link": the token was revoked or expired. Make a new one
  and a new link (section 8). Her queued edits are kept and save once the new link is opened.
