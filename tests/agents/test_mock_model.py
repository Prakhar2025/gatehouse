"""Tests for the mock model provider against a real Strands Agent loop.

These prove the wire format stays compatible with the installed SDK version.
If Strands changes its stream protocol, these tests fail before prod does.
"""

from __future__ import annotations

import asyncio
from typing import Any

from pydantic import BaseModel

from gatehouse.agents.mock_model import MockModel


def run(coro: Any) -> Any:
    return asyncio.run(coro)


class Out(BaseModel):
    answer: str


class TestMockTextPath:
    def test_invoke_returns_text(self) -> None:
        async def go() -> str:
            from strands import Agent

            agent = Agent(model=MockModel(text="VERDICT SCAM"))
            result = await agent.invoke_async("anything")
            return "".join(
                block.get("text", "")
                for block in result.message["content"]
                if isinstance(block, dict)
            )

        assert run(go()) == "VERDICT SCAM"

    def test_stop_reason_end_turn(self) -> None:
        async def go() -> str:
            from strands import Agent

            agent = Agent(model=MockModel(text="x"))
            result = await agent.invoke_async("anything")
            return str(result.stop_reason)

        assert run(go()) == "end_turn"


class TestMockToolPath:
    def test_structured_output_forced_tool(self) -> None:
        async def go() -> Out:
            from strands import Agent

            payload = {"answer": "SCAM"}
            agent = Agent(model=MockModel(tool_payload=payload))
            result = await agent.invoke_async("q", structured_output_model=Out)
            value = result.structured_output
            assert isinstance(value, Out)
            return value

        out = run(go())
        assert out.answer == "SCAM"


class TestUsageAccounting:
    def test_usage_recorded_in_metrics(self) -> None:
        async def go() -> int:
            from strands import Agent

            agent = Agent(model=MockModel(text="hello"))
            result = await agent.invoke_async("hi")
            usage = result.metrics.accumulated_usage
            return int(usage.get("totalTokens", -1))

        assert run(go()) == 12  # our metadata chunk reports 12 total tokens
