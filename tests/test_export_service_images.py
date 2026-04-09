import base64
import tempfile
import unittest
from pathlib import Path

from src.services.export_service import ExportService


class ExportServiceImagesTestCase(unittest.TestCase):
    def test_sync_result_assets_rewrites_markdown_and_copies_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            markdown_path = root / "results" / "task-1.md"
            image_source_dir = root / "temp" / "task-1" / "images"
            image_source_dir.mkdir(parents=True, exist_ok=True)
            markdown_path.parent.mkdir(parents=True, exist_ok=True)

            source_image = image_source_dir / "cover.png"
            source_image.write_bytes(b"fake-image")
            markdown_path.write_text("![cover](cover.png)\n", encoding="utf-8")

            copied = ExportService.sync_result_assets(
                markdown_path=markdown_path,
                asset_sources=[image_source_dir],
                task_id="task-1",
            )

            self.assertEqual(copied, ["cover.png"])
            self.assertTrue((markdown_path.parent / "assets" / "task-1" / "cover.png").exists())
            self.assertIn(
                "![cover](assets/task-1/cover.png)",
                markdown_path.read_text(encoding="utf-8"),
            )

    def test_export_bilingual_html_embeds_local_images(self):
        png_bytes = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9WnR0xUAAAAASUVORK5CYII="
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            markdown_path = root / "task-2.md"
            assets_dir = root / "assets" / "task-2"
            assets_dir.mkdir(parents=True, exist_ok=True)
            (assets_dir / "figure.png").write_bytes(png_bytes)
            markdown_path.write_text(
                "> ![figure](assets/task-2/figure.png)\n\n![figure](assets/task-2/figure.png)\n\n---\n",
                encoding="utf-8",
            )

            html_path = ExportService.export_bilingual_html(markdown_path, title="demo")
            html = Path(html_path).read_text(encoding="utf-8")

            self.assertIn("<img", html)
            self.assertIn("data:image/png;base64,", html)
