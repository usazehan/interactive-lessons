"""Prune abandoned reading-session snapshots.

Deployment-agnostic: this just deletes reading sessions idle longer than the
TTL (config `session_ttl_seconds`, overridable below) and exits. Point whatever
scheduler you already have at it — a system cron, a k8s CronJob, etc.:

    python -m app.cleanup                  # use the configured TTL
    python -m app.cleanup --max-age-seconds 3600

Note: sessions are also pruned opportunistically whenever a reader starts one,
so this is a backstop for projects that get no further traffic.
"""
import argparse
from typing import Optional

from app.store import prune_stale_sessions


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Prune idle reading sessions.")
    parser.add_argument(
        "--max-age-seconds",
        type=int,
        default=None,
        help="Override the idle TTL (defaults to settings.session_ttl_seconds).",
    )
    args = parser.parse_args(argv)

    deleted = prune_stale_sessions(args.max_age_seconds)
    print(f"Pruned {deleted} idle reading session(s).")
    return deleted


if __name__ == "__main__":
    main()
