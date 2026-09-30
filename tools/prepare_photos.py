#!/usr/bin/env python3
"""
Resize photos for the cheer-up feature and strip metadata.

  python3 tools/prepare_photos.py <src_dir_or_files...> --who balto|us [--max 1400] [--quality 80]

Writes docs/cheer/img/<who>-NN.jpg and rebuilds docs/cheer/manifest.json from what is on disk.
HEIC is converted with macOS `sips` first; everything is auto-rotated (EXIF orientation)
and re-saved through Pillow with no EXIF/GPS.
"""
import argparse, hashlib, json, subprocess, sys, tempfile
from pathlib import Path
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "cheer" / "img"
MANIFEST = ROOT / "docs" / "cheer" / "manifest.json"
IMG_EXT = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp", ".gif"}


def load_image(path: Path) -> Image.Image:
    if path.suffix.lower() in (".heic", ".heif"):
        tmp = Path(tempfile.mkdtemp()) / (path.stem + ".jpg")
        subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "95", str(path), "--out", str(tmp)],
                       check=True, capture_output=True)
        return Image.open(tmp)
    return Image.open(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sources", nargs="+")
    ap.add_argument("--who", required=True, choices=["balto", "us"])
    ap.add_argument("--max", type=int, default=1400)
    ap.add_argument("--quality", type=int, default=80)
    a = ap.parse_args()

    files = []
    for s in a.sources:
        p = Path(s).expanduser()
        if p.is_dir():
            files += sorted(x for x in p.iterdir() if x.suffix.lower() in IMG_EXT)
        elif p.exists():
            files.append(p)
    if not files:
        sys.exit("no images found")

    OUT.mkdir(parents=True, exist_ok=True)
    existing = sorted(OUT.glob(f"{a.who}-*.jpg"))
    n = len(existing)
    seen = {hashlib.sha1(x.read_bytes()).hexdigest() for x in existing}
    written = 0
    for f in files:
        try:
            im = load_image(f)
            im = ImageOps.exif_transpose(im)
            im = im.convert("RGB")
            im.thumbnail((a.max, a.max), Image.LANCZOS)
        except Exception as e:  # noqa: BLE001
            print(f"skip {f.name}: {e}")
            continue
        n += 1
        dest = OUT / f"{a.who}-{n:02d}.jpg"
        im.save(dest, "JPEG", quality=a.quality, optimize=True, progressive=True)
        h = hashlib.sha1(dest.read_bytes()).hexdigest()
        if h in seen:
            dest.unlink(); n -= 1; continue
        seen.add(h); written += 1
        print(f"{f.name} -> {dest.name} {im.size[0]}x{im.size[1]} {dest.stat().st_size // 1024} KB")

    photos = []
    for p in sorted(OUT.glob("*.jpg")):
        who = p.name.split("-")[0]
        with Image.open(p) as im:
            w, h = im.size
        photos.append({"file": f"img/{p.name}", "who": who, "w": w, "h": h})
    MANIFEST.write_text(json.dumps({"photos": photos}, indent=1))
    total = sum(p.stat().st_size for p in OUT.glob("*.jpg"))
    print(f"\nwrote {written} new; manifest has {len(photos)} photos, {total / 1e6:.1f} MB total")


if __name__ == "__main__":
    main()
