import json
import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes import glossary as glossary_routes


class GlossaryRoutesTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.glossary_dir = Path(self.temp_dir.name)
        self.original_glossary_dir = glossary_routes.service.glossary_dir
        glossary_routes.service.glossary_dir = self.glossary_dir
        glossary_routes.service.glossary_dir.mkdir(parents=True, exist_ok=True)

        app = FastAPI()
        app.include_router(glossary_routes.router)
        self.client = TestClient(app)

    def tearDown(self):
        glossary_routes.service.glossary_dir = self.original_glossary_dir
        self.temp_dir.cleanup()

    def test_create_glossary_accepts_json_body(self):
        response = self.client.post(
            "/api/glossary/",
            json={"name": "My Terms", "terms": {"Hyperstition": "超虚构"}},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], "my_terms")
        saved = json.loads((self.glossary_dir / "my_terms.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["Hyperstition"], "超虚构")

    def test_update_glossary_accepts_wrapped_terms_body(self):
        (self.glossary_dir / "review_case.json").write_text(
            json.dumps({"A": "B"}, ensure_ascii=False),
            encoding="utf-8",
        )

        response = self.client.put(
            "/api/glossary/review_case",
            json={"terms": {"A": "C"}},
        )

        self.assertEqual(response.status_code, 200)
        saved = json.loads((self.glossary_dir / "review_case.json").read_text(encoding="utf-8"))
        self.assertEqual(saved, {"A": "C"})

    def test_import_glossary_uses_form_name(self):
        response = self.client.post(
            "/api/glossary/import",
            files={"file": ("demo.json", b'{"A":"B"}', "application/json")},
            data={"name": "custom_name"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], "custom_name")
        self.assertTrue((self.glossary_dir / "custom_name.json").exists())
