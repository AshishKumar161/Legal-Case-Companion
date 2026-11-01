---
name: subagent-orchestrator
description: >-
  Workflows and best practices for orchestrating specialist subagents, managing shared cross-agent
  memory, and assigning peer reviews using the lcc-agent-system MCP server.
---

# Subagent Orchestrator Skill

Use this skill when tackling multi-faceted features, cross-layer refactors, or tasks requiring specialized roles (Architect, Backend, Frontend, Legal NLP, QA, Security).

## Available Orchestrator Tools

- `create_agent_task(title, assigned_agent, description, priority)`: Create a task for a subagent.
- `list_agent_tasks(status_filter, agent_filter)`: List active or pending tasks.
- `update_agent_task(task_id, status, notes, output_summary)`: Update status to `in_progress`, `review_requested`, or `completed`.
- `save_shared_memory(key, content, category, tags)`: Record persistent context accessible to all agents.
- `recall_shared_memory(query, category)`: Query shared decisions by keyword or category.
- `request_subagent_review(task_id, reviewing_agent, review_checklist)`: Request a peer review.
- `get_agent_ecosystem_overview()`: Executive summary of current team state.

## Specialist Subagent Roles

1. `system_architect`: Enforces schema contracts, domain boundaries, and ADRs.
2. `backend_engineer`: Implements FastAPI routers, SQLAlchemy models, and domain services.
3. `frontend_engineer`: Builds Next.js 16 components, UI tokens, and client flows.
4. `legal_nlp_agent`: Legal citation integrity, Kanoon retrieval, and case classification.
5. `qa_engineer`: Test runner execution, regression verification, and load tests.
6. `security_auditor`: Evidence locker quarantine, token rotation, and RBAC authorization.

## Execution Checklist

1. **Break Down Request**: Decompose complex user goals into atomic tasks for each specialist agent.
2. **Assign Tasks**: Call `create_agent_task` with specific instructions and priorities.
3. **Execute & Document**: Update tasks with findings and store critical architecture notes via `save_shared_memory`.
4. **Peer Review**: Before final delivery, assign a review to `@security_auditor` or `@qa_engineer`.
5. **Verify & Close**: Mark completed tasks via `update_agent_task(status='completed')`.
