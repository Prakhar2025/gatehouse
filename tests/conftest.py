"""Root test fixtures.

The suite must never depend on the host machine: a developer with a real
.env at the repo root would otherwise leak live secrets into unit tests and
flip environment-dependent assertions. Runs before any test module imports
gatehouse.config, pinning the dotenv source to an always-empty file.
"""

from __future__ import annotations

import os
import pathlib
import re
from typing import Any

_EMPTY_DOTENV = pathlib.Path(__file__).resolve().parent / "dotenv-empty"
_EMPTY_DOTENV.touch(exist_ok=True)
os.environ["GATEHOUSE_DOTENV_PATH"] = str(_EMPTY_DOTENV)

# Scrub any GATEHOUSE_* variables exported in the developer's shell: real
# environment beats dotenv in pydantic-settings, and a session that sourced
# .env would otherwise leak live values into unit tests.
for _key in [k for k in os.environ if k.startswith("GATEHOUSE_")]:
    if _key != "GATEHOUSE_DOTENV_PATH":
        del os.environ[_key]

# Subset of the DynamoDB reserved-word list covering every attribute name
# this repo stores. The live service rejects bare reserved words inside
# update/condition expressions while in-memory fakes accept anything, which
# is how a green suite shipped a 500ing bind path. Any recorded call carrying
# a bare reserved word fails the test run.
_DYNAMO_RESERVED = re.compile(
    r"\b(consumed|expires_at|taint|size|status|timestamp|ttl|name|count)\b", re.IGNORECASE
)


def assert_dynamo_grammar_safe(call_kwargs: dict[str, Any]) -> None:
    """Fail when an expression uses a reserved word without a #placeholder."""
    for key in ("UpdateExpression", "ConditionExpression"):
        expr = call_kwargs.get(key)
        if not isinstance(expr, str):
            continue
        hit = _DYNAMO_RESERVED.search(expr)
        if hit:
            raise AssertionError(
                f"{key} uses bare reserved word '{hit.group(0)}': {expr!r}. "
                "Use ExpressionAttributeNames placeholders."
            )
