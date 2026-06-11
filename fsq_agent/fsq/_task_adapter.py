import json
from typing import Any

from fsq_agent.models import ANDROID_ACTION_DEFINITIONS_BY_NAME, FsqCase, Task, VerificationCriterion, VerificationCriterionKind


class FsqTaskAdapter:
    def to_task(self, case: FsqCase) -> Task:
        key_actions = self.extract_ordered_key_actions(case)
        verification_goal = f"Goal completed: {case.config.name}"
        verification_criteria = self.extract_verification_criteria(case, key_actions, verification_goal)
        return Task(
            id=case.id,
            name=case.config.name,
            description=self.render_description(case),
            acceptance_criteria=[criterion.text for criterion in verification_criteria],
            key_actions=key_actions,
            verification_goal=verification_goal,
            verification_criteria=verification_criteria,
        )

    def extract_ordered_key_actions(self, case: FsqCase) -> list[str]:
        key_actions = [
            rendered
            for command in case.commands
            if (rendered := self._render_key_action(command)) is not None
        ]
        if key_actions:
            return [f"Key action {index}: {action}" for index, action in enumerate(key_actions, start=1)]
        return []

    def extract_verification_criteria(
        self,
        case: FsqCase,
        key_actions: list[str] | None = None,
        verification_goal: str | None = None,
    ) -> list[VerificationCriterion]:
        key_actions = key_actions if key_actions is not None else self.extract_ordered_key_actions(case)
        verification_goal = verification_goal or f"Goal completed: {case.config.name}"
        criteria = [
            VerificationCriterion(
                text=verification_goal,
                kind="goal",
                source="fsq_case_goal",
            )
        ]
        key_action_index = 0
        for command in case.commands:
            command_name = self._command_name(command)
            if self._render_key_action(command) is None:
                continue
            key_action_index += 1
            text = key_actions[key_action_index - 1] if key_action_index <= len(key_actions) else self._render_command(command)
            criteria.append(
                VerificationCriterion(
                    text=text,
                    kind=self._criterion_kind(command_name),
                    source="fsq_key_action",
                    key_action_index=key_action_index,
                )
            )
        return criteria

    def render_description(self, case: FsqCase) -> str:
        config = case.config
        preconditions = self._infer_preconditions(case)
        lines = [
            "Run this FSQ AI Test DSL case as a goal-driven automation task.",
            "",
            "The FSQ YAML is authoritative for the intended scenario, but it is advisory for execution details. It may omit transient dialogs, setup, recovery, or state-dependent steps, and it may contain steps that are unnecessary in the live session. Use the flow and locators as preferred hints while adapting to the actual UI state.",
            "",
            "Case metadata:",
            f"- Source: {case.path}",
            f"- Name: {config.name}",
            f"- Description: {config.description or 'not provided'}",
            f"- Platform: {config.platform}",
        ]
        if config.app_id:
            lines.append(f"- App ID: {config.app_id}")
        if config.url:
            lines.append(f"- URL: {config.url}")
        if config.tags:
            lines.append(f"- Tags: {', '.join(config.tags)}")
        if config.env:
            env_refs = ", ".join(f"{key}={value}" for key, value in config.env.items())
            lines.append(f"- Environment variable references: {env_refs}")
        lines.extend([
            "",
            "Execution guidance:",
            "- Prefer explicit FSQ locators such as resourceId, accessibilityId, text, xpath, and className when available.",
            "- For Android cases, use the configured Appium MCP tools for device, session, app lifecycle, element lookup, taps, text input, key presses, page source, and screenshots. Do not use CLI tools unless the task explicitly exposes one.",
            "- Treat optional or transient UI such as dialogs, permissions, and sign-in state as runtime conditions to handle safely.",
            "- Do not edit the source FSQ YAML during execution.",
            "- Treat ordered key actions as the goal's required execution spine, not as a brittle one-for-one script. Preserve their relative order while allowing recovery, wait, evidence, and transient-dialog steps between them.",
            "- Execute with all ordered key actions visible. Final verification mode may later decide which action categories are blocking, but do not skip operation steps because of that.",
            "- If this case has preconditions, inspect the live app state before the ordered key actions. Complete only missing preconditions first, then continue the case flow.",
            "- When a precondition requires credentials, use configured runtime secret tools and environment variable names only. Do not print, store, or report secret values.",
            "- Use success only when the intended scenario is completed with evidence from the live UI or tool outputs.",
            "",
            "Inferred preconditions:",
        ])
        if preconditions:
            lines.extend(f"- {precondition}" for precondition in preconditions)
        else:
            lines.append("- None detected from case metadata or commands.")
        lines.extend([
            "",
            "Ordered key actions for execution:",
        ])
        key_actions = self.extract_ordered_key_actions(case)
        if key_actions:
            lines.extend(f"{index}. {action}" for index, action in enumerate(key_actions, start=1))
        else:
            lines.append("- No required ordered key actions; execute toward the case goal.")
        lines.extend([
            "",
            "Final verification criteria:",
        ])
        for criterion in self.extract_verification_criteria(case, key_actions):
            lines.append(f"- [{criterion.kind}] {criterion.text}")
        lines.extend([
            "",
            "Reference FSQ command flow:",
        ])
        lines.extend(self._render_commands(case.commands))
        return "\n".join(lines)

    def _render_commands(self, commands: list[Any]) -> list[str]:
        return [f"{index}. {self._render_command(command)}" for index, command in enumerate(commands, start=1)]

    def _render_command(self, command: Any) -> str:
        if isinstance(command, str):
            return command
        if isinstance(command, dict) and len(command) == 1:
            name, value = next(iter(command.items()))
            return f"{name}: {json.dumps(value, ensure_ascii=False, sort_keys=True)}"
        return json.dumps(command, ensure_ascii=False, sort_keys=True)

    def _render_key_action(self, command: Any) -> str | None:
        if isinstance(command, str):
            if self._is_setup_or_teardown_action(command):
                return None
            return command
        if not isinstance(command, dict) or len(command) != 1:
            return self._render_command(command)

        name, value = next(iter(command.items()))
        if self._is_setup_or_teardown_action(name):
            return None
        if isinstance(value, dict) and value.get("optional") is True:
            return None
        return self._format_key_action(name, value)

    def _is_setup_or_teardown_action(self, action_name: str) -> bool:
        action_definition = ANDROID_ACTION_DEFINITIONS_BY_NAME.get(action_name)
        return action_definition is not None and action_definition.step_kind in {"setup", "teardown"}

    def _command_name(self, command: Any) -> str:
        if isinstance(command, str):
            return command
        if isinstance(command, dict) and len(command) == 1:
            return str(next(iter(command.keys())))
        return "command"

    def _criterion_kind(self, command_name: str) -> VerificationCriterionKind:
        return "assertion" if command_name.lower().startswith("assert") else "operation"

    def _format_key_action(self, name: str, value: Any) -> str:
        if not isinstance(value, dict):
            return f"{name}: {value}"

        target = value.get("target") or value.get("prompt") or value.get("text")
        if not target and isinstance(value.get("element"), dict):
            target = self._format_locator(value["element"])
        if name == "pressKey" and value.get("key"):
            action = f"{name}: {value['key']}"
        elif name == "inputText" and value.get("text") and value.get("target"):
            action = f"{name} {value['text']} into {value['target']}"
        else:
            action = f"{name} {target}" if target else name

        details = []
        if isinstance(value.get("locator"), dict):
            details.append(f"locator: {self._format_locator(value['locator'])}")
        if isinstance(value.get("element"), dict):
            details.append(f"element: {self._format_locator(value['element'])}")
        if isinstance(value.get("text"), dict):
            details.append(f"text: {json.dumps(value['text'], ensure_ascii=False, sort_keys=True)}")
        elif isinstance(value.get("text"), str) and name != "inputText":
            details.append(f"text: {value['text']}")

        if details:
            return f"{action} ({'; '.join(details)})"
        return action

    def _format_locator(self, locator: dict[str, Any]) -> str:
        return ", ".join(f"{key}={value}" for key, value in locator.items())

    def _infer_preconditions(self, case: FsqCase) -> list[str]:
        config = case.config
        text_parts = [config.name, config.description, *config.tags]
        text_parts.extend(self._render_command(command) for command in case.commands)
        text = "\n".join(str(part).lower() for part in text_parts)
        preconditions: list[str] = []

        for tag in config.tags:
            lowered = tag.lower()
            if not lowered.startswith("requires-") or lowered == "requires-msa":
                continue
            requirement = lowered[len("requires-") :].replace("-", " ").strip()
            if requirement:
                preconditions.append(
                    f"Case tag `{tag}` indicates required setup: {requirement}. Inspect whether this setup is already satisfied before executing key actions; if not, complete it first."
                )

        if any(marker in text for marker in ("requires-msa", " msa", "microsoft account", "signed in", "sign in", "login", "account state")):
            preconditions.append(
                "Microsoft account sign-in is required. Before executing ordered key actions, inspect whether Edge is already signed in. If it is not signed in, retrieve `TEST_ACCOUNT_EMAIL` and `TEST_ACCOUNT_PASSWORD` with `get_runtime_secret`, complete the sign-in flow, verify the signed-in account marker, and never reveal the credential values in progress, evidence, or final output."
            )

        return self._dedupe(preconditions)

    def _dedupe(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            result.append(value)
        return result
