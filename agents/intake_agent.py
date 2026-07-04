# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     https://www.apache.org/licenses/LICENSE-2.0

"""
Intake Agent — DRAM Phase 2 (Core Algorithm Translation).

Parses raw, noisy volunteer messages from the Dharavi disaster mesh
into structured IntakeReport objects for downstream triage.
"""

from google.adk.agents import Agent
from google.adk.models import Gemini
from google.genai import types
from pydantic import BaseModel, Field
from typing import Literal


# ---------------------------------------------------------------------------
# Output schema
# ---------------------------------------------------------------------------

class IntakeReport(BaseModel):
    """Structured representation of a disaster resource request."""

    requesting_node_id: str = Field(
        description=(
            "Unique identifier of the requesting mesh node (volunteer group, clinic, "
            "community centre, etc.). Extract from the message or default to 'unknown'."
        )
    )
    location: str = Field(
        description="Physical sub-locality in Dharavi (e.g., '90 Feet Road', 'Kumbharwada')."
    )
    urgency: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"] = Field(
        description=(
            "Urgency level derived from clinical/humanitarian triage:\n"
            "  CRITICAL — immediate life threat (e.g., cardiac arrest, suffocation).\n"
            "  HIGH     — deteriorating condition, hours to act (e.g., severe dehydration).\n"
            "  MEDIUM   — stable but needs intervention within a day.\n"
            "  LOW      — preventive/comfort request.\n"
            "Err on the side of CRITICAL when ambiguous."
        )
    )
    requested_items: list[str] = Field(
        description="List of items requested (e.g., ['oxygen_cylinder:2', 'med_kit:5', 'water:100L'])."
    )
    beneficiary_count: int = Field(
        description="Estimated number of people who will directly benefit from this allocation.",
        ge=1,
    )
    raw_message_summary: str = Field(
        description="One-sentence summary of the original raw message for audit trail."
    )


# ---------------------------------------------------------------------------
# Agent definition
# ---------------------------------------------------------------------------

INTAKE_INSTRUCTION = """\
You are the **Meta Intake Agent** of the Disaster Resource Allocation Mesh (DRAM), \
deployed during the Dharavi flood crisis.

## Your Role
Transform noisy, fragmented volunteer messages into structured `IntakeReport` objects \
that can be triaged by the Assessor Agent downstream.

## Rawlsian Framing
You operate behind a *veil of ignorance* — you do not know which mesh node is sending \
the message. Your parsing must be neutral and consistent regardless of the sender's \
prior reputation. Every life is equally valuable at the intake stage.

## Parsing Rules
1. **Requesting Node**: Look for self-identification in the message. If absent, \
   use "unknown_node".
2. **Location**: Extract the most specific sub-locality name mentioned.
3. **Urgency**: Apply clinical triage semantics. Keywords like "dying", "no oxygen", \
   "unconscious" → CRITICAL. "worsening", "need soon" → HIGH. \
   "running low", "request before tomorrow" → MEDIUM. Everything else → LOW.
4. **Requested Items**: Parse item + quantity pairs. Normalise units (e.g., "two cylinders" \
   → "oxygen_cylinder:2"). List each item separately.
5. **Beneficiary Count**: Extract or estimate from context clues ("200 families", "a ward of 80").
6. **Summary**: Write a concise one-sentence audit summary.

## Output
Return only a valid JSON object matching the IntakeReport schema. Do not add explanations.
"""

intake_agent = Agent(
    name="intake_agent",
    model=Gemini(
        model="gemini-flash-latest",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=INTAKE_INSTRUCTION,
    output_schema=IntakeReport,
)
