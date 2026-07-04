# Disaster Resource Allocation Mesh (DRAM) 🌧️⚕️📦

An offline-first, game-theoretically secure multi-agent resource triage and allocation system designed for **Aapda Mitra** volunteers operating in the high-density sub-localities of **Dharavi, Mumbai** during severe monsoon flooding crises.

DRAM is built on top of **Google's Agent Development Kit (ADK)** and the `google-genai` SDK. It coordinates resource allocation under severe supply constraints by translating game-theoretic principles—specifically the **Rawlsian Maximin principle** and non-linear hoarding penalties—into an automated multi-agent pipeline.

---

## 🏗️ System Architecture

DRAM splits the cognitive burden of disaster resource triage across three distinct, specialized LLM-powered agents and a deterministic database security gateway. This prevents the "generous-agent bias" and LLM cognitive collapse typically seen when a single agent attempts to parse, evaluate, and allocate resources simultaneously.

```mermaid
graph TD
    %% Define Nodes
    RawInput[/"Noisy Volunteer Messages<br>(SMS / LoRa Mesh)"/]
    
    subgraph CognitivePipeline ["ADK Multi-Agent Cognitive Pipeline"]
        IntakeAgent["Node 1: Meta Intake Agent<br>(Veil of Ignorance Parser)"]
        AssessorAgent["Node 2: Assessor Agent<br>(Rawlsian Triage Gate)"]
        AllocationAgent["Node 3: Task Generator Agent<br>(Allocation Order Formulator)"]
    end
    
    subgraph DataSecurityGateway ["Security Gateway & Persistence (MCP)"]
        MCPServer["DRAM FastMCP Server"]
        TelemetryDB[("Telemetry DB<br>(telemetry.json)")]
        InventoryDB[("Inventory DB<br>(dharavi_inventory.json)")]
        AuditLog[("Audit Log<br>(allocations_log.json)")]
    end

    %% Define Flow
    RawInput -->|Noisy Text| IntakeAgent
    IntakeAgent -->|IntakeReport JSON| AssessorAgent
    
    AssessorAgent -->|Call Tool| MCPServer
    MCPServer <-->|Read Node Stats| InventoryDB
    MCPServer <-->|Read Live Sensors| TelemetryDB
    
    MCPServer -->|Return Γ(Aᵢ) & is_hoarder| AssessorAgent
    AssessorAgent -->|TriageDecision JSON| AllocationAgent
    
    AllocationAgent -->|Call Tool| MCPServer
    MCPServer <-->|Read Current Stock| InventoryDB
    MCPServer -->|Deduct Stock & Write Audit| MCPServer
    MCPServer -->|Commit Update| InventoryDB
    MCPServer -->|Append Event| AuditLog
    
    AllocationAgent -->|Final AllocationOrder JSON| Output[/"Final Resource Order"/]

    %% Styles
    classDef agent fill:#e8f0fe,stroke:#1a73e8,stroke-width:2px,color:#1a73e8;
    classDef db fill:#f1f3f4,stroke:#5f6368,stroke-width:2px,color:#3c4043;
    classDef input fill:#e6f4ea,stroke:#137333,stroke-width:2px,color:#137333;
    
    class IntakeAgent,AssessorAgent,AllocationAgent agent;
    class TelemetryDB,InventoryDB,AuditLog,MCPServer db;
    class RawInput,Output input;
```

---

## 📈 The Game-Theoretic Invariant: Rawlsian Maximin Score $\Gamma(A_i)$

To prevent selfish nodes (e.g., private clinics hoarding oxygen cylinders) from depleting vital disaster supplies, DRAM computes a composite **Rawlsian Maximin accountability score** $\Gamma(A_i)$ for any requesting node $A_i$.

$$\Gamma(A_i) = \alpha \cdot H(A_i) + \beta \cdot C(A_i) - \Phi(A_i)$$

Where:
* **$H(A_i)$ (Honesty Ratio):** The ratio of historically verified truthful resource requests to total requests:
  $$H(A_i) = \frac{\text{Requests Truthful}}{\text{Requests Total}}$$
* **$C(A_i)$ (Contribution Ratio):** The ratio of resources contributed back to the mesh versus resources consumed, capped at $1.0$ to prevent gaming:
  $$C(A_i) = \min\left(1.0, \frac{\text{Resources Contributed}}{\text{Resources Consumed}}\right)$$
* **$\Phi(A_i)$ (Hoarding Penalty):** A non-linear penalty triggered when the intake-to-contribution ratio exceeds the acceptable safety threshold ($\text{Threshold} = 2.0$):
  $$\Phi(A_i) = \min\left(1.0, \lambda \cdot \max\left(0, \frac{\text{Resources Consumed}}{\text{Resources Contributed}} - \text{Threshold}\right)\right)$$
  *(Default parameters: weights $\alpha = 0.5$, $\beta = 0.5$, severity penalty $\lambda = 0.3$)*

The score is clamped strictly: $\Gamma(A_i) \in [0.0, 1.0]$.

### 🚪 Triage Gating Rubric
Honest nodes are evaluated against urgency-based reputation gates, while flagged hoarding nodes ($\Phi > 0$) face a strict **+0.15 threshold penalty boost**:

| Urgency Level | Min $\Gamma(A_i)$ (Honest Node) | Min $\Gamma(A_i)$ (Flagged Hoarder) |
|---|---|---|
| **CRITICAL** (Life Threat) | $\ge 0.00$ | $\ge 0.15$ |
| **HIGH** (Severe Condition) | $\ge 0.25$ | $\ge 0.40$ |
| **MEDIUM** (Stable / Needs Aid) | $\ge 0.50$ | $\ge 0.65$ |
| **LOW** (Preventive / Comfort) | $\ge 0.70$ | $\ge 0.85$ |

> [!TIP]
> **Rawlsian Override:** If an intake request is marked `CRITICAL`, will benefit more than `50` people, and has zero history of inventory fraud, the Assessor Agent overrides the reputation gates and approves the request unconditionally.

---

## 🔒 MCP Server & Security Gateway

The DRAM MCP Server (`dram-mesh-server`) acts as an air-gapped **Zero-Trust Security Gateway**. LLMs do not have direct write access to database files. All reads and modifications to telemetry, inventory, and audit logs are mediated by deterministic Python functions exposed through the Model Context Protocol (MCP).

Exposed tools include:
1. **`query_telemetry`**: Retrieves live sensor data (flood level in meters, medical demand, power status, population at risk) for the target sub-locality.
2. **`get_node_history`**: Returns the node's prior reputation metrics, resource ratios, and history tags.
3. **`check_inventory`**: Checks current stock levels of critical supplies (oxygen, med_kits, water).
4. **`update_inventory`**: Atomically updates stock level using signed deltas (protects against negative stock underflows).
5. **`record_allocation`**: Appends immutable allocation events into `allocations_log.json` for forensic auditing.

---

## 📂 Project Directory Structure

```
dram-agent/
├── agents/
│   ├── intake_agent.py      # Meta Intake Agent (Veil of Ignorance parsing)
│   ├── assessor_agent.py    # Assessor Agent (Rawlsian triage gating)
│   └── allocation_agent.py  # Task Generator Agent (Urgency-capped allocation)
├── db/
│   ├── dharavi_inventory.json # Local District War Room stock & node profiles
│   ├── telemetry.json       # Simulated real-time sensor & disaster status
│   └── allocations_log.json # Append-only immutable audit trail for allocations
├── mcp_server/
│   ├── __init__.py
│   └── dram_server.py       # FastMCP Server exposing the 5 gateway tools
├── skills/
│   └── reputation_calc.py   # Invariant math implementation for Γ(Aᵢ) & Φ(Aᵢ)
├── tools/
│   ├── __init__.py
│   └── dram_toolset.py      # ADK McpToolset factory class wiring
├── tests/
│   └── test_mesh.py         # Complete verification test suite (36 tests)
├── main.py                  # ADK Workflow definition & App entrypoint
├── pyproject.toml           # Project dependencies managed via uv
└── README.md                # System documentation
```

---

## 🧪 Verification & Testing

DRAM features a comprehensive test suite covering:
* **Workflow Compilation:** Validates that the ADK 3-node graph structure initializes correctly.
* **Reputation Mathematics:** Asserts edge cases for honesty ratios, contribution caps, non-linear hoarding penalties, and $\Gamma$ clamping behavior.
* **MCP Server Integration:** Verifies tool actions, inventory subtraction logic, and audit trail logging.

To run the test suite, ensure you have `uv` installed, then execute:

```bash
uv run python -m pytest tests/test_mesh.py -v
```

All 36 tests run and pass locally:

```
tests/test_mesh.py::TestBoilerplate::test_app_initialization PASSED
tests/test_mesh.py::TestBoilerplate::test_workflow_compilation PASSED
tests/test_mesh.py::TestReputationMath::test_honesty_ratio_perfect PASSED
...
tests/test_mesh.py::TestMcpRecordAllocation::test_record_allocation_writes_audit_log PASSED
======================= 36 passed in 3.30s =======================
```

---

## 👥 Aapda Mitra Integration & Live Execution

When running the DRAM App workflow, the execution flow operates as follows:
1. A volunteer submits a noisy mesh message:
   > *"Volunteer Camp A here at 90 Feet Road. We have a severe flood rising fast (around 0.8m). Need oxygen cylinders urgently for 65 patients in the camp. We are running low."*
2. **`intake_agent`** parses this into:
   ```json
   {
     "requesting_node_id": "volunteer_group_a",
     "location": "90 Feet Road",
     "urgency": "CRITICAL",
     "requested_items": ["oxygen_cylinder:65"],
     "beneficiary_count": 65,
     "raw_message_summary": "Volunteer Camp A at 90 Feet Road requests urgent oxygen cylinders due to rising flood waters."
   }
   ```
3. **`assessor_agent`** fetches the node history using `get_node_history("volunteer_group_a")` (obtaining $\Gamma \approx 0.95$, `is_hoarder=False`). Since $\Gamma \ge 0.0$ (Critical threshold), the request is approved.
4. **`allocation_agent`** checks inventory via `get_inventory()` and creates the final allocation:
   - Cap limit checked (CRITICAL = 100% of requested).
   - Rawlsian 10% reserve floor applied (never deplete below 10% of total stock).
   - Deducts stock via `update_inventory` and writes to the audit log via `record_allocation`.
