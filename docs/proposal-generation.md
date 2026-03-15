# Proposal Generation: Two Code Paths Explained

This document explains the two proposal generation functions that exist in `backend/app/services/ai_service.py`, when each is used, and why both exist.

---

## The Short Answer

| Function | Used by | When to use |
|---|---|---|
| `generate_three_proposals()` | `ProposalService` → Celery task | **Primary path.** Normal user flow — debate first, then 3 PRDs |
| `generate_council_variations()` | Not called anywhere currently | **Legacy path.** Parallel generation, no debate phase |

If you are building a new feature or endpoint that generates proposals, use `generate_three_proposals()`.

---

## Path 1: `generate_three_proposals()` — The Research Workflow

**File:** `backend/app/services/ai_service.py`  
**Called by:** `generate_proposal_content_task` in `backend/app/services/proposal_service.py`  
**Triggered when:** A user clicks **Execute** on a DRAFT proposal in the UI

### What it does

This is a two-phase process:

**Phase 1 — Debate**

All three personas (Legacy Keeper, Innovator, Mediator) discuss the architectural task in a single multi-turn exchange. Up to 6 turns run in sequence. This produces a debate transcript.

**Phase 2 — Per-persona PRDs**

Each persona reads the debate transcript and writes their own full architectural proposal (a structured PRD in Markdown). The three calls run sequentially, not in parallel, so each persona can reflect on what was said in the debate.

**Output:** Exactly 3 `ProposalVariation` records saved to the database — one per persona (`LEGACY_KEEPER`, `INNOVATOR`, `MEDIATOR`).

### Why this approach

The research design requires three *distinct* proposals that reflect different strategic positions. Running the debate first forces each persona to engage with the other viewpoints before writing, which produces more differentiated outputs and aligns with the thesis research questions (RQ1: which proposal do participants trust more? RQ2: does each persona stay consistent?).

### Flow diagram

```
User clicks Execute
       │
       ▼
Celery task: generate_proposal_content_task(proposal_id)
       │
       ├── Fetch proposal + stakeholders + RAG chunks (sync, Part 1)
       │
       └── run_ai_generation() (async, Part 2)
               │
               ▼
       ai_service.generate_three_proposals()
               │
               ├── Phase 1: _conduct_debate()
               │     └── Single Claude call → debate transcript (up to 6 turns)
               │
               └── Phase 2: _generate_persona_proposal() × 3
                     ├── Legacy Keeper PRD (reads debate transcript)
                     ├── Innovator PRD (reads debate transcript)
                     └── Mediator PRD (reads debate transcript)
                           │
                           ▼
               3 × ProposalVariation saved to DB
               Proposal status → COMPLETED
```

---

## Path 2: `generate_council_variations()` — The Legacy Path

**File:** `backend/app/services/ai_service.py`  
**Called by:** Nothing — currently unused  
**Status:** Kept for reference; not part of the active user flow

### What it does

Fetches all active `PromptTemplate` records from the database and calls `generate_single_variation()` for each one **in parallel** using `asyncio.gather()`. There is no debate phase — each persona generates a proposal independently without seeing the others' viewpoints.

**Output:** A list of proposal dicts — one per active template in the database.

### Why it still exists

This was the original generation approach before the research design was finalised. It is more flexible (adding a persona means adding a database record, not changing code) and faster (parallel calls). However, it produces less differentiated proposals because the personas never interact.

It is kept in the codebase in case the debate-first approach needs to be compared against the parallel approach, or in case a faster generation mode is needed in future.

### Key differences from Path 1

| | `generate_three_proposals` | `generate_council_variations` |
|---|---|---|
| Debate phase | ✅ Yes | ❌ No |
| Execution | Sequential | Parallel |
| Persona source | Hardcoded (3 personas) | Database `PromptTemplate` records |
| Output count | Always exactly 3 | One per active template |
| Currently used | ✅ Yes | ❌ No |

---

## The Baseline Path (Condition A)

There is a third, separate generation path used exclusively by the research experiment:

**Function:** `BaselineService.generate_baseline_proposal()`  
**File:** `backend/app/services/baseline_service.py`  
**Called by:** `POST /api/v1/experiments/baseline` endpoint  
**Used for:** Generating the single-agent Condition A proposal for A/B comparison

This uses a single generic "senior architect" persona with no Council debate. It uses the same RAG context as the multi-agent path to ensure a fair comparison. Output is a single `ProposalVariation` with `agent_persona = BASELINE`.

---

## Adding a New Persona

If you want to add a fourth persona to the Council:

1. Add the persona slug to the `personas_config` list inside `generate_three_proposals()` in `ai_service.py`
2. Add the corresponding `AgentPersona` enum value in `backend/app/models/proposal.py`
3. Add the matching TypeScript enum value in `frontend/src/types/index.ts`
4. Update the frontend `VariationCard` and `ProposalDetailPage` components to display the new variation

> Note: If you are using `generate_council_variations()` instead, you only need to add a new `PromptTemplate` record via the Admin Console — no code changes required. This is the advantage of the template-driven approach.

---

## Summary

- **For normal proposal generation:** `generate_three_proposals()` is the active path. It runs a debate first, then generates 3 PRDs.
- **For the research experiment baseline:** `BaselineService.generate_baseline_proposal()` generates a single-agent Condition A proposal.
- **`generate_council_variations()`** is the legacy parallel path — it works but is not currently wired up to any endpoint.