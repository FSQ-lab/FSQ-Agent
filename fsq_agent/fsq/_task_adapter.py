import json
from typing import Any

from fsq_agent.models import FsqCase, Task


class FsqTaskAdapter:
    def to_task(self, case: FsqCase) -> Task:
        return Task(
            id=case.id,
            name=case.config.name,
            description=self.render_description(case),
        )

    def render_description(self, case: FsqCase) -> str:
        config = case.config
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
        lines.extend([
            "",
            "Execution guidance:",
            "- Prefer explicit FSQ locators such as resourceId, accessibilityId, text, xpath, and className when available.",
            "- For Android cases, use the configured Appium MCP tools for device, session, app lifecycle, element lookup, taps, text input, key presses, page source, and screenshots. Do not use CLI tools unless the task explicitly exposes one.",
            "- Treat optional or transient UI such as dialogs, permissions, and sign-in state as runtime conditions to handle safely.",
            "- Do not edit the source FSQ YAML during execution.",
            "- Derive success criteria from the case description, assertion commands, and final intended app/page state.",
            "- Use success only when the intended scenario is completed with evidence from the live UI or tool outputs.",
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