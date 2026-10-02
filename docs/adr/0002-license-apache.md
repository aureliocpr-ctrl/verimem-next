# ADR-0002 — Apache-2.0 for the library

Status: accepted (2026-10-02)

## Context
The goal is revenue. The library runs inside the user's process; AGPL keeps exactly the
companies that would pay away. Every main competitor (Mem0, Zep/Graphiti, Cognee, Letta) is
Apache-2.0 or MIT. The code itself is not the moat: calibration data, domain expertise,
service quality and speed are.

## Decision
The library, CLI, MCP server and evaluation kit are Apache-2.0. Revenue comes from services
(memory reliability audits, integration pilots) and, later, from a hosted API and enterprise
features under a separate commercial license, kept outside this repository.

## Consequences
- Anyone can use and fork the code, including competitors.
- Contributions require no CLA under Apache-2.0; if a dual-license model is ever needed, add a
  CLA before accepting external contributions.
