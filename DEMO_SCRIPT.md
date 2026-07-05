# Kaggle Capstone Demo Video Script: Disaster Resource Allocation Mesh (DRAM) 🎙️📹

This document contains the complete script, visual guidelines, and timing cues for recording the 3-minute capstone presentation video for the Kaggle Judges.

*   **Target Duration:** ~3 Minutes
*   **Format:** Screen recording (Terminal + Code Editor) with Voiceover. No slides or face-cam required.

---

## 🎬 Section 1: The Hook (0:00 - 0:45)

*   **Visual on Screen:**
    *   Show a clean title card in your code editor or browser:
        *   **Title:** *Disaster Resource Allocation Mesh (DRAM)*
        *   **Subtitle:** *Game-Theoretic Multi-Agent Triage and Zero-Trust Allocation*
    *   At **0:25**, switch the screen to the system architecture diagram (e.g., the Mermaid diagram in `README.md`).

*   **Voiceover Script:**
    > "In a severe disaster, traditional AI architectures collapse. When a single LLM is faced with high-stress resource requests, it falls victim to **generous-agent bias**—approving every emotional plea and depleting critical supplies early—or it suffers **cognitive collapse** under multi-step reasoning.
    >
    > To solve this for *Aapda Mitra* volunteers operating during monsoon floods in Dharavi, Mumbai, I built **DRAM**—the Disaster Resource Allocation Mesh. 
    >
    > DRAM bypasses LLM cognitive limitations by splitting the triage workflow into a 3-node directed acyclic graph using **Google's Agent Development Kit** and the `google-genai` SDK, routing requests through specialized Intake, Assessor, and Allocation Agents."

---

## 💻 Section 2: Code & Theory (0:45 - 1:30)

*   **Visual on Screen:**
    *   Open your code editor (e.g., VS Code) and navigate to `skills/reputation_calc.py`.
    *   Highlight the mathematical formula block for $\Gamma(A_i)$ and the `_hoarding_penalty` function.
    *   At **1:15**, open `agents/assessor_agent.py` and show the clinical urgency gate thresholds.

*   **Voiceover Script:**
    > "Let's look at the implementation. To guarantee equity under scarcity, we implement the **Rawlsian Maximin Invariant** inside a custom Python skill. The formula calculates a composite accountability score $\Gamma(A_i)$ based on a node's historical honesty and contribution ratios.
    >
    > If a node attempts to hoard resources, our non-linear hoarding penalty $\Phi(A_i)$ automatically triggers, dragging their score down to block selfish exploitation.
    >
    > The Assessor Agent uses this reputation score to gate requests based on clinical urgency, while the Allocation Agent enforces safety reserve floors—ensuring we never deplete local stock below 10% for future survivors."

---

## 🚀 Section 3: Live Pipeline Demo (1:30 - 2:30)

*   **Visual on Screen:**
    *   Open your terminal and type:
        ```bash
        uv run python run_demo.py
        ```
    *   When the menu pops up:
        1.  Type `1` and press **Enter** to run the Cooperating Volunteer scenario. Let the terminal scroll, highlight the approved status and the `15 med_kits` allocation. Press **Enter** to return to the menu.
        2.  Type `2` and press **Enter** to run the Selfish Node scenario. Highlight the `Gamma = 0.00` reputation calculation and the denied allocation. Press **Enter** to return to the menu.
        3.  Type `3` and press **Enter** to run the Rawlsian Emergency Override scenario. Highlight the critical urgency, the override trigger, and the 100% allocation.

*   **Voiceover Script:**
    > "Let's run the interactive pipeline simulation to see this in action. 
    >
    > **First, we run Scenario 1: A cooperating volunteer group.** The Intake Agent parses the noisy request, the Assessor calculates a high Gamma score of `0.95`, and the request is approved. The Allocation Agent caps the output at 75% for high urgency, and successfully dispatches 15 kits.
    >
    > **Next, Scenario 2: A selfish node attempting to hoard.** Private Clinic B requests 60 oxygen cylinders. The Assessor Agent detects a severe hoarding penalty and calculates a Gamma score of `0.00`. The triage gate immediately blocks the request to protect community resources.
    >
    > **Finally, Scenario 3: The Rawlsian emergency override.** When a community hall with 300 trapped families requests critical aid, the Assessor triggers our emergency rule, bypassing the contribution ratio to prioritize saving lives first."

---

## 🔒 Section 4: Security & Verification (2:30 - 3:00)

*   **Visual on Screen:**
    *   Open `db/allocations_log.json` to show the append-only audit trail.
    *   Open the terminal and run the test suite:
        ```bash
        uv run python -m pytest tests/test_mesh.py -v
        ```
    *   Let the green `36 passed` output fill the screen.

*   **Voiceover Script:**
    > "To guarantee zero-trust, all database operations are mediated by a FastMCP server acting as a secure gateway. Agents can never write directly to the state; they must call deterministic tools that protect stock levels and log every action to an append-only audit trail.
    >
    > With a complete test suite of 36 unit tests validating our game-theoretic invariants, DRAM provides a robust, offline-first shield for crisis logistics. Thank you!"

---

## 💡 Quick Tips for Recording:
1.  **Resolution:** Record in 1080p (1920x1080) for clear text readability.
2.  **Zoom:** Zoom in your code editor (`Ctrl` + `+`) and terminal so judges can easily read the code and outputs on mobile or small screens.
3.  **Pace:** Keep your speaking pace steady and energetic. 3 minutes goes by fast!
