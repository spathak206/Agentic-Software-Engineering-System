# Agentic Software Engineering Prototype

A runnable, dependency-free Python prototype that turns a natural-language software requirement into a validated engineering proposal. It demonstrates specialist agents, parallel execution with dependency barriers, bounded retry, codebase mapping, artifact generation, and a human approval gate. It uses deterministic local heuristics rather than an external LLM, so runs are reproducible and no source code or prompts leave the machine.

## Requirements

- Python 3.8 or newer
- No third-party packages

## Run the required URL shortener workflow

From this directory:

```powershell
python -m agentic_sdlc --requirement "Build a scalable URL shortener service with APIs, persistence, and analytics." --project-root . --output .\engineering-output\url-shortener
```

The selected output directory must be new or empty. The workflow never changes the project being analyzed. It prints validation and approval status and writes:

- `requirement.json`, `tasks.json`, `orchestration.json`
- `architecture.md`, `openapi.yaml`, `risks.md`, `validation.md`, `summary.md`
- `validation-result.json`, `approval.json`
- `generated\agentic_sdlc\url_shortener.py`, `generated\tests\test_url_shortener.py`, and a generated service README

`openapi.yaml` is JSON, a valid YAML subset, and can be parsed by ordinary OpenAPI tooling.

Run the generated service from its self-contained package directory:

```powershell
Set-Location .\engineering-output\url-shortener\generated
python -m agentic_sdlc.url_shortener --database .\url_shortener.db --host 127.0.0.1 --port 8000
```

Create a short URL from another terminal:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/urls -ContentType "application/json" -Body '{"target_url":"https://example.com"}'
```

Open the returned `short_url` to record a redirect click. Retrieve analytics at `http://127.0.0.1:8000/api/urls/{code}/analytics`.

For a complete customer-facing walkthrough, including Windows Command Prompt commands, pre-demo checks, a live API flow, and a talk track, see [the customer demo guide](examples/customer-demo.md).

## Try the example scenarios

Each requirement is available under `examples\`. Run each with a distinct output directory:

```powershell
python -m agentic_sdlc --requirement "Fix the existing API service behavior and add regression tests." --project-root . --output .\engineering-output\brownfield
python -m agentic_sdlc --requirement "Make the existing service faster and more reliable." --project-root . --output .\engineering-output\ambiguous
```

The greenfield example is the mandatory URL shortener requirement above. The brownfield run reports discovered modules and route-like files. The ambiguous example keeps unresolved SLO and acceptance questions visible in `requirement.json`, `validation.md`, and `summary.md`. Every run includes a task dependency graph, parallel orchestration trace, and validation result. See `examples\sample_outputs.json` for representative task dependencies, parallel waves, and validation/approval results for all three scenarios.

## Architecture and execution model

`RequirementAnalyst` normalizes intent and flags ambiguity; `CodebaseMapper` scans bounded source files for modules, imports, and route-like entry points. Those independent agents execute concurrently. `ArchitectureAgent` and `RiskAgent` then coordinate from both results; `TaskPlanner` builds a dependency-linked plan; `ArtifactAgent` emits the API, implementation/test proposal, and documentation; `ValidationAgent` checks artifact structure, dependency integrity/cycles, the OpenAPI document, and Python syntax; `ReviewAgent` blocks release pending explicit approval.

The orchestrator executes ready DAG nodes concurrently, waits at dependency barriers, records attempts and status, and retries an agent once for transient I/O errors. Failed validation stops artifact writing. The output directory is an isolated proposal; `--approve` records a human decision but deliberately does not apply code or deploy.

The included URL shortener uses Python's threaded HTTP server and SQLite. It provides `POST /api/urls`, `GET /{code}` redirects, and `GET /api/urls/{code}/analytics`. Click count and click event writes are transactional. SQLite is appropriate for a local prototype, not a horizontally scaled production deployment.

## Validation and testing

Run the focused test suite from the project root:

```powershell
python -m unittest discover -s tests -v
```

Integration tests use a temporary SQLite database and an ephemeral loopback HTTP port. Workflow checks cover greenfield, brownfield, ambiguous requirements, approval state, and generated bundle validation. The workflow statically parses generated Python and validates OpenAPI JSON; it never executes generated code or arbitrary commands found in the inspected project.

For production, first agree traffic and availability targets. Add load and concurrency tests, auth/rate limiting and abuse controls, operational monitoring, data-retention policy, a managed multi-node database, security review, and deployment/rollback verification.

## Assumptions and limitations

- Requirement understanding and codebase discovery are transparent heuristics, not semantic LLM reasoning. Findings must be reviewed.
- Discovery is capped at 250 source files and skips common generated/dependency directories. Dynamic routing and nonstandard layouts may not be found.
- The prototype emits a vetted URL shortener source/test template for the mandatory use case. Other requirements receive a scoped architecture/API proposal and engineering task plan, not invented application source.
- The shortener is unauthenticated, has no rate limiting, expiry, custom aliases, abuse reporting, or production-grade observability. Its open redirect behavior is intrinsic to URL shortening and needs abuse controls before public exposure.
- Human approval is recorded for review; applying generated code and deployment are intentionally out of scope.
