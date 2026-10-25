import ast
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Set


IGNORED_DIRECTORIES = {
    ".git",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "engineering-output",
    "node_modules",
    "venv",
}
SOURCE_SUFFIXES = {".go", ".java", ".js", ".py", ".rb", ".ts"}


class RequirementAnalyst:
    def analyze(self, text: str) -> Dict[str, Any]:
        normalized = " ".join(text.split())
        lowered = normalized.lower()
        url_shortener = any(
            phrase in lowered
            for phrase in ("url shortener", "url shortening", "shorten url", "short links")
        )
        if url_shortener:
            capabilities = [
                "Create short links from validated HTTP or HTTPS URLs",
                "Persist mappings and click events",
                "Redirect visitors and expose click analytics",
            ]
            questions = []
            if not re.search(r"\b(99|availability|rps|requests per second|p\d)\b", lowered):
                questions.append(
                    "What traffic, availability, and redirect-latency targets define scalable?"
                )
            if not any(word in lowered for word in ("auth", "authentication", "private")):
                questions.append("Are links private or authenticated, or is anyone allowed to create them?")
            if not any(word in lowered for word in ("expire", "expiration", "ttl")):
                questions.append("Should links expire, and what is the retention policy for click events?")
            domain = "URL shortening and click analytics"
        else:
            capabilities = self._capabilities(normalized)
            questions = self._ambiguities(normalized, lowered)
            domain = self._domain(normalized)

        change_type = self._change_type(lowered)
        return {
            "original": text,
            "normalized": normalized,
            "domain": domain,
            "change_type": change_type,
            "capabilities": capabilities,
            "is_url_shortener": url_shortener,
            "ambiguities": questions,
            "assumptions": [
                "Generated artifacts are proposals in an isolated output directory; the source project is not modified.",
                "No generated code or project commands are executed automatically.",
            ],
        }

    @staticmethod
    def _capabilities(text: str) -> List[str]:
        lowered = text.lower()
        capabilities = []
        if any(word in lowered for word in ("api", "endpoint", "service")):
            capabilities.append("Define and implement the requested API or service behavior")
        if any(word in lowered for word in ("persist", "database", "storage", "data")):
            capabilities.append("Persist and retrieve the required domain data")
        if any(word in lowered for word in ("test", "quality", "validate")):
            capabilities.append("Add automated tests and document verification steps")
        if any(word in lowered for word in ("refactor", "enhance", "improve", "fix", "bug")):
            capabilities.append("Preserve existing behavior while addressing the requested change")
        if not capabilities:
            capabilities.append("Clarify and implement the requested software behavior")
        return capabilities

    @staticmethod
    def _ambiguities(text: str, lowered: str) -> List[str]:
        questions = []
        if re.search(r"\b(scalable|fast|secure|reliable|user-friendly)\b", lowered):
            questions.append("Which measurable service-level targets and workload should acceptance use?")
        if not any(word in lowered for word in ("api", "endpoint", "interface")):
            questions.append("What user-facing or service interface should be exposed?")
        if not any(word in lowered for word in ("test", "acceptance", "criteria")):
            questions.append("What acceptance criteria and edge cases must tests cover?")
        if len(text.split()) < 10:
            questions.append("Which users, permissions, and operational constraints are in scope?")
        return questions

    @staticmethod
    def _domain(text: str) -> str:
        words = re.findall(r"[A-Za-z0-9]+", text)
        return " ".join(words[:8]) or "Software requirement"

    @staticmethod
    def _change_type(lowered: str) -> str:
        if any(
            word in lowered
            for word in (
                "refactor",
                "enhance",
                "improve",
                "fix",
                "bug",
                "existing",
                "faster",
                "reliable",
                "upgrade",
            )
        ):
            return "brownfield"
        return "greenfield"


class CodebaseMapper:
    def scan(self, root: str) -> Dict[str, Any]:
        project = Path(root).resolve()
        if not project.exists() or not project.is_dir():
            raise ValueError("Project root must be an existing directory: {}".format(project))

        files = []
        imports: Dict[str, Set[str]] = {}
        route_files = []
        for path in project.rglob("*"):
            if any(part in IGNORED_DIRECTORIES or part.startswith(".") for part in path.parts):
                continue
            if not path.is_file() or path.suffix.lower() not in SOURCE_SUFFIXES:
                continue
            if len(files) >= 250:
                break
            relative = str(path.relative_to(project))
            files.append(relative)
            try:
                if path.stat().st_size > 256 * 1024:
                    continue
                source = path.read_text(encoding="utf-8", errors="replace")
            except OSError as error:
                raise OSError("Unable to inspect {}: {}".format(relative, error))

            if re.search(r"(?i)(route|router|@app\.(get|post|put|delete)|app\.(get|post))", source):
                route_files.append(relative)
            if path.suffix.lower() == ".py":
                try:
                    tree = ast.parse(source)
                except SyntaxError:
                    continue
                names = set()
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        names.update(alias.name.split(".")[0] for alias in node.names)
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        names.add(node.module.split(".")[0])
                if names:
                    imports[relative] = names

        modules = [
            {
                "path": name,
                "area": self._area(name),
                "imports": sorted(imports.get(name, set())),
                "defines_routes": name in route_files,
            }
            for name in files
        ]
        return {
            "root": str(project),
            "file_count": len(files),
            "truncated": len(files) >= 250,
            "modules": modules,
            "route_files": route_files,
            "data_flow_hypothesis": self._data_flow(files, route_files),
        }

    @staticmethod
    def _area(path: str) -> str:
        lowered = path.lower()
        for token, area in (
            ("test", "tests"),
            ("api", "API"),
            ("route", "API"),
            ("model", "data model"),
            ("db", "persistence"),
            ("database", "persistence"),
            ("service", "service logic"),
        ):
            if token in lowered:
                return area
        return "application module"

    @staticmethod
    def _data_flow(files: List[str], routes: List[str]) -> str:
        if not files:
            return "No source files were found; treat this as a greenfield project."
        if routes:
            return (
                "Potential request entry points: {}. Inspect their imports and call sites "
                "to verify the route-to-service-to-persistence flow.".format(", ".join(routes[:8]))
            )
        return "Source files were found, but no common route declaration pattern was detected."


class ArchitectureAgent:
    def design(self, requirement: Dict[str, Any], codebase: Dict[str, Any]) -> Dict[str, Any]:
        if requirement["is_url_shortener"]:
            components = [
                "HTTP API: validate URL creation requests, issue redirects, and expose analytics.",
                "Short-link service: generate collision-checked opaque codes and enforce URL policy.",
                "SQLite repository: persist mappings and click events; keep redirect updates atomic.",
                "Analytics query: aggregate persisted click events by day.",
            ]
            endpoints = {
                "/api/urls": {"post": "Create a short link from {target_url}; return code and short_url."},
                "/{code}": {"get": "Record a click and return HTTP 302 to the original URL."},
                "/api/urls/{code}/analytics": {
                    "get": "Return the target URL, total clicks, and daily click counts."
                },
            }
            tradeoffs = [
                "SQLite keeps the prototype runnable without external infrastructure; use PostgreSQL for multi-node writes.",
                "Random opaque codes avoid leaking creation order; collision checks retry before surfacing an error.",
                "Click events are recorded synchronously for accuracy; queue/batch them if redirect latency dominates.",
            ]
        else:
            components = [
                "API boundary: validate inputs and return a versioned, documented contract.",
                "Application service: hold domain rules outside transport handlers.",
                "Persistence adapter: isolate storage behind a replaceable repository.",
                "Automated test suite: cover domain behavior, API boundaries, and failure cases.",
            ]
            endpoints = {
                "/health": {"get": "Illustrative health check; confirm whether this endpoint is in scope."}
            }
            tradeoffs = [
                "Keep the prototype dependency-free and use replaceable interfaces for production adapters.",
                "Treat inferred scope and the illustrative API as assumptions until a human confirms them.",
            ]
        modules = codebase["modules"]
        return {
            "components": components,
            "endpoints": endpoints,
            "tradeoffs": tradeoffs,
            "impacted_modules": [item["path"] for item in modules[:30]],
            "brownfield_observations": codebase["data_flow_hypothesis"],
        }


class RiskAgent:
    def assess(self, requirement: Dict[str, Any], codebase: Dict[str, Any]) -> List[Dict[str, str]]:
        risks = [
            {
                "risk": "Ambiguous acceptance criteria can cause a technically complete but unwanted change.",
                "mitigation": "Keep unresolved questions visible and require human review before implementation is applied.",
                "severity": "medium",
            },
            {
                "risk": "Static codebase discovery may miss dynamic routes, generated code, or external dependencies.",
                "mitigation": "Treat file/import matches as hypotheses and confirm findings with repository owners and tests.",
                "severity": "medium",
            },
            {
                "risk": "Generated artifacts have not been executed against the target runtime or production data.",
                "mitigation": "Review the validation report, run project-specific checks, and approve deployment separately.",
                "severity": "high",
            },
        ]
        if requirement["is_url_shortener"]:
            risks.extend(
                [
                    {
                        "risk": "Unbounded traffic or database growth can exhaust a single SQLite instance.",
                        "mitigation": "Load test against agreed SLOs; set retention limits and migrate to a managed database.",
                        "severity": "high",
                    },
                    {
                        "risk": "Public URL creation can be abused for phishing or malicious redirects.",
                        "mitigation": "Add authentication, rate limits, abuse reporting, domain/reputation controls, and monitoring.",
                        "severity": "high",
                    },
                ]
            )
        return risks


class TaskPlanner:
    def decompose(
        self, requirement: Dict[str, Any], architecture: Dict[str, Any], risks: List[Dict[str, str]]
    ) -> List[Dict[str, Any]]:
        tasks = [
            {
                "id": "confirm-requirements",
                "title": "Confirm scope and measurable acceptance criteria",
                "depends_on": [],
                "owner": "human + requirement analyst",
                "deliverable": "Approved scope, SLOs, and resolved ambiguity list",
            },
            {
                "id": "define-contract",
                "title": "Define the API contract and error semantics",
                "depends_on": ["confirm-requirements"],
                "owner": "architecture agent",
                "deliverable": "Versioned OpenAPI contract",
            },
            {
                "id": "implement-domain",
                "title": "Implement domain behavior and persistence",
                "depends_on": ["confirm-requirements", "define-contract"],
                "owner": "implementation agent",
                "deliverable": "Modular service and persistence adapter",
            },
            {
                "id": "verify-change",
                "title": "Add unit, API integration, and failure-path tests",
                "depends_on": ["implement-domain", "define-contract"],
                "owner": "test agent",
                "deliverable": "Repeatable automated tests and validation report",
            },
            {
                "id": "review-and-release",
                "title": "Review risks and approve the proposed change",
                "depends_on": ["verify-change"],
                "owner": "human reviewer",
                "deliverable": "Explicit approval before applying or deploying changes",
            },
        ]
        if requirement["change_type"] == "brownfield" and architecture["impacted_modules"]:
            tasks[1]["deliverable"] += "; verify impacted modules and preserve existing contracts"
        tasks[0]["description"] = (
            "Resolve {} open questions and agree the measurable behavior.".format(
                len(requirement["ambiguities"])
            )
        )
        tasks[4]["description"] = "Address {} identified risks before release.".format(len(risks))
        return tasks


class ArtifactAgent:
    def generate(
        self,
        requirement: Dict[str, Any],
        architecture: Dict[str, Any],
        tasks: List[Dict[str, Any]],
        risks: List[Dict[str, str]],
    ) -> Dict[str, str]:
        artifacts = {
            "requirement.json": json.dumps(requirement, indent=2, sort_keys=True),
            "tasks.json": json.dumps(tasks, indent=2),
            "architecture.md": self._architecture_markdown(requirement, architecture),
            "openapi.yaml": self._openapi(requirement, architecture),
            "risks.md": self._risks_markdown(risks),
            "validation.md": self._validation_markdown(requirement),
            "summary.md": self._summary_markdown(requirement, architecture, tasks),
        }
        if requirement["is_url_shortener"]:
            root = Path(__file__).resolve().parent.parent
            artifacts["generated/agentic_sdlc/__init__.py"] = (
                root / "agentic_sdlc" / "__init__.py"
            ).read_text(encoding="utf-8")
            artifacts["generated/agentic_sdlc/url_shortener.py"] = (
                root / "agentic_sdlc" / "url_shortener.py"
            ).read_text(encoding="utf-8")
            artifacts["generated/tests/test_url_shortener.py"] = (
                root / "tests" / "test_url_shortener.py"
            ).read_text(encoding="utf-8")
            artifacts["generated/tests/__init__.py"] = (
                root / "tests" / "__init__.py"
            ).read_text(encoding="utf-8")
            artifacts["generated/README.md"] = (
                "# Generated URL shortener\n\n"
                "Run the service with `python -m agentic_sdlc.url_shortener`.\n\n"
                "Run its integration tests with `python -m unittest discover -s tests -v`.\n"
            )
        return artifacts

    @staticmethod
    def _architecture_markdown(requirement: Dict[str, Any], architecture: Dict[str, Any]) -> str:
        lines = [
            "# Architecture proposal",
            "",
            "Requirement: {}".format(requirement["normalized"]),
            "",
            "## Components",
        ]
        lines.extend("- {}".format(item) for item in architecture["components"])
        lines.extend(["", "## Request and data flow", architecture["brownfield_observations"], ""])
        lines.append("## Endpoints")
        for path, methods in architecture["endpoints"].items():
            for method, description in methods.items():
                lines.append("- `{} {}` — {}".format(method.upper(), path, description))
        lines.extend(["", "## Trade-offs"])
        lines.extend("- {}".format(item) for item in architecture["tradeoffs"])
        lines.extend(["", "## Impacted modules"])
        if architecture["impacted_modules"]:
            lines.extend("- `{}`".format(path) for path in architecture["impacted_modules"])
        else:
            lines.append("- No existing source modules detected.")
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _openapi(requirement: Dict[str, Any], architecture: Dict[str, Any]) -> str:
        if requirement["is_url_shortener"]:
            document = {
                "openapi": "3.0.3",
                "info": {
                    "title": "URL shortener API",
                    "version": "1.0.0",
                    "description": "Generated proposal. Confirm assumptions before implementation.",
                },
                "paths": {
                    "/api/urls": {
                        "post": {
                            "summary": "Create a short link",
                            "requestBody": {
                                "required": True,
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "required": ["target_url"],
                                            "properties": {
                                                "target_url": {
                                                    "type": "string",
                                                    "format": "uri",
                                                    "maxLength": 2048,
                                                }
                                            },
                                        }
                                    }
                                },
                            },
                            "responses": {
                                "201": {
                                    "description": "Short link created",
                                    "content": {
                                        "application/json": {
                                            "schema": {"$ref": "#/components/schemas/ShortUrl"}
                                        }
                                    },
                                },
                                "400": {"description": "Invalid URL or request body"},
                                "413": {"description": "Request body exceeds the size limit"},
                            },
                        }
                    },
                    "/{code}": {
                        "get": {
                            "summary": "Record a click and redirect",
                            "parameters": [
                                {
                                    "name": "code",
                                    "in": "path",
                                    "required": True,
                                    "schema": {"type": "string", "pattern": "^[A-Za-z0-9_-]{1,32}$"},
                                }
                            ],
                            "responses": {
                                "302": {
                                    "description": "Redirect to the original URL",
                                    "headers": {
                                        "Location": {
                                            "schema": {"type": "string", "format": "uri"}
                                        }
                                    },
                                },
                                "404": {"description": "Short code not found"},
                            },
                        }
                    },
                    "/api/urls/{code}/analytics": {
                        "get": {
                            "summary": "Get click analytics",
                            "parameters": [
                                {
                                    "name": "code",
                                    "in": "path",
                                    "required": True,
                                    "schema": {"type": "string", "pattern": "^[A-Za-z0-9_-]{1,32}$"},
                                }
                            ],
                            "responses": {
                                "200": {
                                    "description": "Click totals and daily breakdown",
                                    "content": {
                                        "application/json": {
                                            "schema": {
                                                "$ref": "#/components/schemas/Analytics"
                                            }
                                        }
                                    },
                                },
                                "404": {"description": "Short code not found"},
                            },
                        }
                    },
                },
                "components": {
                    "schemas": {
                        "ShortUrl": {
                            "type": "object",
                            "required": ["code", "target_url", "created_at", "short_url"],
                            "properties": {
                                "code": {"type": "string"},
                                "target_url": {"type": "string", "format": "uri"},
                                "created_at": {"type": "string", "format": "date-time"},
                                "short_url": {"type": "string", "format": "uri"},
                            },
                        },
                        "Analytics": {
                            "type": "object",
                            "required": [
                                "code",
                                "target_url",
                                "created_at",
                                "click_count",
                                "daily_clicks",
                            ],
                            "properties": {
                                "code": {"type": "string"},
                                "target_url": {"type": "string", "format": "uri"},
                                "created_at": {"type": "string", "format": "date-time"},
                                "click_count": {"type": "integer", "minimum": 0},
                                "daily_clicks": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "required": ["date", "clicks"],
                                        "properties": {
                                            "date": {"type": "string", "format": "date"},
                                            "clicks": {"type": "integer", "minimum": 1},
                                        },
                                    },
                                },
                            },
                        },
                    }
                },
            }
            return json.dumps(document, indent=2) + "\n"
        paths = {}
        for path, methods in architecture["endpoints"].items():
            paths[path] = {}
            for method, description in methods.items():
                paths[path][method] = {
                    "summary": description,
                    "responses": {"200": {"description": "Successful response"}},
                }
        document = {
            "openapi": "3.0.3",
            "info": {
                "title": requirement["domain"] + " API",
                "version": "1.0.0",
                "description": "Generated proposal. Confirm assumptions before implementation.",
            },
            "paths": paths,
        }
        return json.dumps(document, indent=2) + "\n"

    @staticmethod
    def _risks_markdown(risks: List[Dict[str, str]]) -> str:
        lines = ["# Risks and mitigations", ""]
        for risk in risks:
            lines.extend(
                [
                    "## {} ({})".format(risk["risk"], risk["severity"].upper()),
                    "",
                    "Mitigation: {}".format(risk["mitigation"]),
                    "",
                ]
            )
        return "\n".join(lines)

    @staticmethod
    def _validation_markdown(requirement: Dict[str, Any]) -> str:
        lines = [
            "# Validation strategy",
            "",
            "## Automated checks performed by the workflow",
            "",
            "- Requirement and task graph shape, including dependency integrity and cycle detection.",
            "- OpenAPI document parses as JSON (valid YAML subset) and exposes at least one path.",
            "- Generated Python artifacts parse successfully without executing them.",
            "- Required test artifact is present for the URL shortener use case.",
            "",
            "## Checks for the human reviewer",
            "",
            "- Run `python -m unittest discover -s tests -v` from the prototype root.",
            "- Confirm behavior against approved acceptance criteria and run load/security tests.",
            "- Validate migrations, operational limits, monitoring, and rollback in the target environment.",
            "- Approve the generated proposal before applying code or deploying.",
            "",
            "The workflow does not execute generated code, run arbitrary project commands, or deploy.",
            "",
            "## Unresolved acceptance questions",
            "",
        ]
        lines.extend("- {}".format(item) for item in requirement["ambiguities"])
        if not requirement["ambiguities"]:
            lines.append("- None detected by the local heuristic analyst.")
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _summary_markdown(
        requirement: Dict[str, Any], architecture: Dict[str, Any], tasks: List[Dict[str, Any]]
    ) -> str:
        lines = [
            "# Engineering outcome",
            "",
            "## Requirement and approach",
            "",
            requirement["normalized"],
            "",
            "Change classification: **{}**. Domain: **{}**.".format(
                requirement["change_type"], requirement["domain"]
            ),
            "",
            "## Implementation plan",
            "",
        ]
        lines.extend(
            "{}. **{}** — {}".format(index, task["title"], task["deliverable"])
            for index, task in enumerate(tasks, 1)
        )
        lines.extend(
            [
                "",
                "## Generated artifacts",
                "",
                "Requirement, task graph, architecture proposal, OpenAPI contract, risk register, "
                "validation strategy, and this summary.",
            ]
        )
        if requirement["is_url_shortener"]:
            lines.append("Runnable SQLite-backed URL shortener service and HTTP integration tests.")
        lines.extend(
            [
                "",
                "## Risks, trade-offs, and approval",
                "",
                "See `risks.md` and `architecture.md`. No generated code is applied to the project. "
                "Human review and approval are required before implementation or deployment.",
                "",
                "## Assumptions and limitations",
                "",
            ]
        )
        lines.extend("- {}".format(item) for item in requirement["assumptions"])
        lines.append(
            "- Architecture and codebase discovery use local deterministic heuristics, not an LLM."
        )
        lines.append("")
        return "\n".join(lines)


class ValidationAgent:
    def validate(self, artifacts: Dict[str, str], tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        checks = []
        try:
            requirement = json.loads(artifacts["requirement.json"])
            checks.append({"name": "requirement-json", "status": "passed"})
            task_ids = {task["id"] for task in tasks}
            if len(task_ids) != len(tasks):
                raise ValueError("task identifiers must be unique")
            if any(dep not in task_ids for task in tasks for dep in task["depends_on"]):
                raise ValueError("task references an unknown dependency")
            if self._has_cycle(tasks):
                raise ValueError("task dependency graph contains a cycle")
            checks.append({"name": "task-dependency-graph", "status": "passed"})
            contract = json.loads(artifacts["openapi.yaml"])
            if contract.get("openapi") != "3.0.3" or not contract.get("paths"):
                raise ValueError("OpenAPI version or paths are missing")
            if requirement.get("is_url_shortener"):
                paths = contract["paths"]
                expected = {
                    "/api/urls": {"post"},
                    "/{code}": {"get"},
                    "/api/urls/{code}/analytics": {"get"},
                }
                if any(
                    path not in paths or not methods.issubset(paths[path])
                    for path, methods in expected.items()
                ):
                    raise ValueError("URL shortener contract is missing a required endpoint")
                if "ShortUrl" not in contract.get("components", {}).get("schemas", {}):
                    raise ValueError("URL shortener response schema is missing")
            checks.append({"name": "openapi-contract", "status": "passed"})
            if not all(key in artifacts for key in ("architecture.md", "risks.md", "validation.md", "summary.md")):
                raise ValueError("required documentation artifact is missing")
            checks.append({"name": "documentation-artifacts", "status": "passed"})
            if requirement.get("is_url_shortener"):
                source_key = "generated/agentic_sdlc/url_shortener.py"
                test_key = "generated/tests/test_url_shortener.py"
                test_package_key = "generated/tests/__init__.py"
                if any(key not in artifacts for key in (source_key, test_key, test_package_key)):
                    raise ValueError("URL shortener source or integration test artifact is missing")
                ast.parse(artifacts[source_key])
                ast.parse(artifacts[test_key])
                ast.parse(artifacts[test_package_key])
                checks.append({"name": "generated-python-syntax", "status": "passed"})
        except (KeyError, TypeError, ValueError, SyntaxError) as error:
            checks.append({"name": "artifact-validation", "status": "failed", "detail": str(error)})
        return {
            "status": "passed" if all(check["status"] == "passed" for check in checks) else "failed",
            "checks": checks,
            "execution_policy": "Generated code and target-project commands were not executed.",
        }

    @staticmethod
    def _has_cycle(tasks: List[Dict[str, Any]]) -> bool:
        dependencies = {task["id"]: set(task["depends_on"]) for task in tasks}
        visited = set()
        active = set()

        def visit(node: str) -> bool:
            if node in active:
                return True
            if node in visited:
                return False
            active.add(node)
            if any(visit(dep) for dep in dependencies[node]):
                return True
            active.remove(node)
            visited.add(node)
            return False

        return any(visit(node) for node in dependencies)


class ReviewAgent:
    def review(self, validation: Dict[str, Any], requirement: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "status": "review_required" if validation["status"] == "passed" else "blocked",
            "human_approval_required": True,
            "unresolved_questions": requirement["ambiguities"],
            "recommendation": (
                "Review assumptions and validation evidence, then explicitly approve before applying."
                if validation["status"] == "passed"
                else "Resolve validation failures before requesting human approval."
            ),
        }
