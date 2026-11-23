#!/usr/bin/env python3
"""A tiny stand-in for the parts of the GitHub REST API the app uses, for testing saves locally.

  python3 tests/mock_github.py [--port 8766] [--token test-token]

Serves a temporary copy of docs/decks/ (the real files are never written):
  GET  /repos/<o>/<r>                         -> {"permissions": {"push": true}} for the right token
  GET  /repos/<o>/<r>/contents/<path>?ref=..  -> {"sha", "content" (base64)}
  PUT  /repos/<o>/<r>/contents/<path>         -> 409 if "sha" is stale, else writes and returns a commit
  GET  /repos/<o>/<r>/commits?path=<path>     -> the commits made through this server, newest first
Test hooks (no auth): GET /__mock/files, POST /__mock/edit {path, answerHtml, id} (simulates the
other device saving), POST /__mock/revoke (later requests get 401).
Point the app at it from a localhost page: localStorage['nf.gh.dev'] = JSON.stringify({api: 'http://localhost:8766', owner: 'o', repo: 'r'}).
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import shutil
import tempfile
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parent.parent


class State:
    def __init__(self, token: str):
        self.dir = Path(tempfile.mkdtemp(prefix="mockgh-"))
        shutil.copytree(ROOT / "docs" / "decks", self.dir / "docs" / "decks")
        self.token = token
        self.revoked = False
        self.commits: list[dict] = []

    def path(self, p: str) -> Path:
        full = (self.dir / p).resolve()
        if self.dir.resolve() not in full.parents:
            raise PermissionError(p)
        return full


def sha_of(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def make_handler(st: State):
    class H(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # quiet
            pass

        def send(self, code: int, body):
            data = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_OPTIONS(self):
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, PUT, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-GitHub-Api-Version, Accept")
            self.end_headers()

        def authed(self) -> bool:
            ok = not st.revoked and self.headers.get("Authorization") == "Bearer " + st.token
            if not ok:
                self.send(401, {"message": "Bad credentials"})
            return ok

        def body(self) -> dict:
            n = int(self.headers.get("Content-Length") or 0)
            return json.loads(self.rfile.read(n) or b"{}")

        def do_GET(self):
            u = urlparse(self.path)
            parts = [unquote(p) for p in u.path.split("/") if p]
            if parts[:2] == ["__mock", "files"]:
                out = {str(p.relative_to(st.dir)): json.loads(p.read_text()).get("rev") for p in (st.dir / "docs" / "decks").glob("*.json")}
                return self.send(200, {"files": out, "commits": len(st.commits)})
            if len(parts) == 3 and parts[0] == "repos":
                if not self.authed():
                    return
                return self.send(200, {"full_name": f"{parts[1]}/{parts[2]}", "permissions": {"push": True, "pull": True}})
            if len(parts) >= 4 and parts[0] == "repos" and parts[3] == "contents":
                if not self.authed():
                    return
                f = st.path("/".join(parts[4:]))
                if not f.exists():
                    return self.send(404, {"message": "Not Found"})
                data = f.read_bytes()
                return self.send(200, {"sha": sha_of(data), "content": base64.encodebytes(data).decode()})
            if len(parts) == 4 and parts[0] == "repos" and parts[3] == "commits":
                path = parse_qs(u.query).get("path", [""])[0]
                return self.send(200, [c for c in reversed(st.commits) if not path or c["path"] == path][:20])
            self.send(404, {"message": "Not Found"})

        def do_PUT(self):
            parts = [unquote(p) for p in urlparse(self.path).path.split("/") if p]
            if not (len(parts) >= 4 and parts[0] == "repos" and parts[3] == "contents"):
                return self.send(404, {"message": "Not Found"})
            if not self.authed():
                return
            b = self.body()
            f = st.path("/".join(parts[4:]))
            current = sha_of(f.read_bytes()) if f.exists() else None
            if b.get("sha") != current:
                return self.send(409, {"message": "is at %s but expected %s" % (current, b.get("sha"))})
            data = base64.b64decode(b["content"])
            f.write_bytes(data)
            sha = hashlib.sha1(data + str(time.time()).encode()).hexdigest()
            st.commits.append({"sha": sha, "path": "/".join(parts[4:]), "html_url": "https://github.com/o/r/commit/" + sha,
                               "commit": {"message": b.get("message", ""), "author": {"date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}}})
            self.send(200, {"content": {"sha": sha_of(data)}, "commit": {"sha": sha}})

        def do_POST(self):
            parts = [p for p in urlparse(self.path).path.split("/") if p]
            if parts == ["__mock", "revoke"]:
                st.revoked = True
                return self.send(200, {"revoked": True})
            if parts == ["__mock", "edit"]:
                b = self.body()
                f = st.path(b["path"])
                deck = json.loads(f.read_text())
                for s in deck["sections"]:
                    for c in s["cards"]:
                        if c["id"] == b["id"]:
                            c["answerHtml"] = b["answerHtml"]
                deck["rev"] = deck.get("rev", 0) + 1
                f.write_text(json.dumps(deck, ensure_ascii=False, indent=1))
                st.commits.append({"sha": "other", "path": b["path"], "html_url": "", "commit": {"message": "other device", "author": {"date": ""}}})
                return self.send(200, {"rev": deck["rev"]})
            self.send(404, {"message": "Not Found"})

    return H


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8766)
    ap.add_argument("--token", default="test-token")
    args = ap.parse_args()
    st = State(args.token)
    print(f"Mock GitHub API on http://localhost:{args.port} (token {args.token!r}), files in {st.dir}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(st)).serve_forever()


if __name__ == "__main__":
    main()
