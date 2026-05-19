from fsq_agent.cli._main import _task_from_goal, main


def test_run_goal_command_is_registered() -> None:
    assert "run-goal" in main.commands


def test_task_from_goal_creates_goal_only_task() -> None:
    task = _task_from_goal("  Access Downloads through the overflow menu.  ")

    assert task.id == "access-downloads-through-the-overflow-menu"
    assert task.name == "Access Downloads through the overflow menu."
    assert task.key_actions == []
    assert task.verification_goal == "Goal completed: Access Downloads through the overflow menu."
    assert [criterion.kind for criterion in task.verification_criteria] == ["goal"]