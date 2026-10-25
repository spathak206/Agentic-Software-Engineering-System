# Customer demo: requirement to working URL shortener

This walkthrough demonstrates the proposal workflow and the generated URL shortener running locally. It uses only Python's standard library; no package installation or PowerShell script activation is required.

## What the customer will see

1. A natural-language requirement produces an engineering proposal.
2. The workflow reports validation results, orchestration steps, and a pending human review.
3. The proposal includes architecture, API contract, risks, dependency-linked tasks, and a generated service.
4. The service creates a short URL, redirects a visitor, and records click analytics in SQLite.

The workflow is deterministic local heuristics, not an LLM. The URL shortener is a vetted example template; other requirements produce a proposal rather than application source code.

## Before the demo

- Use a Windows **Command Prompt** terminal (`cmd.exe`) to follow the commands below. In VS Code, open the terminal profile dropdown and choose **Command Prompt**. Do not paste these commands into a Python prompt.
- Replace the repository path below if you cloned the project somewhere else.
- Confirm `.venv\Scripts\python.exe` exists. This repository's `activate.bat` may refer to a different checkout, so do not activate it. Calling the repository's Python executable directly also avoids PowerShell execution-policy problems.
- The workflow output directory must be new or empty. If `customer-demo` already contains files, choose a different name and update the later paths accordingly.
- The service listens on `127.0.0.1` only. This is a local demo, not a shared customer-facing deployment.

## 1. Open the repository and run the pre-demo tests

Open a Command Prompt terminal and run:

```cmd
cd /d "D:\AI-ML Learning\Use Case\Agentic-Software-Engineering-System"
".\.venv\Scripts\python.exe" --version
".\.venv\Scripts\python.exe" -m unittest discover -s tests -v
```

The tests should finish with `OK`. If the first command says the Python executable cannot be found, check the repository path and `.venv` folder before continuing.

## 2. Generate the proposal

Run this from the repository root:

```cmd
".\.venv\Scripts\python.exe" -m agentic_sdlc --requirement "Build a scalable URL shortener service with APIs, persistence, and analytics." --project-root "." --output ".\engineering-output\customer-demo"
```

The command should print JSON with `"validation": "passed"` and `"approval": "review_required"`. The workflow writes the proposal under `engineering-output\customer-demo` and does not change the source project.

Open the output folder in VS Code or File Explorer and use these files for the walkthrough:

- `summary.md` — concise overview and review status.
- `requirement.json` — normalized requirement, assumptions, and open questions.
- `tasks.json` — proposed tasks and dependencies.
- `orchestration.json` — execution waves, step status, and output location.
- `architecture.md`, `openapi.yaml`, and `risks.md` — design, API contract, and risks.
- `validation.md` and `validation-result.json` — validation explanation and checks.
- `approval.json` — pending review state.
- `generated\agentic_sdlc\url_shortener.py` — generated runnable service.

The validation stage checks the proposal structure, task graph, OpenAPI document, documentation artifacts, and generated Python syntax. It does **not** execute the generated service or its tests.

## 3. Run the generated service tests

From the repository root, run the integration tests against the generated bundle:

```cmd
cd /d "D:\AI-ML Learning\Use Case\Agentic-Software-Engineering-System\engineering-output\customer-demo\generated"
"..\..\..\.venv\Scripts\python.exe" -m unittest discover -s tests -v
```

These tests use a temporary SQLite database and a temporary local HTTP port. They verify URL creation, redirects, analytics persistence, malformed input, invalid URLs, and missing short codes. The tests should finish with `OK`.

## 4. Start the service

Keep this terminal open. Start the service from the generated package directory:

```cmd
cd /d "D:\AI-ML Learning\Use Case\Agentic-Software-Engineering-System\engineering-output\customer-demo\generated"
"..\..\..\.venv\Scripts\python.exe" -m agentic_sdlc.url_shortener --database ".\demo.db" --host 127.0.0.1 --port 8000
```

Wait for:

```text
URL shortener listening on http://127.0.0.1:8000
```

The local database is created as `generated\demo.db`. The server stops when you press `Ctrl+C` in this terminal.

## 5. Create a short link

Open a **second Command Prompt** terminal and run:

```cmd
curl.exe -i -X POST "http://127.0.0.1:8000/api/urls" -H "Content-Type: application/json" -d "{\"target_url\":\"https://example.com/demo\"}"
```

Expect HTTP `201` and a JSON response containing `code`, `target_url`, and `short_url`. Note the returned `code`; it is randomly generated, so it will differ on each run.

## 6. Demonstrate redirect and analytics

Replace `REPLACE_WITH_CODE` below with the actual code from the previous response. Do not include angle brackets.

First, show the redirect response:

```cmd
curl.exe -i "http://127.0.0.1:8000/REPLACE_WITH_CODE"
```

Expect HTTP `302` and a `Location: https://example.com/demo` header. This request records a click. To show the destination loading in a browser, open the returned `short_url`; that requires Internet access to reach `example.com` and records another click.

Then retrieve analytics:

```cmd
curl.exe "http://127.0.0.1:8000/api/urls/REPLACE_WITH_CODE/analytics"
```

Expect JSON with `click_count` and `daily_clicks`. The count should increase after each redirect request. You can run the redirect and analytics commands again to show the change.

## Optional: show invalid URL handling

This request should be rejected with HTTP `400`:

```cmd
curl.exe -i -X POST "http://127.0.0.1:8000/api/urls" -H "Content-Type: application/json" -d "{\"target_url\":\"javascript:alert(1)\"}"
```

## Optional: show the approval state

The initial run intentionally leaves the proposal in `review_required`. If you want to demonstrate the recorded approval flag, run a second workflow into another new output directory:

```cmd
cd /d "D:\AI-ML Learning\Use Case\Agentic-Software-Engineering-System"
".\.venv\Scripts\python.exe" -m agentic_sdlc --requirement "Build a scalable URL shortener service with APIs, persistence, and analytics." --project-root "." --output ".\engineering-output\customer-demo-approved" --approve
```

This records `"approved"` in the workflow output. It does **not** apply code to the repository, start the service, or deploy anything.

## Suggested talk track

- “We start with a plain-language requirement. The workflow identifies scope and unanswered questions rather than hiding them.”
- “Independent requirement analysis and codebase mapping run in parallel; dependent design, planning, artifact generation, validation, and review follow in order.”
- “The output is an isolated, reviewable proposal. Validation passes, but approval remains explicit.”
- “For this URL-shortener example, we can run the generated service, create a link, follow the redirect, and inspect persisted click analytics.”
- “This is a local prototype. It is not a production deployment or a claim of scalability.”

## Troubleshooting and limits

- **`Set-Location` or `Invoke-RestMethod` is not recognized:** those are PowerShell commands. Use a Command Prompt terminal for this guide, or switch to a PowerShell terminal before using PowerShell commands.
- **PowerShell says scripts are disabled:** do not run `Activate.ps1`; use the direct `.venv\Scripts\python.exe` commands above.
- **The generated output folder is not empty:** select another output folder. The workflow deliberately refuses to overwrite existing files.
- **Port 8000 is already in use:** stop the other service or choose another port in the server command, then replace `8000` in the request URLs with that port.
- **Browser does not reach `example.com`:** the local service may still be working; verify the `302` response with `curl.exe`. Browser navigation needs Internet access.
- **Customer cannot connect from another machine:** expected; the server binds to loopback (`127.0.0.1`) and is intentionally local-only.

The service has no authentication, rate limiting, expiry, abuse reporting, or production-grade observability. Do not expose it publicly or use it for real customer traffic.
