"""Publish local evidence atomically, privately, and without overwriting.

Each UTF-8 payload is staged in its destination directory as a mode-0600
temporary file. A hard link publishes the completed file exclusively: an
existing path, including a symlink or a file created by a concurrent writer,
is never replaced. Multi-file publication is best-effort atomic as a group;
on a failed publication, only links created by this invocation are removed.
The filesystem must support hard links within a directory.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Sequence

from .core import ReceiptError


def publish_private_texts(files: Sequence[tuple[Path, str]]) -> None:
    """Create all destinations from completed UTF-8 payloads, without clobbering.

    File creation is exclusive and mode 0600 on POSIX. Each destination is
    published atomically; multiple destinations have no global filesystem
    transaction, so failure causes a best-effort rollback of our own links.
    """
    if not files:
        raise ReceiptError("no output files specified")
    staged: list[tuple[Path, Path]] = []
    published: list[tuple[Path, Path]] = []
    destinations: set[Path] = set()
    try:
        for name, contents in files:
            destination = Path(name)
            if not destination.name or not isinstance(contents, str):
                raise ReceiptError("invalid output path or payload")
            resolved = destination.resolve(strict=False)
            if resolved in destinations:
                raise ReceiptError("duplicate output destinations")
            destinations.add(resolved)
            if destination.exists() or destination.is_symlink():
                raise ReceiptError(f"output already exists: {destination}")
            destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            fd, temporary_name = tempfile.mkstemp(
                prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
            )
            temporary = Path(temporary_name)
            staged.append((destination, temporary))
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(contents)
                stream.flush()
                os.fsync(stream.fileno())

        for destination, temporary in staged:
            try:
                os.link(temporary, destination)
            except FileExistsError as exc:
                raise ReceiptError(f"output already exists: {destination}") from exc
            published.append((destination, temporary))
    except BaseException:
        # A concurrent process could replace a destination. Roll back only if
        # it still names the inode that this invocation published.
        for destination, temporary in reversed(published):
            try:
                original = temporary.stat()
                current = destination.stat(follow_symlinks=False)
                if (original.st_dev, original.st_ino) == (current.st_dev, current.st_ino):
                    destination.unlink()
            except FileNotFoundError:
                pass
        raise
    finally:
        for _, temporary in staged:
            temporary.unlink(missing_ok=True)
