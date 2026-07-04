# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     https://www.apache.org/licenses/LICENSE-2.0

"""
DRAM MCP Server — Phase 3.

Exposes disaster mesh tools over the Model Context Protocol (MCP)
so that ADK agents can call them via McpToolset.

Tools exposed:
  - query_telemetry(node_id)         → real-time disaster telemetry for a node
  - get_node_history(node_id)        → node's reputation history from the inventory DB
  - check_inventory(item)            → stock level for a specific item
  - update_inventory(item, delta)    → deduct stock after a successful allocation
  - record_allocation(...)           → persist an allocation event to the audit log

Run this server with:
    uv run python -m mcp_server.dram_server
  or in Stdio mode for ADK agent integration:
    uv run python -m mcp_server.dram_server --transport stdio
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT = Path(__file__).parent.parent
DB_DIR = ROOT / "db"

INVENTORY_PATH = DB_DIR / "dharavi_inventory.json"
TELEMETRY_PATH = DB_DIR / "telemetry.json"
AUDIT_LOG_PATH = DB_DIR / "allocations_log.json"


# ---------------------------------------------------------------------------
# FastMCP server instance
# ---------------------------------------------------------------------------

mcp = FastMCP(
    name="dram-mesh-server",
    instructions=(
        "DRAM Disaster Resource Allocation Mesh server. "
        "Provides telemetry, inventory, and allocation tools for the Dharavi crisis mesh. "
        "All writes are persisted to local JSON databases."
    ),
)


# ---------------------------------------------------------------------------
# Internal DB helpers (not exposed as tools)
# ---------------------------------------------------------------------------

def _read_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Tool: query_telemetry
# ---------------------------------------------------------------------------

@mcp.tool()
def query_telemetry(node_id: str) -> dict:
    """Query real-time disaster telemetry for a mesh node.

    Returns flood level, medical demand, power status, connectivity,
    population at risk, and the timestamp of the last sensor reading.
    Falls back to 'unknown_node' defaults if the node is not found.

    Args:
        node_id: Unique identifier of the requesting mesh node.

    Returns:
        dict with keys: node_id, flood_level_m, medical_demand,
        power_status, connectivity, population_at_risk, last_updated_utc,
        landmark, found (bool).
    """
    db = _read_json(TELEMETRY_PATH)
    nodes = db.get("nodes", {})
    record = nodes.get(node_id) or nodes.get("unknown_node", {})
    found = node_id in nodes

    return {
        "node_id": node_id,
        "found": found,
        "flood_level_m": record.get("flood_level_m", 0.0),
        "medical_demand": record.get("medical_demand", "UNKNOWN"),
        "power_status": record.get("power_status", "UNKNOWN"),
        "connectivity": record.get("connectivity", "UNKNOWN"),
        "population_at_risk": record.get("population_at_risk", 0),
        "last_updated_utc": record.get("last_updated_utc", ""),
        "landmark": record.get("landmark", "Unknown location"),
    }


# ---------------------------------------------------------------------------
# Tool: get_node_history
# ---------------------------------------------------------------------------

@mcp.tool()
def get_node_history(node_id: str) -> dict:
    """Retrieve the historical behavior profile of a mesh node.

    Returns the node's existing reputation score and its qualitative
    history tags (e.g., 'truthful', 'hoarding', 'cooperative').

    Args:
        node_id: Unique identifier of the mesh node.

    Returns:
        dict with keys: node_id, found (bool), reputation (float),
        history (list[str]).
    """
    db = _read_json(INVENTORY_PATH)
    nodes = db.get("nodes", {})
    record = nodes.get(node_id, {})
    found = node_id in nodes

    return {
        "node_id": node_id,
        "found": found,
        "reputation": record.get("reputation", 1.0),
        "history": record.get("history", []),
        "resources_consumed": record.get("resources_consumed", 1.0),
        "resources_contributed": record.get("resources_contributed", 1.0),
        "requests_total": record.get("requests_total", 1),
        "requests_truthful": record.get("requests_truthful", 1),
    }


# ---------------------------------------------------------------------------
# Tool: check_inventory
# ---------------------------------------------------------------------------

@mcp.tool()
def check_inventory(item: str) -> dict:
    """Check the current stock level of a specific inventory item.

    Args:
        item: The item name to query (e.g., 'oxygen', 'med_kits', 'water').

    Returns:
        dict with keys: item, quantity (int or None), all_items (dict).
    """
    db = _read_json(INVENTORY_PATH)
    inventory = db.get("inventory", {})
    quantity = inventory.get(item)

    return {
        "item": item,
        "quantity": quantity,
        "found": quantity is not None,
        "all_items": inventory,
    }


# ---------------------------------------------------------------------------
# Tool: update_inventory
# ---------------------------------------------------------------------------

@mcp.tool()
def update_inventory(item: str, delta: int) -> dict:
    """Deduct or replenish stock for an inventory item.

    Negative delta = deduction (allocation). Positive delta = replenishment.
    Will never reduce quantity below 0 (floors at 0).

    Args:
        item:  The item name (e.g., 'oxygen', 'med_kits', 'water').
        delta: Signed integer quantity change (negative to deduct).

    Returns:
        dict with keys: item, previous_qty, new_qty, delta, success (bool),
        error (str, empty if success).
    """
    db = _read_json(INVENTORY_PATH)
    inventory = db.get("inventory", {})

    if item not in inventory:
        return {
            "item": item,
            "previous_qty": None,
            "new_qty": None,
            "delta": delta,
            "success": False,
            "error": f"Item '{item}' not found in inventory.",
        }

    prev = inventory[item]
    new_qty = max(0, prev + delta)
    inventory[item] = new_qty
    db["inventory"] = inventory
    _write_json(INVENTORY_PATH, db)

    return {
        "item": item,
        "previous_qty": prev,
        "new_qty": new_qty,
        "delta": delta,
        "success": True,
        "error": "",
    }


# ---------------------------------------------------------------------------
# Tool: record_allocation
# ---------------------------------------------------------------------------

@mcp.tool()
def record_allocation(
    order_id: str,
    node_id: str,
    urgency: str,
    approved: bool,
    items_allocated: str,
    gamma_score: float,
    is_hoarder: bool,
    summary: str,
) -> dict:
    """Persist a completed allocation event to the immutable audit log.

    This function appends the allocation event to allocations_log.json.
    It is append-only — no event is ever modified or deleted.

    Args:
        order_id:        Unique order ID (e.g., 'ORD-volunteer_group_a-CRITICAL').
        node_id:         The requesting mesh node.
        urgency:         Urgency level: CRITICAL, HIGH, MEDIUM, or LOW.
        approved:        Whether the triage approved this request.
        items_allocated: JSON-encoded list of AllocationLineItem dicts.
        gamma_score:     Γ(Aᵢ) score used in the triage decision.
        is_hoarder:      Whether the node was flagged as a hoarder.
        summary:         Human-readable allocation summary string.

    Returns:
        dict with keys: success (bool), order_id, timestamp_utc, error (str).
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    event = {
        "order_id": order_id,
        "node_id": node_id,
        "urgency": urgency,
        "approved": approved,
        "items_allocated": items_allocated,
        "gamma_score": gamma_score,
        "is_hoarder": is_hoarder,
        "summary": summary,
        "timestamp_utc": timestamp,
    }

    try:
        log = _read_json(AUDIT_LOG_PATH)
        log.setdefault("allocations", []).append(event)
        _write_json(AUDIT_LOG_PATH, log)
        return {"success": True, "order_id": order_id, "timestamp_utc": timestamp, "error": ""}
    except Exception as exc:
        return {"success": False, "order_id": order_id, "timestamp_utc": timestamp, "error": str(exc)}


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="DRAM MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport mode: stdio (default, for ADK agents) or sse (for HTTP clients).",
    )
    parser.add_argument(
        "--host", default="0.0.0.0", help="Host for SSE transport."
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="Port for SSE transport."
    )
    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport="sse", host=args.host, port=args.port)
