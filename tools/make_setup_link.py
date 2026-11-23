#!/usr/bin/env python3
"""Make the one-tap link that turns on saving edits on one of her devices.

  python3 tools/make_setup_link.py            # link copied to the clipboard
  python3 tools/make_setup_link.py --print    # also print it (it contains the token)

The token is a fine-grained GitHub personal access token for this repo only, with Contents:
read and write (create it at https://github.com/settings/personal-access-tokens/new). Keep it in
the macOS Keychain, never in a file or the shell history:

  security add-generic-password -s nursing-flashcards-token -a "$USER" -w

(it prompts for the token). If it isn't in the Keychain, the token is read from the clipboard.

The script checks the token can write to the repo, then builds
https://<owner>.github.io/<repo>/#setup=<token>. The part after '#' is never sent to a server.
Text the link to her privately; she taps it once on her phone and once on her laptop. If a device
is lost or the token expires, revoke or regenerate it on GitHub and send a new link.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote

KEYCHAIN_SERVICE = "nursing-flashcards-token"
TOKEN_RE = re.compile(r"^(github_pat_[A-Za-z0-9_]{20,}|ghp_[A-Za-z0-9]{20,})$")
ROOT = Path(__file__).resolve().parent.parent


def repo_from_remote(url: str) -> str | None:
    """'git@github.com:owner/repo.git' or 'https://github.com/owner/repo' -> 'owner/repo'."""
    m = re.search(r"github\.com[:/]([^/\s]+)/([^/\s]+?)(?:\.git)?/?$", url.strip())
    return f"{m.group(1)}/{m.group(2)}" if m else None


def site_for(repo: str) -> str:
    owner, name = repo.split("/", 1)
    return f"https://{owner.lower()}.github.io/{name}/"


def build_link(site: str, token: str) -> str:
    return site.rstrip("/") + "/#setup=" + quote(token, safe="")


def looks_like_token(s: str) -> bool:
    return bool(TOKEN_RE.match(s.strip()))


def read_token() -> tuple[str | None, str]:
    try:
        out = subprocess.run(["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"], capture_output=True, text=True, timeout=10)
        if out.returncode == 0 and looks_like_token(out.stdout):
            return out.stdout.strip(), "Keychain"
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        clip = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=5).stdout.strip()
        if looks_like_token(clip):
            return clip, "clipboard"
    except (OSError, subprocess.SubprocessError):
        pass
    return None, ""


def check_token(repo: str, token: str) -> tuple[bool, str]:
    req = urllib.request.Request(f"https://api.github.com/repos/{repo}", headers={
        "Accept": "application/vnd.github+json", "Authorization": "Bearer " + token, "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "nursing-flashcards-setup-link"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.load(resp)
            expiry = resp.headers.get("github-authentication-token-expiration") or "no expiry reported"
    except urllib.error.HTTPError as e:
        return False, f"GitHub said {e.code} ({'bad or expired token' if e.code == 401 else 'no access to ' + repo})"
    except urllib.error.URLError as e:
        return False, f"could not reach GitHub ({e.reason})"
    if not (data.get("permissions") or {}).get("push"):
        return False, f"the token can read {repo} but not write to it (it needs Contents: read and write)"
    return True, f"expires: {expiry}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", help="owner/name (default: from the git remote)")
    ap.add_argument("--print", action="store_true", help="Also print the link (it contains the token)")
    args = ap.parse_args(argv)

    repo = args.repo
    if not repo:
        remote = subprocess.run(["git", "-C", str(ROOT), "remote", "get-url", "origin"], capture_output=True, text=True).stdout
        repo = repo_from_remote(remote)
    if not repo:
        print("Could not tell which GitHub repo this is; pass --repo owner/name.", file=sys.stderr)
        return 2
    token, where = read_token()
    if not token:
        print(f"No token found. Store it in the Keychain with:\n  security add-generic-password -s {KEYCHAIN_SERVICE} -a \"$USER\" -w\n"
              "or copy it to the clipboard and run this again.", file=sys.stderr)
        return 2
    ok, detail = check_token(repo, token)
    if not ok:
        print(f"The token from the {where} doesn't work: {detail}.", file=sys.stderr)
        return 1
    link = build_link(site_for(repo), token)
    subprocess.run(["pbcopy"], input=link, text=True, check=False)
    print(f"Token from the {where} can write to {repo} ({detail}).")
    print("Setup link copied to the clipboard. Text it to her privately; she taps it once on each device, then can delete the message.")
    if args.print:
        print(link)
    return 0


if __name__ == "__main__":
    sys.exit(main())
