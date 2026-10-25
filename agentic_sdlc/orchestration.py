import concurrent.futures
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List

from agentic_sdlc.agents import (
    ArchitectureAgent,
    ArtifactAgent,
    CodebaseMapper,
    RequirementAnalyst,
    ReviewAgent,
    RiskAgent,
    TaskPlanner,
    ValidationAgent,
)


class WorkflowError(RuntimeError):
    pass


class WorkflowOrchestrator:
    def __init__(self, project_root: str, workers: int = 4) -> None:
        self.project_root = project_root
        self.workers = workers
        self.agents = {
            "requirements": RequirementAnalyst(),
            "codebase": CodebaseMapper(),
            "architecture": ArchitectureAgent(),
            "risk": RiskAgent(),
            "planning": TaskPlanner(),
            "artifacts": ArtifactAgent(),
            "validation": ValidationAgent(),
            "review": ReviewAgent(),
        }

    def run(self, text: str, output: str, approved: bool = False) -> Dict[str, Any]:
        functions: Dict[str, Callable[[Dict[str, Any]], Any]] = {
            "requirements": lambda context: self.agents["requirements"].analyze(text),
            "codebase": lambda context: self.agents["codebase"].scan(self.project_root),
            "architecture": lambda context: self.agents["architecture"].design(
                context["requirements"], context["codebase"]
            ),
            "risk": lambda context: self.agents["risk"].assess(
                context["requirements"], context["codebase"]
            ),
            "planning": lambda context: self.agents["planning"].decompose(
                context["requirements"], context["architecture"], context["risk"]
            ),
            "artifacts": lambda context: self.agents["artifacts"].generate(
                context["requirements"], context["architecture"], context["planning"], context["risk"]
            ),
            "validation": lambda context: self.agents["validation"].validate(
                context["artifacts"], context["planning"]
            ),
            "review": lambda context: self.agents["review"].review(
                context["validation"], context["requirements"]
            ),
        }
        dependencies = {
            "requirements": set(),
            "codebase": set(),
            "architecture": {"requirements", "codebase"},
            "risk": {"requirements", "codebase"},
            "planning": {"architecture", "risk"},
            "artifacts": {"planning", "architecture", "requirements", "risk"},
            "validation": {"artifacts", "planning"},
            "review": {"validation", "requirements"},
        }
        results: Dict[str, Any] = {}
        trace = []
        pending = set(functions)
        wave = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.workers) as executor:
            while pending:
                ready = sorted(
                    name for name in pending if dependencies[name].issubset(results.keys())
                )
                if not ready:
                    raise WorkflowError("Workflow graph is blocked; unresolved nodes: {}".format(sorted(pending)))
                wave += 1
                futures = {
                    executor.submit(functions[name], dict(results)): name
                    for name in ready
                }
                for future in concurrent.futures.as_completed(futures):
                    name = futures[future]
                    pending.remove(name)
                    attempts = 1
                    try:
                        value = future.result()
                    except (OSError, TimeoutError, ConnectionError) as first_error:
                        attempts = 2
                        try:
                            value = functions[name](dict(results))
                        except (OSError, TimeoutError, ConnectionError) as retry_error:
                            error_message = "{}: {}".format(type(retry_error).__name__, retry_error)
                            trace.append(
                                {
                                    "step": name,
                                    "status": "failed",
                                    "attempts": attempts,
                                    "wave": wave,
                                    "parallel_group": ready,
                                    "depends_on": sorted(dependencies[name]),
                                    "error": error_message,
                                }
                            )
                            raise WorkflowError(
                                "Agent '{}' failed after one transient-error retry: {}".format(
                                    name, error_message
                                )
                            ) from retry_error
                        trace.append(
                            {
                                "step": name,
                                "status": "completed",
                                "attempts": attempts,
                                "wave": wave,
                                "parallel_group": ready,
                                "recovered_from": "{}: {}".format(
                                    type(first_error).__name__, first_error
                                ),
                                "depends_on": sorted(dependencies[name]),
                            }
                        )
                    else:
                        trace.append(
                            {
                                "step": name,
                                "status": "completed",
                                "attempts": attempts,
                                "wave": wave,
                                "parallel_group": ready,
                                "depends_on": sorted(dependencies[name]),
                            }
                        )
                    if value is None:
                        trace.append(
                            {
                                "step": name,
                                "status": "failed",
                                "attempts": attempts,
                                "wave": wave,
                                "parallel_group": ready,
                                "depends_on": sorted(dependencies[name]),
                                "error": "Agent returned no result.",
                            }
                        )
                        raise WorkflowError("Agent '{}' returned no result.".format(name))
                    results[name] = value

        validation = results["validation"]
        review = results["review"]
        review["status"] = "approved" if approved and validation["status"] == "passed" else review["status"]
        results["approval"] = {
            "status": review["status"],
            "approved_by_human": bool(approved and validation["status"] == "passed"),
            "note": "Approval applies to this proposal only; it does not modify or deploy project code.",
        }
        results["orchestration"] = {
            "execution": "parallel DAG with dependency barriers and one retry for transient I/O errors",
            "worker_limit": self.workers,
            "trace": trace,
            "independent_first_wave": ["requirements", "codebase"],
            "output": str(Path(output).resolve()),
        }
        if validation["status"] != "passed":
            raise WorkflowError(
                "Generated artifacts failed validation: {}".format(
                    json.dumps(validation["checks"], indent=2)
                )
            )
        self._write_artifacts(output, results)
        return results

    @staticmethod
    def _write_artifacts(output: str, results: Dict[str, Any]) -> None:
        target = Path(output).resolve()
        if target.exists() and any(target.iterdir()):
            raise FileExistsError(
                "Output directory is not empty; choose a new path or remove it explicitly: {}".format(target)
            )
        target.mkdir(parents=True, exist_ok=True)
        generated = dict(results["artifacts"])
        generated["orchestration.json"] = json.dumps(results["orchestration"], indent=2) + "\n"
        generated["validation-result.json"] = json.dumps(results["validation"], indent=2) + "\n"
        generated["approval.json"] = json.dumps(results["approval"], indent=2) + "\n"
        for relative, content in generated.items():
            path = target / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")


def default_output_path(requirement: str) -> str:
    slug = "-".join(requirement.lower().split()[:5])
    slug = "".join(character for character in slug if character.isalnum() or character == "-")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return os.path.join("engineering-output", "{}-{}".format(slug or "requirement", timestamp))
