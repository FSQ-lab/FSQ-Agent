from pathlib import Path

from fsq_agent.models import FsqAgentError, SkillBundle, SkillConfig


class SkillLoader:
    def __init__(self, root: Path) -> None:
        self.root = root

    def load(self, configs: list[SkillConfig]) -> list[SkillBundle]:
        return [self._load_one(config) for config in configs]

    def _load_one(self, config: SkillConfig) -> SkillBundle:
        if config.kind == "markdown":
            return self._load_markdown(config)
        return SkillBundle(name=config.name, description=config.description, kind=config.kind, instructions=config.content or "")

    def _load_markdown(self, config: SkillConfig) -> SkillBundle:
        if config.content:
            return SkillBundle(name=config.name, description=config.description, kind=config.kind, instructions=config.content)
        if config.path is None:
            if config.required:
                raise FsqAgentError("Required skill path is missing.", context={"skill": config.name})
            return SkillBundle(
                name=config.name,
                description=config.description,
                kind=config.kind,
                warnings=[f"Skill {config.name} has no path or inline content."],
            )
        path = config.path if config.path.is_absolute() else self.root / config.path
        if not path.exists():
            if config.required:
                raise FsqAgentError("Required skill file does not exist.", context={"path": str(path)})
            return SkillBundle(
                name=config.name,
                description=config.description,
                kind=config.kind,
                warnings=[f"Skill file not found: {path}"],
            )
        if path.is_dir():
            files = sorted(path.glob("*.md"))
            instructions = "\n\n".join(file.read_text(encoding="utf-8") for file in files)
            return SkillBundle(name=config.name, description=config.description, kind=config.kind, instructions=instructions, files=files)
        return SkillBundle(
            name=config.name,
            description=config.description,
            kind=config.kind,
            instructions=path.read_text(encoding="utf-8"),
            files=[path],
        )