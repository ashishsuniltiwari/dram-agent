# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     https://www.apache.org/licenses/LICENSE-2.0

"""
Assessor Agent — DRAM Phase 2 (Core Algorithm Translation).

Applies the Rawlsian Maximin triage rubric to an IntakeReport, using
the Γ(Aᵢ) reputation score as an equity gate.

Decision logic:
  1. Compute Γ(Aᵢ) for the requesting node via the reputation_calc tool.
  2. Gate approval by urgency + reputation threshold:
       - CRITICAL → approve if Γ >= 0.0  (no minimum — life first)
       - HIGH     → approve if Γ >= 0.25
       - MEDIUM   → approve if Γ >= 0.50
       - LOW      → approve if Γ >= 0.70
  3. Hoarder nodes (Φ(Aᵢ) > 0) face a tighter gate at every urgency level.
"""

from google.adk.agents import Agent
from google.adk.models import Gemini
from google.genai import types
from pydantic import BaseModel, Field
from typing import Literal

from skills.reputation_calc import reputation_calc


# ---------------------------------------------------------------------------
# Output schema
# ---------------------------------------------------------------------------

class TriageDecision(BaseModel):
    """Output of the assessor triage step."""

    requesting_node_id: str = Field(description="The node ID evaluated.")
    approved: bool = Field(
        description="True if the request passes the Rawlsian triage gate."
    )
    urgency: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"] = Field(
        description="Urgency level inherited from the IntakeReport."
    )
    gamma_score: float = Field(
        description="Γ(Aᵢ) — the Rawlsian Maximin reputation score used for gating.",
        ge=0.0, le=1.0,
    )
    is_hoarder: bool = Field(
        description="Whether the node was classified as a hoarder."
    )
    reasoning: str = Field(
        description="Concise step-by-step reasoning for the decision, citing Γ, urgency, and any penalties."
    )


# ---------------------------------------------------------------------------
# Urgency → minimum Γ threshold map
# ---------------------------------------------------------------------------

URGENCY_THRESHOLD: dict[str, float] = {
    "CRITICAL": 0.0,
    "HIGH":     0.25,
    "MEDIUM":   0.50,
    "LOW":      0.70,
}

HOARDER_PENALTY_BOOST: float = 0.15  # Extra Γ needed from hoarders


# ---------------------------------------------------------------------------
# Agent definition
# ---------------------------------------------------------------------------

ASSESSOR_INSTRUCTION = """\
You are the **Assessor Agent** of the Disaster Resource Allocation Mesh (DRAM).

## Your Role
Apply the Rawlsian Maximin triage rubric to every IntakeReport, using the \
`reputation_calc` tool to retrieve Γ(Aᵢ) — the accountability score of the \
requesting node.

## Step-by-Step Protocol

### Step 1 — Retrieve Reputation
Call `reputation_calc(node_id=<requesting_node_id>)` to obtain:
  - Γ     : composite accountability score ∈ [0, 1]
  - is_hoarder : boolean flag (True when Φ(Aᵢ) > 0)

### Step 2 — Apply Urgency Gate
Determine the minimum Γ required for approval:

  | Urgency  | Min Γ (honest node) | Min Γ (hoarder, +0.15 penalty) |
  |----------|---------------------|-------------------------------|
  | CRITICAL | 0.00                | 0.15                          |
  | HIGH     | 0.25                | 0.40                          |
  | MEDIUM   | 0.50                | 0.65                          |
  | LOW      | 0.70                | 0.85                          |

### Step 3 — Rawlsian Override
If the request is CRITICAL AND the beneficiary count > 50 AND no inventory fraud \
has been detected in the node's history, APPROVE unconditionally. Document this \
override explicitly in your reasoning.

### Step 4 — Emit Decision
Return a JSON object matching the TriageDecision schema.
Include Γ, urgency, is_hoarder, approved, and your reasoning chain.

## Rawlsian Principle
Prioritise the *worst-off*. Do not let reputational bias block life-critical aid \
to vulnerable populations. Reputation gates exist to prevent *gaming*, not to \
gatekeep the truly desperate.
"""

assessor_agent = Agent(
    name="assessor_agent",
    model=Gemini(
        model="gemini-flash-latest",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=ASSESSOR_INSTRUCTION,
    tools=[reputation_calc],
    output_schema=TriageDecision,
)
