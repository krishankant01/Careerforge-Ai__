# LangGraph Multi-Agent System

Phase 7 introduced a multi-agent orchestrated backend using **LangGraph**.

## Architecture
Instead of single-shot LLM requests or rigid chains, we use a dynamic graph of AI agents. The graph consists of:
1. **Supervisor Agent**: The orchestrator. It receives the user's message, analyzes the intent, and conditionally routes the request to the appropriate sub-agent.
2. **Sub-Agents**: Specialized workers (e.g., Resume Agent, Job Agent, Interview Agent, Code Review Agent, Project Recommendation Agent).

## Why Agents?
- **Separation of Concerns**: A single LLM prompt trying to handle mock interviews, resume writing, and code reviews simultaneously degrades in quality.
- **Tools**: Each agent can be equipped with its own specific Python tools (e.g., the GitHub Agent has a tool to fetch a repository tree, the Resume Agent can read the RAG index).
- **State Management**: LangGraph passes an `AgentState` object between nodes, ensuring context (like the user's target job) is preserved seamlessly across turns without passing large string blobs manually.

## Workflow Example
1. User: "Give me a mock interview for my target job."
2. **Supervisor** reads state, routes to **Interview Agent**.
3. **Interview Agent** reads `AgentState.user_context` (which contains the parsed resume and job description), and generates a highly personalized technical question.
4. User replies with an answer.
5. **Interview Agent** evaluates the answer and provides feedback.
