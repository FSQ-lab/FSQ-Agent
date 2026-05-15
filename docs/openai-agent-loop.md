# OpenAI Agent Task Loop

This project delegates the model/tool loop to OpenAI Agents SDK. fsq-agent does not reimplement a Responses API function-call loop. Instead, it prepares the runtime context, starts one SDK run, and then verifies the structured final output.

## High-Level Flow

1. The CLI loads a task file into `Task`. Only `description` is required.
2. `FsqAgent.run` loads private knowledge, matched flow templates, and configured skills.
3. `OpenAIAgentsRuntime.run_task` validates Azure OpenAI and SDK settings.
4. The runtime creates an `AsyncOpenAI` client and wraps it in `OpenAIProvider`.
5. The runtime enters configured MCP servers and builds local SDK tools.
6. The runtime creates an SDK `Agent` with instructions, tools, MCP servers, and the Azure model deployment.
7. `Runner.run` owns the loop: model turn, tool call, tool result, next model turn, and final answer.
8. The agent final answer must be JSON containing pre-plan steps, plan updates, satisfied criteria, unmet criteria, evidence, and errors.
9. The runtime converts pre-plan JSON entries into `StepResult` records and appends the raw SDK final output as the runner summary step.
10. `Verifier` parses the final JSON and determines `success`, `failed`, or `inconclusive`.
11. `ReportGenerator` writes the report and evidence manifest.

## SDK-Owned Loop

The project starts the loop here:

```python
result = await Runner.run(
    agent,
    input=self._build_task_input(task),
    max_turns=self.settings.openai_agents.max_turns,
    run_config=RunConfig(model_provider=provider),
)
```

Within that SDK call, the model can repeatedly call configured tools until it returns final output or reaches `max_turns`.

The loop shape is:

```text
Task description + instructions + knowledge + skills
        |
        v
OpenAI Agents SDK Runner.run
        |
        +--> model derives acceptance criteria and pre-plan
        +--> model requests MCP or local tool calls
        +--> SDK executes the tool call
        +--> tool result is returned to the model
        +--> model adjusts the pre-plan if needed
        +--> repeat until final JSON or max_turns
        |
        v
Structured final JSON
```

## Project Responsibilities

fsq-agent owns these parts around the SDK loop:

- Build the task input from `Task.description` and optional metadata.
- Load relevant knowledge and flow templates before the run.
- Load skills as descriptive instructions.
- Adapt configured MCP servers into SDK MCP server objects.
- Adapt configured CLI/file/shell capabilities into SDK tools.
- Require non-interactive execution.
- Require final JSON output.
- Convert final pre-plan entries into reportable `StepResult` records.
- Verify the final JSON independently from the prompt.

## Agent Responsibilities During The Loop

The SDK agent is instructed to do this inside `Runner.run`:

- Derive acceptance criteria from the task description, knowledge, flow templates, and skills.
- If the task is broad, use successful flow completion as the success standard.
- Create a pre-plan before external actions.
- Execute each step with MCP/tools/skills.
- Dynamically adjust the pre-plan when tool feedback or page state changes the best path.
- Finish with JSON only.

The required final JSON shape is:

```json
{
  "status": "success|failed|inconclusive",
  "summary": "string",
  "pre_plan": [
    {
      "step_id": 1,
      "action": "string",
      "success_criteria": ["string"],
      "status": "success|failed|skipped|adjusted"
    }
  ],
  "plan_updates": ["string"],
  "satisfied_criteria": ["string"],
  "unmet_criteria": ["string"],
  "evidence": ["string"],
  "errors": ["string"]
}
```

## Why There Is No Manual Tool Loop

OpenAI Agents SDK already provides the loop runner. Rebuilding the loop in this project would duplicate SDK behavior and increase the chance of relying on unstable or invented API details. The project boundary is therefore:

- SDK runner: turn continuation and tool dispatch.
- fsq-agent: task context, tool configuration, verification, reporting, and failure handling.

## Failure Handling

If SDK setup, MCP startup, tool execution, or the runner fails before final JSON, the runtime returns a failed `StepResult` so reporting can still complete.

If the evidence-based verifier agent returns parseable final JSON, `Verifier` preserves that `success`, `failed`, or `inconclusive` status as the final conclusion.

If the verifier task is unavailable, `Verifier` uses parseable runner final JSON as the fallback conclusion.

If no agent final JSON is parseable, `Verifier` falls back to failed-step diagnostics or marks the result `inconclusive`.