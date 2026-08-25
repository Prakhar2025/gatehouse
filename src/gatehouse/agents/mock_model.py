"""Mock model provider: drives real Strands agents offline, zero AWS calls.

Speaks the exact wire protocol Strands consumes (verified against
strands.event_loop.streaming.process_stream): Bedrock-style chunks
(messageStart / contentBlockStart / contentBlockDelta / contentBlockStop /
messageStop / metadata).

Used by:
- CI and local tests (fast suite never touches AWS),
- the P2 eval harness LOCAL_MOCK mode,
- developers without credentials.

It is NOT a fake verdict generator: agents still run their real prompts, tools,
and parsing. Only the token-level model is doubled.

Note: strands ships loose stubs; the runtime contract here is enforced by
tests/agents/test_mock_model.py against a live Agent loop. Override-level
mypy warnings in this adapter are suppressed via a pyproject override.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from pydantic import BaseModel
from strands.models import Model
from strands.types.content import Message


class MockModel(Model):
    """Scripted Bedrock-format model double.

    Args:
        text: assistant text when no tool call is requested.
        tool_payload: JSON-serializable payload emitted as a toolUse block when
            the agent loop forces a structured-output tool.
    """

    def __init__(self, text: str = "ok", tool_payload: dict[str, Any] | None = None) -> None:
        self._text = text
        self._payload: dict[str, Any] = tool_payload if tool_payload is not None else {}
        self._config: dict[str, Any] = {}

    # -- Model contract -----------------------------------------------------
    def update_config(self, **model_config: Any) -> None:
        self._config.update(model_config)

    def get_config(self) -> Any:
        return self._config

    async def structured_output(
        self,
        output_model: type[BaseModel],
        prompt: Any,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[dict[str, BaseModel]]:
        yield {"output": output_model(**self._payload)}

    async def stream(
        self,
        messages: list[Message],
        tool_specs: list[dict[str, Any]] | None = None,
        system_prompt: str | None = None,
        *,
        tool_choice: dict[str, Any] | None = None,
        system_prompt_content: list[dict[str, Any]] | None = None,
        invocation_state: dict[str, Any] | None = None,
        model_state: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        async for chunk in self._chunks(tool_specs):
            yield chunk

    # -- internals ----------------------------------------------------------
    async def _chunks(
        self, tool_specs: list[dict[str, Any]] | None
    ) -> AsyncIterator[dict[str, Any]]:
        yield {"messageStart": {"role": "assistant"}}
        if tool_specs:
            name = str(tool_specs[0]["name"])
            yield {
                "contentBlockStart": {
                    "start": {"toolUse": {"toolUseId": "mock-tool-1", "name": name}},
                    "contentBlockIndex": 0,
                }
            }
            yield {
                "contentBlockDelta": {
                    "delta": {"toolUse": {"input": json.dumps(self._payload)}},
                    "contentBlockIndex": 0,
                }
            }
            yield {"contentBlockStop": {"contentBlockIndex": 0}}
        else:
            yield {"contentBlockDelta": {"delta": {"text": self._text}, "contentBlockIndex": 0}}
            yield {"contentBlockStop": {"contentBlockIndex": 0}}
        yield {"messageStop": {"stopReason": "tool_use" if tool_specs else "end_turn"}}
        yield {
            "metadata": {
                "usage": {"inputTokens": 5, "outputTokens": 7, "totalTokens": 12},
                "metrics": {"latencyMs": 1},
            }
        }
