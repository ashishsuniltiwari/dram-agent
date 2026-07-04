# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     https://www.apache.org/licenses/LICENSE-2.0

"""
DRAM test suite — Phases 1, 2 & 3.

Phase 1: Boilerplate — App & Workflow compilation.
Phase 2: Core Algorithm — Γ(Aᵢ) reputation math, hoarding penalty, allocation tool.
"""

import pytest
import math

from google.adk.apps import App
from google.adk.workflow import Workflow
from main import app, dram_workflow

from skills.reputation_calc import (
    NodeRecord,
    compute_gamma,
    _honesty_ratio,
    _contribution_ratio,
    _hoarding_penalty,
    reputation_calc,
    ALPHA, BETA, LAMBDA, HOARD_THRESHOLD,
)
from agents.allocation_agent import get_inventory


# ===========================================================================
# Phase 1 — Boilerplate tests
# ===========================================================================

class TestBoilerplate:
    def test_app_initialization(self):
        """Verify that the DRAM ADK App initializes with correct configuration."""
        assert isinstance(app, App)
        assert app.name == "dram-app"

    def test_workflow_compilation(self):
        """Verify that the DRAM ADK Workflow graph compiles correctly."""
        assert isinstance(dram_workflow, Workflow)
        assert dram_workflow.name == "dram_workflow"
        assert len(dram_workflow.edges) == 3


# ===========================================================================
# Phase 2 — Reputation math tests
# ===========================================================================

class TestReputationMath:

    # -----------------------------------------------------------------------
    # Honesty ratio H(Aᵢ)
    # -----------------------------------------------------------------------

    def test_honesty_ratio_perfect(self):
        record = NodeRecord(requests_total=10, requests_truthful=10)
        assert _honesty_ratio(record) == pytest.approx(1.0)

    def test_honesty_ratio_zero(self):
        record = NodeRecord(requests_total=10, requests_truthful=0)
        assert _honesty_ratio(record) == pytest.approx(0.0)

    def test_honesty_ratio_partial(self):
        record = NodeRecord(requests_total=8, requests_truthful=3)
        assert _honesty_ratio(record) == pytest.approx(3 / 8)

    # -----------------------------------------------------------------------
    # Contribution ratio C(Aᵢ)
    # -----------------------------------------------------------------------

    def test_contribution_ratio_capped_at_1(self):
        # Contributes 3× what it consumes → capped at 1.0
        record = NodeRecord(resources_consumed=10.0, resources_contributed=30.0)
        assert _contribution_ratio(record) == pytest.approx(1.0)

    def test_contribution_ratio_equal(self):
        record = NodeRecord(resources_consumed=20.0, resources_contributed=20.0)
        assert _contribution_ratio(record) == pytest.approx(1.0)

    def test_contribution_ratio_low(self):
        record = NodeRecord(resources_consumed=100.0, resources_contributed=10.0)
        # 10/100 = 0.1
        assert _contribution_ratio(record) == pytest.approx(0.1)

    # -----------------------------------------------------------------------
    # Hoarding penalty Φ(Aᵢ)
    # -----------------------------------------------------------------------

    def test_hoarding_penalty_no_hoard(self):
        # intake_ratio = 20/30 ≈ 0.67 < HOARD_THRESHOLD (2.0) → no penalty
        record = NodeRecord(resources_consumed=20.0, resources_contributed=30.0)
        assert _hoarding_penalty(record) == pytest.approx(0.0)

    def test_hoarding_penalty_at_threshold(self):
        # intake_ratio = 2.0 exactly → max(0, 2.0-2.0)=0 → no penalty
        record = NodeRecord(resources_consumed=20.0, resources_contributed=10.0)
        assert _hoarding_penalty(record) == pytest.approx(0.0)

    def test_hoarding_penalty_above_threshold(self):
        # intake_ratio = 80/5 = 16 → excess = 16 - 2 = 14 → Φ = 0.3 * 14 = 4.2, capped at 1.0
        record = NodeRecord(resources_consumed=80.0, resources_contributed=5.0)
        assert _hoarding_penalty(record) == pytest.approx(1.0)

    def test_hoarding_penalty_mild(self):
        # intake_ratio = 30/10 = 3 → excess = 3 - 2 = 1 → Φ = 0.3 * 1 = 0.3
        record = NodeRecord(resources_consumed=30.0, resources_contributed=10.0)
        assert _hoarding_penalty(record) == pytest.approx(LAMBDA * 1.0)

    # -----------------------------------------------------------------------
    # Full Γ(Aᵢ) computation
    # -----------------------------------------------------------------------

    def test_gamma_perfect_node(self):
        # H=1.0, C=1.0 (capped), Φ=0 → Γ = 0.5*1 + 0.5*1 - 0 = 1.0
        record = NodeRecord(
            requests_total=10, requests_truthful=10,
            resources_consumed=10.0, resources_contributed=50.0,
        )
        gamma, H, C, Phi, is_hoarder = compute_gamma(record)
        assert gamma == pytest.approx(1.0)
        assert is_hoarder is False

    def test_gamma_hoarder_node(self):
        # private_clinic_b stats: H=3/8=0.375, C=5/80=0.0625 (capped at 0.0625)
        # intake_ratio=80/5=16 → excess=14 → Φ = min(0.3*14,1) = 1.0
        # Γ = 0.5*0.375 + 0.5*0.0625 - 1.0 = 0.1875 + 0.03125 - 1.0 → clamped to 0.0
        record = NodeRecord(
            requests_total=8, requests_truthful=3,
            resources_consumed=80.0, resources_contributed=5.0,
        )
        gamma, _, _, _, is_hoarder = compute_gamma(record)
        assert gamma == pytest.approx(0.0)
        assert is_hoarder is True

    def test_gamma_neutral_node(self):
        # H=5/6≈0.833, C=30/30=1.0 (capped), Φ=0 (ratio=1<2)
        # Γ = 0.5*0.833 + 0.5*1.0 = 0.4165 + 0.5 = 0.9165
        record = NodeRecord(
            requests_total=6, requests_truthful=5,
            resources_consumed=30.0, resources_contributed=30.0,
        )
        gamma, _, _, Phi, _ = compute_gamma(record)
        assert gamma == pytest.approx(ALPHA * (5/6) + BETA * 1.0, rel=1e-3)
        assert Phi == pytest.approx(0.0)

    def test_gamma_clamped_below_zero(self):
        # Even with terrible stats, Γ must not go below 0
        record = NodeRecord(
            requests_total=10, requests_truthful=0,
            resources_consumed=500.0, resources_contributed=1.0,
        )
        gamma, _, _, _, _ = compute_gamma(record)
        assert gamma >= 0.0

    def test_gamma_clamped_above_one(self):
        # Perfect node must not exceed 1.0
        record = NodeRecord(
            requests_total=100, requests_truthful=100,
            resources_consumed=1.0, resources_contributed=1000.0,
        )
        gamma, _, _, _, _ = compute_gamma(record)
        assert gamma <= 1.0

    # -----------------------------------------------------------------------
    # reputation_calc tool function (DB-backed)
    # -----------------------------------------------------------------------

    def test_reputation_calc_known_node(self):
        result = reputation_calc("volunteer_group_a")
        assert result.node_id == "volunteer_group_a"
        assert 0.0 <= result.gamma <= 1.0
        # volunteer_group_a is cooperative so Γ should be reasonably high
        assert result.gamma >= 0.5

    def test_reputation_calc_hoarder_node(self):
        result = reputation_calc("private_clinic_b")
        assert result.is_hoarder is True
        assert result.gamma == pytest.approx(0.0)

    def test_reputation_calc_unknown_node_returns_defaults(self):
        # Unknown node should use neutral defaults (not crash)
        result = reputation_calc("nonexistent_node_xyz")
        assert 0.0 <= result.gamma <= 1.0


# ===========================================================================
# Phase 2 — Allocation tool tests
# ===========================================================================

class TestAllocationTools:

    def test_get_inventory_returns_dict(self):
        inv = get_inventory()
        assert isinstance(inv, dict)
        assert "oxygen" in inv
        assert "med_kits" in inv
        assert "water" in inv

    def test_get_inventory_positive_quantities(self):
        inv = get_inventory()
        for item, qty in inv.items():
            assert qty >= 0, f"Inventory item '{item}' has negative quantity."


# ===========================================================================
# Phase 3 — MCP Server & Tool Tests
# ===========================================================================

import json
import pytest
from mcp_server.dram_server import (
    query_telemetry,
    get_node_history,
    check_inventory as mcp_check_inventory,
    update_inventory,
    record_allocation,
    INVENTORY_PATH,
    AUDIT_LOG_PATH,
)


class TestMcpQueryTelemetry:

    def test_known_node_returns_correct_data(self):
        result = query_telemetry("community_centre_c")
        assert result["found"] is True
        assert result["node_id"] == "community_centre_c"
        assert result["flood_level_m"] == pytest.approx(0.8)
        assert result["medical_demand"] == "CRITICAL"
        assert result["population_at_risk"] == 620

    def test_unknown_node_returns_fallback(self):
        result = query_telemetry("nonexistent_xyz")
        assert result["found"] is False
        assert result["node_id"] == "nonexistent_xyz"
        # Should fall back to unknown_node defaults
        assert result["medical_demand"] != "UNKNOWN"

    def test_all_fields_present(self):
        result = query_telemetry("volunteer_group_a")
        for field in ["node_id", "found", "flood_level_m", "medical_demand",
                      "power_status", "connectivity", "population_at_risk",
                      "last_updated_utc", "landmark"]:
            assert field in result, f"Missing field: {field}"

    def test_volunteer_group_a_telemetry(self):
        result = query_telemetry("volunteer_group_a")
        assert result["found"] is True
        assert result["power_status"] in ("FULL", "PARTIAL", "NONE")


class TestMcpGetNodeHistory:

    def test_known_hoarder_node(self):
        result = get_node_history("private_clinic_b")
        assert result["found"] is True
        assert result["reputation"] == pytest.approx(0.4)
        assert "hoarding" in result["history"]

    def test_known_cooperative_node(self):
        result = get_node_history("volunteer_group_a")
        assert result["found"] is True
        assert result["reputation"] >= 0.7
        assert "truthful" in result["history"]

    def test_unknown_node_returns_defaults(self):
        result = get_node_history("totally_new_node")
        assert result["found"] is False
        assert result["reputation"] == pytest.approx(1.0)  # default
        assert result["history"] == []


class TestMcpInventoryTools:

    def test_check_inventory_oxygen(self):
        result = mcp_check_inventory("oxygen")
        assert result["found"] is True
        assert result["quantity"] >= 0

    def test_check_inventory_unknown_item(self):
        result = mcp_check_inventory("antimatter")
        assert result["found"] is False
        assert result["quantity"] is None

    def test_update_inventory_deduct_and_restore(self):
        before = mcp_check_inventory("med_kits")["quantity"]
        deduct_result = update_inventory("med_kits", -5)
        assert deduct_result["success"] is True
        assert deduct_result["new_qty"] == before - 5

        restore_result = update_inventory("med_kits", 5)
        assert restore_result["success"] is True
        after = mcp_check_inventory("med_kits")["quantity"]
        assert after == before

    def test_update_inventory_floors_at_zero(self):
        # Request a deduction larger than the stock
        current = mcp_check_inventory("water")["quantity"]
        result = update_inventory("water", -(current + 9999))
        assert result["new_qty"] == 0
        # Restore for other tests
        update_inventory("water", current)

    def test_update_inventory_unknown_item_fails(self):
        result = update_inventory("plasma_rifle", -1)
        assert result["success"] is False
        assert "not found" in result["error"]


class TestMcpRecordAllocation:

    def test_record_allocation_writes_audit_log(self):
        items = json.dumps([{"item": "water", "qty": 50}])
        result = record_allocation(
            order_id="ORD-test-audit-12345",
            node_id="volunteer_group_a",
            urgency="HIGH",
            approved=True,
            items_allocated=items,
            gamma_score=0.85,
            is_hoarder=False,
            summary="Unit test audit record.",
        )
        assert result["success"] is True
        assert result["order_id"] == "ORD-test-audit-12345"
        assert result["timestamp_utc"] != ""

        # Verify the record actually landed in the log
        with open(AUDIT_LOG_PATH, "r") as f:
            log = json.load(f)
        order_ids = [e["order_id"] for e in log.get("allocations", [])]
        assert "ORD-test-audit-12345" in order_ids

    def test_record_allocation_denied_request(self):
        items = json.dumps([])
        result = record_allocation(
            order_id="ORD-denied-99",
            node_id="private_clinic_b",
            urgency="LOW",
            approved=False,
            items_allocated=items,
            gamma_score=0.0,
            is_hoarder=True,
            summary="Request denied — hoarder with low urgency.",
        )
        assert result["success"] is True
        assert result["error"] == ""

