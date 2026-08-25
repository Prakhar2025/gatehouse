"""Root test fixtures.

The suite must never depend on the host machine: a developer with a real
.env at the repo root would otherwise leak live secrets into unit tests and
flip environment-dependent assertions. Runs before any test module imports
gatehouse.config, pinning the dotenv source to an always-empty file.
"""

from __future__ import annotations

import os
import pathlib

_EMPTY_DOTENV = pathlib.Path(__file__).resolve().parent / "dotenv-empty"
_EMPTY_DOTENV.touch(exist_ok=True)
os.environ["GATEHOUSE_DOTENV_PATH"] = str(_EMPTY_DOTENV)
