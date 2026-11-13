# Rules for agents

## Project
A paper-trading lab for day trading. An LLM helps make trading
decisions, and I evaluate the results day by day.

## Rules
- Paper trading only. Never write code that can place real-money
  orders. Only use Alpaca's paper endpoint.
- Secrets live in .env. Never print, log or commit them.
- Every module gets pytest tests. Tests use fake (mocked) data
  and never call real APIs.
- Do not run AWS or deploy commands. AWS is not needed yet.
- Git: commit only on your own task branch. Never push, and never
  change main. I merge and push myself.
- Agents write the code. I review every change.
- Do only your own role. A planner does not write code. A reviewer
  does not change code.
- Keep changes small so I can learn from them. Only create or
  change the files your task is about. If another file needs
  changing, ask first.

## Workflow
Planner → Builder → Tester. I am the reviewer.
- Planner: writes the plan. No code.
- Builder: writes the code from the plan.
- Tester: writes and runs the pytest tests. Does not change the
  Builder's code; reports problems instead.
- Every change waits for my review before it is merged.

