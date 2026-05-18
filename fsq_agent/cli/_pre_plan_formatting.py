import json
import logging

from fsq_agent.models import GoalPrePlan


logger = logging.getLogger(__name__)


def log_pre_plan(pre_plan: GoalPrePlan, output_format: str = "text") -> None:
    if output_format == "json":
        logger.info(pre_plan.model_dump_json(indent=2))
        return
    logger.info("Goal: %s", pre_plan.goal)
    if pre_plan.summary:
        logger.info("Summary: %s", pre_plan.summary)
    if pre_plan.relevant_page_ids:
        logger.info("Relevant pages: %s", ", ".join(pre_plan.relevant_page_ids))
    logger.info("Key actions:")
    for action in pre_plan.key_actions:
        suffix = f" -> {action.target_page_id}" if action.target_page_id else ""
        logger.info("%s. %s%s", action.step_id, action.action, suffix)
        if action.notes:
            logger.info("   %s", action.notes)
    if pre_plan.warnings:
        logger.warning("Warnings: %s", json.dumps(pre_plan.warnings, ensure_ascii=False))