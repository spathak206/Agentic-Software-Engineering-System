import json
import tempfile
import unittest
from pathlib import Path

from agentic_sdlc.orchestration import WorkflowOrchestrator


class WorkflowTests(unittest.TestCase):
    def test_url_shortener_produces_reviewable_validated_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            output = str(Path(directory) / "bundle")
            result = WorkflowOrchestrator(".").run(
                "Build a scalable URL shortener service with APIs, persistence, and analytics.",
                output,
            )
            self.assertEqual(result["validation"]["status"], "passed")
            self.assertEqual(result["approval"]["status"], "review_required")
            self.assertIn("generated/agentic_sdlc/url_shortener.py", result["artifacts"])
            contract = json.loads(result["artifacts"]["openapi.yaml"])
            self.assertIn("/{code}", contract["paths"])
            self.assertIn(
                "201", contract["paths"]["/api/urls"]["post"]["responses"]
            )
            self.assertTrue((Path(output) / "openapi.yaml").is_file())
            trace = result["orchestration"]["trace"]
            first_wave = {item["step"]: item for item in trace if item["wave"] == 1}
            self.assertEqual(set(first_wave), {"requirements", "codebase"})
            architecture_wave = {
                item["step"]: item for item in trace if item["step"] in ("architecture", "risk")
            }
            self.assertEqual(
                architecture_wave["architecture"]["wave"],
                architecture_wave["risk"]["wave"],
            )
            self.assertEqual(
                json.loads((Path(output) / "approval.json").read_text(encoding="utf-8"))[
                    "approved_by_human"
                ],
                False,
            )

    def test_greenfield_and_ambiguous_requirements_surface_questions(self):
        with tempfile.TemporaryDirectory() as directory:
            result = WorkflowOrchestrator(".").run(
                "Build a scalable analytics API service.", str(Path(directory) / "generic")
            )
            self.assertEqual(result["requirements"]["change_type"], "greenfield")
            self.assertTrue(result["requirements"]["ambiguities"])
            self.assertNotIn("generated/agentic_sdlc/url_shortener.py", result["artifacts"])

    def test_brownfield_requirement_maps_existing_modules(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "service.py").write_text("def update():\n    return True\n", encoding="utf-8")
            (root / "routes.py").write_text("router = object()\n", encoding="utf-8")
            result = WorkflowOrchestrator(str(root)).run(
                "Fix the existing API service behavior and add regression tests.",
                str(root / "bundle"),
            )
            self.assertEqual(result["requirements"]["change_type"], "brownfield")
            self.assertEqual(result["codebase"]["file_count"], 2)
            self.assertIn("routes.py", result["architecture"]["impacted_modules"])

    def test_ambiguous_brownfield_requirement_preserves_open_questions(self):
        with tempfile.TemporaryDirectory() as directory:
            result = WorkflowOrchestrator(".").run(
                "Make the existing service faster and more reliable.",
                str(Path(directory) / "ambiguous"),
            )
            self.assertEqual(result["requirements"]["change_type"], "brownfield")
            self.assertTrue(result["requirements"]["ambiguities"])
            self.assertIn("confirm-requirements", [task["id"] for task in result["planning"]])

    def test_explicit_approval_is_recorded_without_applying_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            result = WorkflowOrchestrator(".").run(
                "Improve API tests.", str(Path(directory) / "approved"), approved=True
            )
            self.assertEqual(result["approval"]["status"], "approved")
            self.assertTrue(result["approval"]["approved_by_human"])


if __name__ == "__main__":
    unittest.main()
