import argparse
import json
import sys

from agentic_sdlc.orchestration import WorkflowError, WorkflowOrchestrator, default_output_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Turn a software requirement into a validated, reviewable engineering proposal."
    )
    parser.add_argument("--requirement", required=True, help="Natural-language engineering requirement")
    parser.add_argument("--project-root", default=".", help="Codebase to inspect (default: current directory)")
    parser.add_argument("--output", help="New or empty directory for generated artifacts")
    parser.add_argument(
        "--approve",
        action="store_true",
        help="Record human approval of this proposal (does not apply or deploy code)",
    )
    arguments = parser.parse_args()
    output = arguments.output or default_output_path(arguments.requirement)
    try:
        results = WorkflowOrchestrator(arguments.project_root).run(
            arguments.requirement, output, approved=arguments.approve
        )
    except (WorkflowError, OSError, ValueError) as error:
        print("Workflow failed: {}".format(error), file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "output": results["orchestration"]["output"],
                "validation": results["validation"]["status"],
                "approval": results["approval"]["status"],
                "steps": results["orchestration"]["trace"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
