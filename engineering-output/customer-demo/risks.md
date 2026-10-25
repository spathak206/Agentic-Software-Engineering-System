# Risks and mitigations

## Ambiguous acceptance criteria can cause a technically complete but unwanted change. (MEDIUM)

Mitigation: Keep unresolved questions visible and require human review before implementation is applied.

## Static codebase discovery may miss dynamic routes, generated code, or external dependencies. (MEDIUM)

Mitigation: Treat file/import matches as hypotheses and confirm findings with repository owners and tests.

## Generated artifacts have not been executed against the target runtime or production data. (HIGH)

Mitigation: Review the validation report, run project-specific checks, and approve deployment separately.

## Unbounded traffic or database growth can exhaust a single SQLite instance. (HIGH)

Mitigation: Load test against agreed SLOs; set retention limits and migrate to a managed database.

## Public URL creation can be abused for phishing or malicious redirects. (HIGH)

Mitigation: Add authentication, rate limits, abuse reporting, domain/reputation controls, and monitoring.
