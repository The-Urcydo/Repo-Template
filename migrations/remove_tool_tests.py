#!/usr/bin/env python3
"""Delete the two tool-test files that older releases shipped into generated projects (ADR 0008).

From v0.6.0 the two files live in the template repo's root-level tool-tests/ and no longer ship.
Copier's 3-way merge keeps files that the new template no longer lists, so an update leaves both
shipped copies behind. This migration removes exactly those two paths and nothing else: a project's
own test under tools/tests/ survives. It runs after the merge (see copier.yml _migrations), standard
library only, with grammar that stays valid on Python 3.9 because migrations run under the user's
interpreter during `copier update`.

    python3 migrations/remove_tool_tests.py <project-root>
"""
from __future__ import annotations

import sys
from pathlib import Path

FILES = ("tools/tests/test_tools.py", "tools/tests/test_eval_harness.py")


def main(root: Path) -> int:
    for rel in FILES:
        path = root / rel
        if path.is_file():
            path.unlink()
            print(f"remove: {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1] if len(sys.argv) > 1 else ".")))
