# Nursing flashcards

A zero-server flashcard site. Cards come from a Google Doc table (prompt | answer), the site is
static HTML/JS hosted on GitHub Pages, and progress lives in each browser with a sync link to
move it between devices.

## Re-import the cards after the doc changes

The doc must be shared as "Anyone with the link can view".

```bash
python3 tools/import_doc.py "https://docs.google.com/document/d/<DOC_ID>/edit" \
  --sections "IV Calculations,Cardiac,Coagulation,Electrolytes,Hematology & Immunity"
git add -A && git commit -m "Update cards" && git push
```

The site updates about a minute after the push.

* `--sections` names the tables in document order. Rows under a heading-styled prompt
  (Heading 1–4 in Google Docs) form their own section automatically, until the next heading row
  or the end of that table.
* Each doc is a separate "test" in the app, named after the doc title. Importing a second doc adds
  it alongside the first; re-importing the same doc replaces it. `--fresh` drops the others.
* `--title "..."` overrides the deck title. `--keep-header` / `--skip-header` override the
  header-row guess.
* Fallback if the doc can't be shared: File ▸ Download ▸ Web page (.html, zipped) and pass the
  `.zip` or `.html` path instead of the URL.

Images are written to `docs/img/` and referenced relatively; highlights, colours, bold, lists and
line breaks are preserved.

## Run locally

```bash
python3 -m http.server 8765 --directory docs
```

Then open http://localhost:8765.

## Tests

```bash
python3 -m unittest tests.test_import
```

## How progress and sync work

* Every answer is stored in the browser (`localStorage`). Nothing leaves the device.
* Sync ▸ "Copy sync link" (or Share…) produces a link with the compressed progress in the URL
  fragment. Open it on another device and accept the merge. "Merge" keeps the newest answer per
  card from either device; "Replace" overwrites.
* Stats ▸ "Reset all progress" clears the device.

## Layout

```
docs/          GitHub Pages root: index.html, app.js, styles.css, cards.json, img/
tools/         import_doc.py (stdlib only) and a sample export used by the tests
tests/         unit tests for the importer
```
