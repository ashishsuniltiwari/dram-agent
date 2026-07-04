# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     https://www.apache.org/licenses/LICENSE-2.0

"""
Reputation & Game-Theory Math for the DRAM system.

Implements:
  - Γ(Aᵢ): Rawlsian Maximin accountability score for a mesh node Aᵢ.
  - Hoarding-penalty function Φ(Aᵢ).
  - reputation_calc tool for use inside ADK agents.

The Rawlsian Maximin principle prioritises the *worst-off* position.
We extend it into a composite reputation metric:

    Γ(Aᵢ) = α·H(Aᵢ) + β·C(Aᵢ) - Φ(Aᵢ)

Where:
  H(Aᵢ)  = historical honesty ratio   (past requests flagged as truthful / total requests)
  C(Aᵢ)  = contribution ratio         (resources shared / resources consumed)
  Φ(Aᵢ)  = hoarding penalty           (λ · max(0, intake_ratio - HOARD_THRESHOLD))
  α, β    = weighting coefficients     (default: α=0.5, β=0.5)
  λ       = penalty severity factor    (default: 0.3)

Score is clamped to [0.0, 1.0].
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALPHA: float = 0.5          # Weight on historical honesty ratio
BETA: float = 0.5           # Weight on contribution ratio
LAMBDA: float = 0.3         # Hoarding penalty severity
HOARD_THRESHOLD: float = 2.0  # intake/contribution ratio above which hoarding begins
DECAY_FACTOR: float = 0.85  # Exponential decay for old events (per turn)

DB_PATH: Path = Path(__file__).parent.parent / "db" / "dharavi_inventory.json"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

class NodeRecord(BaseModel):
    """Per-node statistics loaded from the inventory database."""
    reputation: float = Field(default=1.0, ge=0.0, le=1.0)
    history: list[str] = Field(default_factory=list)
    resources_consumed: float = Field(default=1.0, gt=0.0)
    resources_contributed: float = Field(default=1.0, ge=0.0)
    requests_total: int = Field(default=1, ge=1)
    requests_truthful: int = Field(default=1, ge=0)


class ReputationResult(BaseModel):
    """Result of the Γ(Aᵢ) calculation."""
    node_id: str
    gamma: float = Field(description="Rawlsian Maximin accountability score Γ(Aᵢ) ∈ [0, 1].")
    honesty_ratio: float = Field(description="H(Aᵢ): truthful requests / total requests.")
    contribution_ratio: float = Field(description="C(Aᵢ): resources contributed / consumed.")
    hoarding_penalty: float = Field(description="Φ(Aᵢ): penalty for exceeding HOARD_THRESHOLD.")
    is_hoarder: bool = Field(description="True if the node is classified as a hoarder.")


# ---------------------------------------------------------------------------
# Math helpers
# ---------------------------------------------------------------------------

def _load_node_record(node_id: str) -> NodeRecord:
    """Load a node's record from the inventory JSON; return defaults if missing."""
    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            db = json.load(f)
        raw = db.get("nodes", {}).get(node_id, {})
        return NodeRecord(**raw)
    except (FileNotFoundError, json.JSONDecodeError, Exception):
        return NodeRecord()


def _honesty_ratio(record: NodeRecord) -> float:
    """H(Aᵢ) — fraction of past requests assessed as truthful."""
    return record.requests_truthful / max(record.requests_total, 1)


def _contribution_ratio(record: NodeRecord) -> float:
    """C(Aᵢ) — ratio of resources shared vs. resources consumed.

    Capped at 1.0 to avoid inflating the score for extreme contributors.
    """
    raw = record.resources_contributed / max(record.resources_consumed, 1e-9)
    return min(raw, 1.0)


def _hoarding_penalty(record: NodeRecord) -> float:
    """Φ(Aᵢ) — non-linear penalty for exceeding the intake/contribution threshold.

    Φ = λ · max(0, intake_ratio - HOARD_THRESHOLD)

    A node is a hoarder if it consumes far more than it contributes.
    """
    intake_ratio = record.resources_consumed / max(record.resources_contributed, 1e-9)
    excess = max(0.0, intake_ratio - HOARD_THRESHOLD)
    return min(LAMBDA * excess, 1.0)  # cap penalty at 1.0


def compute_gamma(record: NodeRecord) -> tuple[float, float, float, float, bool]:
    """Compute Γ(Aᵢ) = α·H + β·C - Φ, clamped to [0, 1].

    Returns:
        (gamma, honesty_ratio, contribution_ratio, hoarding_penalty, is_hoarder)
    """
    H = _honesty_ratio(record)
    C = _contribution_ratio(record)
    Phi = _hoarding_penalty(record)

    raw_score = ALPHA * H + BETA * C - Phi
    gamma = max(0.0, min(1.0, raw_score))
    is_hoarder = Phi > 0.0

    return gamma, H, C, Phi, is_hoarder


# ---------------------------------------------------------------------------
# Public tool function (can be registered as an ADK tool)
# ---------------------------------------------------------------------------

def reputation_calc(node_id: str) -> ReputationResult:
    """Compute the Rawlsian Maximin reputation score Γ(Aᵢ) for a mesh node.

    This function is designed to be registered as a tool inside an ADK agent.
    It loads the node's history from the local inventory database and computes
    the composite accountability score using the formula:

        Γ(Aᵢ) = α·H(Aᵢ) + β·C(Aᵢ) - Φ(Aᵢ)

    Args:
        node_id: The unique identifier of the requesting node.

    Returns:
        A ReputationResult containing Γ and all intermediate metrics.
    """
    record = _load_node_record(node_id)
    gamma, H, C, Phi, is_hoarder = compute_gamma(record)

    return ReputationResult(
        node_id=node_id,
        gamma=gamma,
        honesty_ratio=H,
        contribution_ratio=C,
        hoarding_penalty=Phi,
        is_hoarder=is_hoarder,
    )
