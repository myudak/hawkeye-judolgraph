"""Minimal frozen entry point; multiprocessing dispatch must happen before heavy imports."""

from __future__ import annotations

import multiprocessing

if __name__ == "__main__":
    multiprocessing.freeze_support()

    from hawkeye.desktop import main

    raise SystemExit(main())
