"""Evaluation data models (doc 07)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

GroundTruth = Literal["scam", "benign"]
Difficulty = Literal["easy", "medium", "hard"]


class EvalCase(BaseModel):
    """One labeled case in a benchmark set."""

    model_config = ConfigDict(extra="forbid")

    id: str
    stratum: str
    lang: Literal["en", "hi"]
    difficulty: Difficulty
    ground_truth: GroundTruth
    text: str = Field(min_length=1)
    expect_payment_intent: bool = False


class StratumMetrics(BaseModel):
    """Metrics for one stratum with Wilson 95 percent intervals on rates."""

    model_config = ConfigDict(extra="forbid")

    stratum: str
    n: int
    tp: int = 0
    fp: int = 0
    tn: int = 0
    fn: int = 0

    @property
    def precision(self) -> float:
        denom = self.tp + self.fp
        return self.tp / denom if denom else 0.0

    @property
    def recall(self) -> float:
        denom = self.tp + self.fn
        return self.tp / denom if denom else 0.0


class Report(BaseModel):
    """Aggregate metrics over a run; byte-stable for fixed inputs."""

    model_config = ConfigDict(extra="forbid")

    cases: int
    tp: int
    fp: int
    tn: int
    fn: int
    precision: float
    precision_ci: tuple[float, float]
    recall: float
    recall_ci: tuple[float, float]
    false_gate_rate: float
    noise_leak_rate: float
    per_stratum: list[StratumMetrics]
