import tempfile
from pathlib import Path

from src.pipelines.postprocess.result_postprocess_pipeline import ResultPostprocessPipeline


def test_pipeline_formats_markdown_file():
    pipeline = ResultPostprocessPipeline()

    with tempfile.TemporaryDirectory() as temp_dir:
        markdown_path = Path(temp_dir) / "sample.md"
        markdown_path.write_text(
            "## []{#sec .calibre1}Title {.calibre2}\n\n::: quote\nHello\n:::\n",
            encoding="utf-8",
        )

        stats = pipeline.format_markdown_file(markdown_path, source_type="epub")
        content = markdown_path.read_text(encoding="utf-8")

        assert "## Title" in content
        assert "> Hello" in content
        assert stats["headers_normalized"] >= 1


def test_pipeline_syncs_assets_for_multiple_markdown_variants():
    pipeline = ResultPostprocessPipeline()

    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        results_dir = root / "results"
        source_dir = root / "source" / "images"
        results_dir.mkdir(parents=True, exist_ok=True)
        source_dir.mkdir(parents=True, exist_ok=True)

        source_image = source_dir / "cover.jpg"
        source_image.write_bytes(b"fake-jpeg")

        mono_path = results_dir / "task.md"
        bilingual_path = results_dir / "task.bilingual.md"
        mono_path.write_text("![cover](cover.jpg)\n", encoding="utf-8")
        bilingual_path.write_text("> ![cover](cover.jpg)\n\n![cover](cover.jpg)\n", encoding="utf-8")

        copied = pipeline.sync_assets(
            markdown_paths=[mono_path, bilingual_path],
            asset_sources=[source_dir],
            task_id="task",
        )

        assert copied == ["cover.jpg"]
        assert (results_dir / "assets" / "task" / "cover.jpg").exists()
        assert "assets/task/cover.jpg" in mono_path.read_text(encoding="utf-8")
        assert "assets/task/cover.jpg" in bilingual_path.read_text(encoding="utf-8")
