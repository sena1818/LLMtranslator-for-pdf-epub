import tempfile
from pathlib import Path

from src.utils.config_loader import get_config


def test_get_config_reloads_when_path_changes():
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        config_a = root / "a.yaml"
        config_b = root / "b.yaml"

        config_a.write_text(
            """
translation_profile:
  name: "profile-a"
paths:
  input: "data/input"
  output: "data/output"
  temp: "data/temp"
  glossaries: "data/glossaries"
  logs: "logs"
  artifact_rules: "config/artifact_rules.yaml"
""".strip(),
            encoding="utf-8",
        )
        config_b.write_text(
            """
translation_profile:
  name: "profile-b"
paths:
  input: "data/input"
  output: "data/output"
  temp: "data/temp"
  glossaries: "data/glossaries"
  logs: "logs"
  artifact_rules: "config/artifact_rules.yaml"
""".strip(),
            encoding="utf-8",
        )

        loaded_a = get_config(config_a)
        loaded_b = get_config(config_b)

        assert loaded_a.translation_profile_name == "profile-a"
        assert loaded_b.translation_profile_name == "profile-b"


def test_prompt_fingerprint_changes_with_profile():
    default_config = get_config(Path("config/config.yaml"))
    research_config = get_config(Path("config/research_paper.yaml"))

    assert default_config.translation_profile_name != research_config.translation_profile_name
    assert default_config.prompt_fingerprint != research_config.prompt_fingerprint
