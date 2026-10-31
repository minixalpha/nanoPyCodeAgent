"""Container-side driver for the upstream DeepSeek Harness Python SDK."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path


def main():
    from deepseek_harness import DeepSeekHarness

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--reasoning-effort", default="high")
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--instruction")
    args = parser.parse_args()
    home = Path(args.home)
    home.mkdir(parents=True, exist_ok=True)
    with DeepSeekHarness(
        provider="deepseek-official", model=args.model,
        reasoning_effort=args.reasoning_effort, profile="sdk-minimal",
        cwd=str(Path.cwd()), dsh_home=str(home),
    ) as harness:
        # Initialization resolves the real profile/provider/model without a prompt.
        if args.preflight:
            print(json.dumps({"initialized": True, "model": args.model}))
            return 0
        if args.instruction is None:
            parser.error("--instruction is required for model work")
        with (home.parent / "dsh-events.jsonl").open("w") as events:
            def notification(event):
                # Durable session events contain usage and tool results. Omit
                # streaming projections, whose text duplicates the native log.
                if event.method == "session.event":
                    events.write(json.dumps(asdict(event)) + "\n")
                    events.flush()

            result = harness.run(
                Path(args.instruction).read_text(), session_id="benchmark",
                on_notification=notification,
            )
            (home.parent / "dsh-result.json").write_text(json.dumps({
                "session_id": result.session_id,
                "finish_reason": result.finish_reason,
                "final_response": result.final_response,
            }) + "\n")
        return 0 if result.finish_reason == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
