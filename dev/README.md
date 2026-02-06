# Development Tracking

This directory contains structured documentation for ongoing development tasks. Each task has its own subdirectory with comprehensive planning and progress tracking.

---

## Active Tasks

- **[bitcoin-blockchain-core]** - Bitcoin blockchain full archival node implementation (production-quality, no P2P) - Started: 2026-02-06
  - Path: `dev/active/bitcoin-blockchain-core/`
  - Status: Not Started
  - Goal: Implement Bitcoin-accurate blockchain with PoW, UTXO model, transactions, fork handling, and all consensus rules

---

## Task Structure

Each task directory contains:

- **plan.md** - Complete implementation plan with all technical details
- **tasks.md** - Actionable checklist for tracking progress (update as you work)
- **context.md** - Quick reference for files, decisions, dependencies, and constraints

---

## How to Use

1. **Starting Work**: Read `plan.md` to understand the full scope
2. **During Development**:
   - Check off tasks in `tasks.md` as you complete them
   - Add progress notes with dates in the Progress Notes section
   - Update task status (Not Started → In Progress → Completed)
3. **Context Recovery**: If you lose context, `context.md` has all key information
4. **After Completion**: Move task from `active/` to `completed/`

---

## Progress Tracking

Update task progress in `tasks.md`:
- [ ] Not Started
- [→] In Progress
- [✓] Completed

Calculate progress: `(completed tasks / total tasks) × 100%`

---

## Notes

- This structure survives context resets - just reference these files to resume work
- Keep documentation in sync with actual implementation
- Use task dependencies to ensure proper implementation order
- Add dated progress notes to track blockers and decisions
