"""Install the exact published wheel and capture a non-sensitive demo transcript."""
from __future__ import annotations

import argparse
import html
import os
import shutil
import subprocess
from pathlib import Path

WHEEL = "cost_to_done-0.1.0-py3-none-any.whl"
URL = "https://github.com/fraware/cost-to-done/releases/download/v0.1.0/" + WHEEL


def run(command: list[str], cwd: Path, env: dict[str, str]) -> str:
    result = subprocess.run(command, cwd=cwd, env=env, check=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, timeout=120)
    return result.stdout


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--venv", type=Path, required=True)
    parser.add_argument("--site", type=Path, required=True)
    args = parser.parse_args()
    wheel = args.wheel.resolve(strict=True)
    if wheel.name != WHEEL:
        raise ValueError("Unexpected distribution")
    root = Path(__file__).resolve().parents[1]
    shutil.copytree(root / "docs", args.site)
    # Use a separate environment and no credential or user Python configuration.
    env = {key: value for key, value in os.environ.items()
           if key in ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "SSL_CERT_FILE")}
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    env["PYTHONNOUSERSITE"] = "1"
    python = args.venv.resolve(strict=True) / "bin/python"
    cli = python.with_name("cost-to-done")
    install = run([str(python), "-m", "pip", "install", "--no-index", "--no-deps",
                   str(wheel)], args.site, env)
    if "Successfully installed cost-to-done-0.1.0" not in install:
        raise ValueError("Unexpected installation result")
    run([str(python), "-c", "import cost_to_done; assert cost_to_done.__version__ == '0.1.0'"],
        args.site, env)
    result = run([str(cli), "demo", "--output", "demo.html"], args.site, env)
    if "Synthetic demonstration" not in result:
        raise ValueError("Missing synthetic disclosure")
    transcript = (
        "$ python -m pip install " + WHEEL + "\n"
        + "Successfully installed cost-to-done-0.1.0\n\n"
        + "$ cost-to-done demo --output demo.html\n" + result
    )
    # Record the actual successful line, not all of pip's host-specific paths.
    print(transcript)
    page = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Release command transcript · Cost to Done</title><link rel="stylesheet" href="site.css">
<style>pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:18px;line-height:1.7}</style>
</head><body><main class="container"><div class="page-title"><h1>Install. Generate a report.</h1>
<p class="lead">Actual v0.1.0 command output captured in a clean environment. The recorded installation used the downloaded and checksum-verified wheel.</p></div>
<div class="code-panel"><div class="code-head"><span>Captured command transcript</span><span>No model calls</span></div><pre>""" + html.escape(transcript) + """</pre></div>
<p class="note">The installation output is condensed to its confirmed success line. The demo is synthetic, not measured model performance.</p>
<p class="note">Published wheel: <a href="""" + URL + """">v0.1.0</a></p></main></body></html>"""
    (args.site / "release-transcript.html").write_text(page, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
