# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     https://www.apache.org/licenses/LICENSE-2.0

"""
Allocation Agent — DRAM Phase 2 (Core Algorithm Translation).

Translates an approved TriageDecision into concrete AllocationOrders,
drawing from the Dharavi local inventory database and applying the
Rawlsian Maximin equity principle to decide quantities when supplies
are constrained.

Allocation policy:
  - CRITICAL: Allocate 100 % of requested quantity (or all available).
  - HIGH:     Allocate up to 75 % of requested quantity.
  - MEDIUM:   Allocate up to 50 % of requested quantity.
  - LOW:      Allocate up to 25 % of requested quantity.

If a request is not approved, all allocations are denied.
"""

from google.adk.agents import Agent
from google.adk.models import Gemini
from google.genai import types
from pydantic import BaseModel, Field
from typing import Literal
import json
from pathlib import Path


# ---------------------------------------------------------------------------
# Inventory loader tool
# ---------------------------------------------------------------------------

DB_PATH = Path(__file__).parent.parent / "db" / "dharavi_inventory.json"


def get_inventory() -> dict:
    """Retrieve the current Dharavi local inventory levels.

    Returns:
        A dict mapping item names to available quantities.
        Example: {"oxygen": 100, "med_kits": 150, "water": 1000}
    """
    with open(DB_PATH, "r", encoding="utf-8") as f:
        db = json.load(f)
    return db.get("inventory", {})


# ---------------------------------------------------------------------------
# Output schema
# ---------------------------------------------------------------------------

class AllocationLineItem(BaseModel):
    """A single item allocation within an order."""
    item: str = Field(description="Normalised item name (e.g., 'oxygen', 'med_kits').")
    requested_qty: int = Field(description="Quantity requested in the IntakeReport.", ge=0)
    allocated_qty: int = Field(description="Quantity actually allocated.", ge=0)
    available_qty: int = Field(description="Quantity available in the local inventory.", ge=0)
    allocation_ratio: float = Field(
        description="Fraction of requested quantity that was fulfilled ∈ [0, 1].", ge=0.0, le=1.0
    )
    denied_reason: str = Field(
        default="",
        description="Non-empty if this item was not fully allocated (e.g., 'insufficient stock')."
    )


class AllocationOrder(BaseModel):
    """Final resource allocation order for a node request."""
    order_id: str = Field(description="Unique order ID, e.g. 'ORD-<node_id>-<timestamp>'.")
    requesting_node_id: str = Field(description="The mesh node receiving this allocation.")
    approved: bool = Field(description="Whether the upstream triage approved this request.")
    urgency: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"] = Field(
        description="Urgency level, which governs the allocation ratio cap."
    )
    line_items: list[AllocationLineItem] = Field(
        description="Per-item breakdown of the allocation."
    )
    total_items_allocated: int = Field(
        description="Total number of distinct items successfully allocated (qty > 0)."
    )
    allocation_summary: str = Field(
        description="Human-readable summary of the allocation decision."
    )


# ---------------------------------------------------------------------------
# Agent definition
# ---------------------------------------------------------------------------

ALLOCATION_INSTRUCTION = """\
You are the **Task Generator Agent** of the Disaster Resource Allocation Mesh (DRAM).

## Your Role
Convert an approved TriageDecision into a concrete AllocationOrder by cross-referencing \
the current inventory via the `get_inventory` tool.

## Allocation Protocol

### Step 1 — Check Approval
If the TriageDecision has `approved=False`, emit an AllocationOrder with \
all `allocated_qty=0` and the summary "Request denied at triage stage."

### Step 2 — Retrieve Inventory
Call `get_inventory()` to get current stock levels.

### Step 3 — Apply Urgency-Based Allocation Ratio Cap

  | Urgency  | Max Allocation Ratio |
  |----------|---------------------|
  | CRITICAL | 100 %               |
  | HIGH     | 75 %                |
  | MEDIUM   | 50 %                |
  | LOW      | 25 %                |

Compute `allocated_qty = min(requested_qty * ratio_cap, available_qty)`.
Round down to the nearest integer.

### Step 4 — Rawlsian Reserve Rule
For CRITICAL requests, never deplete any inventory item below 10 % of its \
current level — that minimum is reserved for even-worse-off nodes that may \
arrive next. Document this as "Rawlsian reserve applied" if triggered.

### Step 5 — Emit AllocationOrder
Populate every field of AllocationOrder. Generate `order_id` as \
`ORD-<requesting_node_id>-<urgency>`.

## Equity Mandate
You serve the worst-off first, but you must also ensure that your allocation \
does not catastrophically deplete supplies needed by future arrivals who may \
be in worse condition. This is the Rawlsian balance: protect the floor, not \
just the immediate request.
"""

allocation_agent = Agent(
    name="allocation_agent",
    model=Gemini(
        model="gemini-flash-latest",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=ALLOCATION_INSTRUCTION,
    tools=[get_inventory],
    output_schema=AllocationOrder,
)
