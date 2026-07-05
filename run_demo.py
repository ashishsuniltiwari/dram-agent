# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     https://www.apache.org/licenses/LICENSE-2.0

"""
DRAM Live Pipeline Simulation & Demo.

This script runs a complete interactive demo of the Disaster Resource
Allocation Mesh (DRAM) system. It simulates the cognitive multi-agent pipeline
(Intake Agent -> Assessor Agent -> Allocation Agent) and its integration with the
FastMCP database gateway tools, showing how the game-theoretic Rawlsian Maxim
reputation scores work under different scenarios.

Run it with:
    uv run python run_demo.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Literal

# Add root folder to sys.path to ensure local imports work
sys.path.insert(0, str(Path(__file__).parent))

from skills.reputation_calc import reputation_calc, NodeRecord, compute_gamma, DB_PATH
from mcp_server.dram_server import query_telemetry, get_node_history, check_inventory, update_inventory, record_allocation

# Define paths
TELEMETRY_PATH = Path("db/telemetry.json")
AUDIT_LOG_PATH = Path("db/allocations_log.json")


def print_header(title: str):
    print("\n" + "=" * 80)
    print(f" {title.upper()} ".center(80, "="))
    print("=" * 80)


def print_sub_header(title: str):
    print(f"\n--- {title} ---")


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def run_pipeline(scenario_name: str, raw_message: str, node_id: str, items_requested: list[str], beneficiary_count: int, default_urgency: str):
    print_header(f"Running Scenario: {scenario_name}")
    print(f"\nRaw Input Message:\n  \"{raw_message}\"")

    # Save original database states to restore them later
    orig_inventory = load_json(DB_PATH)
    orig_telemetry = load_json(TELEMETRY_PATH)
    orig_audit = load_json(AUDIT_LOG_PATH)

    try:
        # ===================================================================
        # NODE 1: META INTAKE AGENT (Simulation)
        # ===================================================================
        print_sub_header("Node 1: Meta Intake Agent (Veil of Ignorance)")
        print("[Agent Action] Parsing noisy text and structuring data...")
        time.sleep(0.5)

        # Detect clinical urgency based on text keywords (clinical triage)
        urgency = default_urgency
        lower_msg = raw_message.lower()
        if any(w in lower_msg for w in ["dying", "no oxygen", "unconscious", "critical", "suffocating"]):
            urgency = "CRITICAL"
        elif any(w in lower_msg for w in ["severe", "deteriorating", "urgent", "worsening"]):
            urgency = "HIGH"
        elif any(w in lower_msg for w in ["running low", "need soon", "stable"]):
            urgency = "MEDIUM"

        # Formulate IntakeReport
        intake_report = {
            "requesting_node_id": node_id,
            "location": query_telemetry(node_id).get("landmark", "Unknown"),
            "urgency": urgency,
            "requested_items": items_requested,
            "beneficiary_count": beneficiary_count,
            "raw_message_summary": raw_message[:70] + "..." if len(raw_message) > 70 else raw_message
        }
        print(json.dumps(intake_report, indent=2))

        # ===================================================================
        # NODE 2: ASSESSOR AGENT (Simulation)
        # ===================================================================
        print_sub_header("Node 2: Assessor Agent (Rawlsian Triage Gating)")
        print(f"[Agent Action] Evaluating triage for node '{node_id}' at urgency '{urgency}'...")
        time.sleep(0.5)

        # 1. Fetch live telemetry (MCP query)
        telemetry = query_telemetry(node_id)
        print(f"  -> Telemetry: Flood={telemetry['flood_level_m']}m, Med Demand={telemetry['medical_demand']}, Power={telemetry['power_status']}, Connectivity={telemetry['connectivity']}")

        # 2. Fetch history and compute reputation (Skills & MCP)
        history = get_node_history(node_id)
        rep_result = reputation_calc(node_id)
        gamma = rep_result.gamma
        is_hoarder = rep_result.is_hoarder

        print(f"  -> Rawlsian Gamma Math Gamma(A_i):")
        print(f"     Honesty Ratio H(A_i): {rep_result.honesty_ratio:.2f}")
        print(f"     Contribution Ratio C(A_i): {rep_result.contribution_ratio:.2f}")
        print(f"     Hoarding Penalty Phi(A_i): {rep_result.hoarding_penalty:.2f} (Is Hoarder: {is_hoarder})")
        print(f"     Resulting Score Gamma(A_i): {gamma:.2f}")

        # 3. Determine Triage Gate limits
        # Gate maps
        urgency_thresholds = {
            "CRITICAL": 0.0,
            "HIGH":     0.25,
            "MEDIUM":   0.50,
            "LOW":      0.70,
        }
        min_gamma = urgency_thresholds.get(urgency, 0.5)
        if is_hoarder:
            min_gamma += 0.15  # Penalty boost

        print(f"  -> Triage Threshold: Required Gamma >= {min_gamma:.2f}")

        # 4. Check Rawlsian Override rules
        approved = False
        reasoning = ""

        # Overrides: Critical urgency, large beneficiary count (>50), and perfect honesty ratio
        if urgency == "CRITICAL" and beneficiary_count > 50 and rep_result.honesty_ratio == 1.0:
            approved = True
            reasoning = f"Rawlsian Emergency Override Applied: Urgency is CRITICAL, beneficiary count is {beneficiary_count} (>50), and the node has perfect honesty history. Approved unconditionally."
        else:
            if gamma >= min_gamma:
                approved = True
                reasoning = f"Request Approved: Node Gamma ({gamma:.2f}) meets the urgency gate threshold ({min_gamma:.2f}) for urgency level '{urgency}'."
            else:
                approved = False
                reasoning = f"Request DENIED: Node Gamma ({gamma:.2f}) is below the required gate threshold ({min_gamma:.2f}) for urgency level '{urgency}'. Hoarding penalty or poor history detected."


        triage_decision = {
            "requesting_node_id": node_id,
            "approved": approved,
            "urgency": urgency,
            "gamma_score": round(gamma, 4),
            "is_hoarder": is_hoarder,
            "reasoning": reasoning
        }
        print(json.dumps(triage_decision, indent=2))

        # ===================================================================
        # NODE 3: ALLOCATION AGENT (Simulation)
        # ===================================================================
        print_sub_header("Node 3: Task Generator Agent (Urgency-based Allocation)")
        print("[Agent Action] Inspecting stocks and formulating final orders...")
        time.sleep(0.5)

        allocation_items = []
        summary = ""
        total_items_allocated = 0

        if not approved:
            summary = "Allocation cancelled: Request denied at triage stage."
            print(f"  -> Allocation Order: DENIED\n     Reason: {reasoning}")
        else:
            # Urgency caps
            ratio_caps = {
                "CRITICAL": 1.0,
                "HIGH":     0.75,
                "MEDIUM":   0.50,
                "LOW":      0.25,
            }
            cap = ratio_caps.get(urgency, 0.25)
            print(f"  -> Urgency cap applied: {cap * 100}% max allocation for urgency '{urgency}'")

            # Load active stock
            stock = check_inventory("oxygen")["all_items"]
            print(f"  -> Local Stock before allocation: {stock}")

            for item_req in items_requested:
                parts = item_req.split(":")
                item_name = parts[0]
                qty_req = int(parts[1]) if len(parts) > 1 else 1

                # Normalize item name
                normalized_item = item_name
                if "oxygen" in item_name:
                    normalized_item = "oxygen"
                elif "med" in item_name or "kit" in item_name:
                    normalized_item = "med_kits"
                elif "water" in item_name:
                    normalized_item = "water"

                available = stock.get(normalized_item, 0)
                target_qty = int(qty_req * cap)

                # Rawlsian Reserve Rule (Never deplete stock below 10% for future arrivals)
                reserve_floor = int(available * 0.10)
                allowed_qty = target_qty
                applied_reserve = False

                if (available - allowed_qty) < reserve_floor:
                    allowed_qty = max(0, available - reserve_floor)
                    applied_reserve = True

                # Deduct stock via MCP tool simulation
                update_inventory(normalized_item, -allowed_qty)

                denied_reason = ""
                if applied_reserve:
                    denied_reason = f"Rawlsian reserve applied (10% floor protected, stock was {available})"
                elif allowed_qty < target_qty:
                    denied_reason = "Insufficient local stock"

                allocation_items.append({
                    "item": normalized_item,
                    "requested_qty": qty_req,
                    "allocated_qty": allowed_qty,
                    "available_qty": available,
                    "allocation_ratio": round(allowed_qty / qty_req, 2) if qty_req > 0 else 0.0,
                    "denied_reason": denied_reason
                })
                if allowed_qty > 0:
                    total_items_allocated += 1

            new_stock = check_inventory("oxygen")["all_items"]
            print(f"  -> Local Stock after allocation: {new_stock}")
            summary = "Allocation successfully formulated. Resources dispatched."

        # Compile final order
        order_id = f"ORD-{node_id}-{urgency}"
        allocation_order = {
            "order_id": order_id,
            "requesting_node_id": node_id,
            "approved": approved,
            "urgency": urgency,
            "line_items": allocation_items,
            "total_items_allocated": total_items_allocated,
            "allocation_summary": summary
        }
        print(json.dumps(allocation_order, indent=2))

        # ===================================================================
        # PERSISTENCE & SECURITY AUDIT LOGGING (MCP)
        # ===================================================================
        print_sub_header("Security Gateway: Persisting Audit Trail")
        print("[Gateway Action] Writing log event to allocations_log.json...")
        time.sleep(0.5)

        log_res = record_allocation(
            order_id=order_id,
            node_id=node_id,
            urgency=urgency,
            approved=approved,
            items_allocated=json.dumps(allocation_items),
            gamma_score=round(gamma, 4),
            is_hoarder=is_hoarder,
            summary=summary
        )
        print(f"  -> Audit Log response: {log_res}")

    finally:
        # Restore databases back to initial state so we don't pollute Git workspace
        save_json(DB_PATH, orig_inventory)
        save_json(TELEMETRY_PATH, orig_telemetry)
        save_json(AUDIT_LOG_PATH, orig_audit)


def main():
    while True:
        print_header("DRAM Multi-Agent Triage Simulator")
        print("Select a scenario to execute:")
        print("  1. Cooperative Node (Volunteer Group A) — Requests high-urgency kits (PASSED)")
        print("  2. Selfish Node (Private Clinic B) — Requests high-urgency oxygen (BLOCKED)")
        print("  3. Rawlsian Emergency Override (Community Centre C) — Massive crisis (APPROVED)")
        print("  4. Exit")
        
        try:
            choice = input("\nEnter choice (1-4): ").strip()
            if choice == "1":
                run_pipeline(
                    scenario_name="Cooperating Volunteer Group",
                    raw_message="Volunteer Group A here. The water is rising in Kumbharwada. We need 20 medical kits to treat injured children.",
                    node_id="volunteer_group_a",
                    items_requested=["med_kits:20"],
                    beneficiary_count=15,
                    default_urgency="HIGH"
                )
            elif choice == "2":
                run_pipeline(
                    scenario_name="Selfish Clinic Hoarding",
                    raw_message="Private Clinic B urgent request. We require 60 oxygen cylinders immediately. Deliver to our secure private facility.",
                    node_id="private_clinic_b",
                    items_requested=["oxygen:60"],
                    beneficiary_count=8,
                    default_urgency="HIGH"
                )
            elif choice == "3":
                run_pipeline(
                    scenario_name="Rawlsian Emergency Override",
                    raw_message="Dharavi Main Road Community Centre C. Severe flooding, power is completely out! 300 families are trapped inside. We have multiple unconscious patients. Need oxygen cylinders and water urgently!",
                    node_id="community_centre_c",
                    items_requested=["oxygen:80", "water:500"],
                    beneficiary_count=350,
                    default_urgency="CRITICAL"
                )
            elif choice == "4":
                print("\nExiting DRAM Simulator. Stay safe!")
                break
            else:
                print("\nInvalid choice. Please select 1-4.")
        except KeyboardInterrupt:
            print("\nExiting DRAM Simulator.")
            break
        
        input("\nPress Enter to return to menu...")


if __name__ == "__main__":
    main()
