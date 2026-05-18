import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from fsq_agent.models import GoalPrePlan, KnowledgeBundle, RunEventSink, SkillBundle


PRE_PLAN_AGENT_INSTRUCTIONS = """
You are fsq-agent's goal pre-planner.
Convert one natural-language goal into an ordered list of key actions using the loaded page knowledge graph.

This is planning only. Do not execute UI actions, do not call UI automation tools, and do not claim runtime verification.
Your initial context contains the knowledge index only. Use read_knowledge_page to load concrete page nodes as needed.
When a loaded page operation points to another page_id, read that page if it is needed to continue the action chain.
You may call read_knowledge_index again if you need to resolve a page id or recover from an uncertain route.
Use page identifiers, elements, reference locators, and element operation results to infer a concise action path.
Treat reference locators as helpful hints, not authoritative truth.

Return only the structured GoalPrePlan output. Key actions should be actionable, ordered, and page-aware.
Use result.to_page_id values from page element operations when describing navigation between pages.
If the knowledge is incomplete, still return the best concise contiguous plan and add warnings. You may skip at most
one consecutive missing key action when page or element knowledge is unavailable. If you cannot form a useful action
chain from the available knowledge, return an empty key_actions list and explain the failure in warnings.
""".strip()


class ReadKnowledgeIndexArgs(BaseModel):
    reason: str | None = Field(default=None, description="Short reason for rereading the knowledge index.")


class ReadKnowledgePageArgs(BaseModel):
    page_id: str | None = Field(default=None, description="Page id to load, such as edge_android_new_tab_page.")
    file: str | None = Field(default=None, description="Optional relative page file path from the knowledge index.")
    reason: str | None = Field(default=None, description="Short reason this page is needed for planning.")


def build_pre_plan_input(goal: str, knowledge: KnowledgeBundle, skills: list[SkillBundle]) -> str:
    payload = {
        "goal": goal,
        "knowledge_items": knowledge.items,
        "flow_templates": knowledge.flow_templates,
        "knowledge_warnings": knowledge.warnings,
        "skills": [
            {
                "name": skill.name,
                "description": skill.description,
                "instructions": skill.instructions,
                "warnings": skill.warnings,
            }
            for skill in skills
        ],
        "output_schema": GoalPrePlan.model_json_schema(),
    }
    return json.dumps(payload, indent=2, ensure_ascii=False, default=str)


def extract_json_payload(text: str) -> Any | None:
    stripped = text.strip()
    if stripped.startswith("{"):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            return None
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def page_file_from_index(index_text: str, page_id: str) -> str | None:
    payload = extract_json_payload(index_text)
    if not isinstance(payload, dict):
        return None
    pages = payload.get("pages")
    if not isinstance(pages, list):
        return None
    for page in pages:
        if not isinstance(page, dict):
            continue
        if page.get("page_id") == page_id and page.get("file"):
            return str(page["file"])
    return None


def safe_page_relative_path(value: str) -> Path | None:
    normalized = value.replace("\\", "/").strip()
    if not normalized:
        return None
    path = Path(normalized)
    if path.is_absolute() or ".." in path.parts:
        return None
    if path.parts and path.parts[0] == "pages":
        return path
    return Path("pages") / path


class GoalPrePlanner:
    def __init__(self, runtime: Any) -> None:
        self.runtime = runtime

    async def plan(
        self,
        goal: str,
        knowledge: KnowledgeBundle,
        skills: list[SkillBundle],
        run_id: str,
        event_sink: RunEventSink | None = None,
    ) -> GoalPrePlan:
        return await self.runtime.run_pre_plan(goal, knowledge, skills, run_id, event_sink)