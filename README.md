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

The doc must be shared as **Anyone with the link can view**.

```bash
python3 tools/import_doc.py "https://docs.google.com/document/d/1dASQk4UBi9N3WojeGGZ-XcsBUPzvs01u0pl2h1urGf0/edit" \
  --sections "IV Calculations,Cardiac,Coagulation,Electrolytes,Hematology & Immunity"
git add -A && git commit -m "Update cards" && git push
```

The site updates about a minute after the push. The script prints the sections and card counts it
found plus any warnings (empty answers, merged rows). Hard-refresh the browser if the old deck
still shows.

## 2. Add a second test (another Google Doc)

Each doc becomes a separate **Test** in the app, named after the doc title (a trailing
"- Flashcards" is dropped). A Test picker appears at the top of Home, Stats and Browse once there
is more than one.

```bash
python3 tools/import_doc.py "https://docs.google.com/document/d/<OTHER_DOC_ID>/edit" \
  --sections "Name for table 1,Name for table 2"
git add -A && git commit -m "Add <test name>" && git push
```

* Re-running the import for a doc **replaces** that test and keeps the others.
* `--fresh` drops every other test and keeps only the one being imported.
* `--title "Exam 3"` overrides the title taken from the doc.

## 3. How the doc is read

* Every table in the doc is a set of cards: column 1 = prompt, column 2 = answer. An optional
  column 3 becomes a small label on the card.
* **Sections:** a row whose prompt is styled as a Google Docs *Heading 1–4* starts a new section
  that runs until the next heading row or the end of that table. Rows before the first heading row
  in a table get the table's default name from `--sections` (one name per table, in document
  order; leave an entry blank to keep the automatic name). Without `--sections` the default is a
  heading placed above the table in the doc, else "Part N".
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
python3 -m unittest tests.test_import
```

## How progress and sync work

* Every answer is stored in the browser (`localStorage`). Nothing leaves the device.
* Sync ▸ "Copy sync link" (or Share…) produces a link with the compressed progress in the URL.
  Open it on another device and accept the merge. "Merge" keeps the newest answer per card from
  either device; "Replace" overwrites.
* Stats ▸ "Reset all progress" clears the device.
* Card identity is based on the prompt text, so editing an answer in the doc keeps its progress;
  rewording a prompt makes it a new card.

## Layout

```
docs/            GitHub Pages root: index.html, app.js, styles.css, cards.json, img/, cheer/
tools/           import_doc.py, prepare_photos.py, sample export used by the tests
tests/           unit tests for the importer
```

## If something goes wrong

* `Google returned HTTP 403/401`: the doc isn't shared as "Anyone with the link can view".
* `No cards found`: the content isn't in a two-column table.
* Site doesn't change after a push: wait a minute, then hard-refresh. Check
  https://github.com/mruth1022/nursing-flashcards/actions for a failed Pages build.
* `ModuleNotFoundError: PIL`: run `python3 -m pip install pillow`.
