#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from runtime.work_memory import (  # noqa: E402
    DEFAULT_STATE_RELATIVE_PATH,
    AgentWorkMemoryHook,
    AgentWorkMemoryStore,
)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        override = os.environ.get("AGENT_WORK_MEMORY_DB")
        if not override or not Path(override).is_absolute():
            raise ValueError("explicit_private_work_memory_path_required")
        db_path = Path(override)
        parent = db_path.parent.stat()
        if parent.st_uid != os.getuid() or parent.st_mode & 0o077:
            raise ValueError("private_work_memory_directory_required")
        if db_path.exists():
            meta = db_path.lstat()
            if not stat.S_ISREG(meta.st_mode) or meta.st_uid != os.getuid() or meta.st_mode & 0o077 or meta.st_nlink != 1:
                raise ValueError("private_work_memory_file_required")
        os.umask(0o077)
        result = AgentWorkMemoryHook(AgentWorkMemoryStore(db_path)).handle(payload)
        print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
        return 0
    except Exception as error:
        # Hooks are fail-open for the agent loop, but never echo payloads,
        # transcripts, credentials, or stack traces to stdout.
        print(
            json.dumps(
                {"status": "degraded", "error_type": type(error).__name__},
                separators=(",", ":"),
            )
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
