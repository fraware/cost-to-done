"""Check tracked local links in public Markdown documentation.

This is deliberately a repository-local check, not a network crawler or a
full Markdown parser. Ignore fenced code and external URLs. Links to generated
files should point to generation instructions, not untracked artifacts.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"\]\(\s*(?:<([^>]+)>|([^\s)]+))")
FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")


def local_links(text: str):
    """Yield line numbers and local link destinations outside code fences."""
    fence = None
    for number, line in enumerate(text.splitlines(), 1):
        match = FENCE.match(line)
        if match:
            marker = match.group(1)
            if fence is None:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence) and not line[match.end():].strip():
                fence = None
            continue
        if fence is not None:
            continue
        for match in LINK.finditer(line):
            url = urlsplit(match.group(1) or match.group(2))
            if url.scheme or url.netloc or not url.path or url.path.startswith("/"):
                continue
            yield number, unquote(url.path)


def main() -> int:
    raw = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
    tracked = {PurePosixPath(p.decode("utf-8")) for p in raw.split(b"\0") if p}
    directories = {parent for p in tracked for parent in p.parents}
    docs = sorted(p for p in tracked if p.suffix == ".md"
                  and (len(p.parts) == 1 or p.parts[0] in ("docs", ".github")))
    broken = []
    count = 0
    for doc in docs:
        for line, dest in local_links((ROOT / doc).read_text(encoding="utf-8")):
            count += 1
            target = (ROOT / doc.parent / dest).resolve()
            if not target.is_relative_to(ROOT):
                broken.append(f"{doc}:{line}: link escapes repository: {dest}")
                continue
            relative = PurePosixPath(target.relative_to(ROOT).as_posix())
            if relative not in tracked and relative not in directories:
                broken.append(f"{doc}:{line}: missing tracked target: {dest}")
    for error in broken:
        print(error, file=sys.stderr)
    print(f"Checked {count} local links across {len(docs)} Markdown files; {len(broken)} missing.")
    return int(bool(broken))


if __name__ == "__main__":
    raise SystemExit(main())
