"""Daily digest Lambda: flushes escalations parked by quiet hours.

Invoked by EventBridge schedule once per day (doc 05 section 6 morning
digest). The queue itself is process-local in v1: items survive only inside a
warm container, which covers the staging demo path; a durable DynamoDB-backed
queue is the P4 observability upgrade and its absence degrades to fewer
digest entries, never to a wrong escalation.
"""

from __future__ import annotations

import json
from typing import Any

from gatehouse.logging_utils import configure_logging, get_logger
from gatehouse.runtime import digest_tick

configure_logging()
log = get_logger("gatehouse.digest")


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Scheduled entrypoint: send one morning digest if anything was parked."""
    flushed = digest_tick()
    log.info("digest_tick", extra={"extra_fields": {"flushed": flushed}})
    return {"statusCode": 200, "body": json.dumps({"flushed": flushed})}
