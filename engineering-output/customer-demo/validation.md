# Validation strategy

## Automated checks performed by the workflow

- Requirement and task graph shape, including dependency integrity and cycle detection.
- OpenAPI document parses as JSON (valid YAML subset) and exposes at least one path.
- Generated Python artifacts parse successfully without executing them.
- Required test artifact is present for the URL shortener use case.

## Checks for the human reviewer

- Run `python -m unittest discover -s tests -v` from the prototype root.
- Confirm behavior against approved acceptance criteria and run load/security tests.
- Validate migrations, operational limits, monitoring, and rollback in the target environment.
- Approve the generated proposal before applying code or deploying.

The workflow does not execute generated code, run arbitrary project commands, or deploy.

## Unresolved acceptance questions

- What traffic, availability, and redirect-latency targets define scalable?
- Are links private or authenticated, or is anyone allowed to create them?
- Should links expire, and what is the retention policy for click events?
