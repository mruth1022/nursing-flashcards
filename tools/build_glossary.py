#!/usr/bin/env python3
"""Build a glossary for the app from a Markdown glossary.

Usage:
  python3 tools/build_glossary.py <guide.md> --name psych \
      --decks "Psych Units 5-12 Flashcards,Custom - Psych Exam 2 Flashcards"

Reads every line of the form `- **Term**: definition (source)` under the first heading that
contains "Glossary" (or the whole file if there is none) and writes:
  * docs/glossary/<name>.json   the terms, with aliases, definition HTML and source
  * docs/glossary/index.json    which tests use which glossary (other glossaries are kept)

Term names:
  * "A / B" gives two names for the same entry.
  * "Long name (ABC)" also matches the acronym ABC when it starts with the same letter, and
    "ABC (long name)" also matches the long name.
  * "Developmental (maturational) crisis" matches "Developmental crisis" and "maturational crisis".
  * Any other "(...)" is a qualifier and is dropped for matching: "Autonomy (ethical principle)"
    matches "Autonomy".
  * All-caps names (acronyms) match case-sensitively in the app; everything else ignores case.
tools/glossary_overrides.json, per glossary name:
  * "exclude": whole entries to leave out.
  * "excludeNames": names never matched in card text (everyday words like "Mood"); the entry stays.
  * "dropNames": {"Term": ["name"]} removes one name from one entry.
  * "aliases": {"Term": ["extra name"]} adds names the rules above can't infer.

Stdlib only. Python 3.9+.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENTRY_RE = re.compile(r"^\s*[-*]\s+\*\*(.+?)\*\*\s*:?\s*(.*)$")
SOURCE_HINT = re.compile(r"Boyd|ATI|Townsend|Syllabus|Lecture|Unit|general knowledge|Psych Notes|DSM", re.I)
QUALIFIER_START = re.compile(r"^(vs\.?|e\.g\.|i\.e\.|see|aka|also|old|formerly)\b", re.I)


def glossary_lines(md: str) -> list[str]:
    lines = md.splitlines()
    start = next((i for i, l in enumerate(lines) if l.startswith("#") and "glossary" in l.lower()), None)
    if start is None:
        return lines
    level = len(lines[start]) - len(lines[start].lstrip("#"))
    out = []
    for l in lines[start + 1:]:
        m = re.match(r"^(#+)\s", l)
        if m and len(m.group(1)) <= level:
            break
        out.append(l)
    return out


def inline_md(text: str) -> str:
    """Escape, then turn **bold** and *italic* into HTML."""
    t = html.escape(text, quote=False)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", t)
    return t


def split_source(defn: str) -> tuple[str, str]:
    """Peel a trailing '(Boyd 7e ...; Unit 4)' or '*(general knowledge; Unit 1)*' off the definition."""
    m = re.search(r"\s*\*?\(([^()]*(?:\([^()]*\)[^()]*)*)\)\*?\s*\.?\s*$", defn)
    if m and SOURCE_HINT.search(m.group(1)):
        return defn[: m.start()].rstrip(), m.group(1).strip()
    return defn.strip(), ""


def _is_acronym(s: str) -> bool:
    """'TD', 'AChEIs', 'C-SSRS', 'PHQ-9': mostly capitals, no spaces."""
    return bool(re.fullmatch(r"[A-Za-z0-9&\-]{2,10}", s)) and sum(ch.isupper() for ch in s) >= 2


def names_for(term: str) -> list[str]:
    """The strings that should link to this entry (see the module docstring)."""
    names: list[str] = []
    for part in [p.strip() for p in term.split(" / ") if p.strip()]:
        m = re.match(r"^(.*?)\s*\(([^()]+)\)\s*$", part)
        if m:  # trailing "(...)"
            base, inner = m.group(1).strip(), m.group(2).strip()
            names.append(base)
            if _is_acronym(inner) and inner[0].lower() == base[0].lower():
                names.append(inner)  # "Delirium tremens (DTs)"
            elif _is_acronym(base) and not QUALIFIER_START.match(inner):
                names.append(inner.split(",")[0].strip())  # "PTSD (posttraumatic stress disorder)"
            continue  # otherwise "(...)" is a qualifier: "Autonomy (ethical principle)"
        m = re.match(r"^(.*?)\s*\(([^()]+)\)\s*(.+)$", part)
        if m:  # "(...)" in the middle: "Developmental (maturational) crisis"
            before, inner, after = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
            names.append(f"{before} {after}")
            if re.fullmatch(r"[a-zé]+", inner):
                names.append(" ".join(before.split()[:-1] + [inner, after]))  # "maturational crisis"
            continue
        names.append(part)
    seen, out = set(), []
    for n in names:
        k = n.lower()
        if n and k not in seen and (len(n) >= 3 or _is_acronym(n)):
            seen.add(k)
            out.append(n)
    return out


def build(md: str, overrides: dict) -> list[dict]:
    exclude = {t.lower() for t in overrides.get("exclude", [])}
    extra = {k.lower(): v for k, v in overrides.get("aliases", {}).items()}
    never = {n.lower() for n in overrides.get("excludeNames", [])}
    drop = {k.lower(): {n.lower() for n in v} for k, v in overrides.get("dropNames", {}).items()}
    entries = []
    for line in glossary_lines(md):
        m = ENTRY_RE.match(line)
        if not m:
            continue
        term, rest = m.group(1).strip(), m.group(2).strip()
        if not rest or term.lower() in exclude:
            continue
        defn, source = split_source(rest)
        defn = re.sub(r"\s*See Part [^.;]*[.;]?", "", defn).strip()  # pointers into the study guide, not the app
        if not defn:
            continue  # the entry was only a pointer ("ADHD agents: See Part 1D ...")
        gone = never | drop.get(term.lower(), set())
        names = [n for n in names_for(term) if n.lower() not in gone]
        names += [n for n in extra.get(term.lower(), []) if n.lower() not in {x.lower() for x in names}]
        entries.append({"term": term, "names": names, "html": inline_md(defn), "source": source})
    return entries


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", help="Markdown file containing the glossary")
    ap.add_argument("--name", required=True, help="Glossary id, used as the file name (e.g. psych)")
    ap.add_argument("--title", help="Shown in the app (defaults to the name)")
    ap.add_argument("--decks", required=True, help="Comma-separated test titles (or keys) that use this glossary")
    ap.add_argument("--cards", default=str(ROOT / "docs" / "cards.json"))
    ap.add_argument("--out-dir", default=str(ROOT / "docs" / "glossary"))
    ap.add_argument("--overrides", default=str(ROOT / "tools" / "glossary_overrides.json"))
    args = ap.parse_args(argv)

    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", args.name):
        raise SystemExit("--name must be lowercase letters, digits, - or _")
    ov_path = Path(args.overrides)
    overrides = json.loads(ov_path.read_text(encoding="utf-8")).get(args.name, {}) if ov_path.exists() else {}
    entries = build(Path(args.source).read_text(encoding="utf-8"), overrides)
    if not entries:
        print("No glossary entries found (expected lines like '- **Term**: definition').", file=sys.stderr)
        return 2

    decks = json.loads(Path(args.cards).read_text(encoding="utf-8")).get("decks", [])
    keys = []
    for want in [w.strip() for w in args.decks.split(",") if w.strip()]:
        d = next((d for d in decks if want in (d.get("title"), d.get("key"))), None)
        if not d:
            raise SystemExit(f"No test called {want!r} in {args.cards}. Tests: " + ", ".join(x["title"] for x in decks))
        keys.append(d["key"])

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    (out_dir / f"{args.name}.json").write_text(
        json.dumps({"name": args.name, "generatedAt": now, "terms": entries}, ensure_ascii=False, indent=1), encoding="utf-8")
    idx_path = out_dir / "index.json"
    idx = json.loads(idx_path.read_text(encoding="utf-8")) if idx_path.exists() else {"glossaries": []}
    idx["glossaries"] = [g for g in idx["glossaries"] if g["name"] != args.name]
    idx["glossaries"].append({"name": args.name, "title": args.title or args.name, "file": f"{args.name}.json", "decks": keys})
    idx_path.write_text(json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")

    n_names = sum(len(e["names"]) for e in entries)
    print(f"Glossary '{args.name}': {len(entries)} terms ({n_names} names to match) -> {out_dir / (args.name + '.json')}")
    print("Used by: " + ", ".join(next(d["title"] for d in decks if d["key"] == k) for k in keys))
    return 0


if __name__ == "__main__":
    sys.exit(main())
