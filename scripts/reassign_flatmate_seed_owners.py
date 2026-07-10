"""Reassign ownership of seed flatmate listings across other active users.

All 29 seed flatmate listings (`property_type='flatmate'`, `is_seed_data=true`)
are owned by user 1 (the testing/admin account). The Flatmates app excludes the
current user's own listings from the discover feed, so user 1 sees zero
listings even though the database and API return them.

This script reassigns `owner_id` for those seed listings round-robin across a
fixed set of active, non-user-1 flatmates users (room_posters + co_hunters) so
the inventory becomes discoverable by user 1.

Safety:
- Only touches rows where `property_type='flatmate' AND is_seed_data=true`.
- Never touches real (non-seed) data.
- Defaults to dry-run; pass `--apply` to commit.

Run:
    cd backend && uv run python scripts/reassign_flatmate_seed_owners.py            # dry-run
    cd backend && uv run python scripts/reassign_flatmate_seed_owners.py --apply     # commit
    cd backend && uv run python scripts/reassign_flatmate_seed_owners.py --env .env.dev
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter

from dotenv import load_dotenv

# Active, non-user-1 flatmates users with room-posting intent. Room posters
# are the natural owners of flatmate listings; co_hunters/open_to_both are
# included to spread ownership across enough distinct users.
TARGET_OWNER_IDS: tuple[int, ...] = (10, 13, 15, 16, 19, 29, 20, 24)

# Never reassign to the testing/admin account that triggered the bug.
EXCLUDED_OWNER_IDS: frozenset[int] = frozenset({1})


def _engine():
    from sqlalchemy import create_engine

    url = os.environ["DATABASE_URL"]
    if "+psycopg" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return create_engine(url)


def _load_env(env_file: str) -> None:
    if not os.path.exists(env_file):
        print(f"error: env file not found: {env_file}", file=sys.stderr)
        sys.exit(1)
    load_dotenv(env_file, override=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env",
        default=".env.dev",
        help="Env file to load DATABASE_URL from (default: .env.dev).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Commit the reassignment. Without this flag, only a preview runs.",
    )
    args = parser.parse_args()

    _load_env(args.env)

    from sqlalchemy import text

    engine = _engine()

    with engine.begin() as conn:
        # Validate every target owner exists, is active, and is not excluded.
        rows = conn.execute(
            text(
                "SELECT id, full_name, flatmates_mode, flatmates_profile_status "
                "FROM users WHERE id = ANY(:ids)"
            ),
            {"ids": list(TARGET_OWNER_IDS)},
        ).fetchall()
        found_ids = {r[0] for r in rows}
        missing = set(TARGET_OWNER_IDS) - found_ids
        if missing:
            print(f"error: target owners not found: {sorted(missing)}", file=sys.stderr)
            sys.exit(1)
        for r in rows:
            if r[3] != "active":
                print(
                    f"warning: target owner {r[0]} ({r[1]}) profile_status={r[3]}",
                    file=sys.stderr,
                )

        # Select the seed flatmate listings to reassign.
        listings = conn.execute(
            text(
                "SELECT id, title, owner_id FROM properties "
                "WHERE property_type = 'flatmate' AND is_seed_data = true "
                "ORDER BY id"
            )
        ).fetchall()

        if not listings:
            print("No seed flatmate listings found. Nothing to do.")
            return

        print(f"Seed flatmate listings to reassign: {len(listings)}")
        before = Counter(r[2] for r in listings)
        print(f"Current owner_id distribution: {dict(before)}")
        print(f"Target owner_ids: {TARGET_OWNER_IDS}")
        print()

        # Round-robin assignment across target owners.
        assignments: list[tuple[int, int]] = []
        for idx, row in enumerate(listings):
            prop_id = row[0]
            new_owner = TARGET_OWNER_IDS[idx % len(TARGET_OWNER_IDS)]
            assignments.append((prop_id, new_owner))

        after = Counter(new for _, new in assignments)
        print("Planned owner_id distribution after reassignment:")
        for owner_id in sorted(after):
            print(f"  user {owner_id}: {after[owner_id]} listings")
        print()

        # Show a few sample assignments.
        print("Sample assignments (first 8):")
        for prop_id, new_owner in assignments[:8]:
            title = next(r[1] for r in listings if r[0] == prop_id)
            old_owner = next(r[2] for r in listings if r[0] == prop_id)
            print(f"  property {prop_id} (owner {old_owner} -> {new_owner}): {title[:60]}")
        print()

        if not args.apply:
            print("DRY RUN — no changes made. Re-run with --apply to commit.")
            return

        # Safety: confirm no target owner is in the excluded set.
        if any(oid in EXCLUDED_OWNER_IDS for oid in TARGET_OWNER_IDS):
            print("error: a target owner is in the excluded set; aborting.", file=sys.stderr)
            sys.exit(1)

        # Apply the reassignment. Only update rows that are seed flatmate
        # listings (double-guarded in the WHERE clause).
        for prop_id, new_owner in assignments:
            result = conn.execute(
                text(
                    "UPDATE properties SET owner_id = :new_owner "
                    "WHERE id = :prop_id "
                    "AND property_type = 'flatmate' "
                    "AND is_seed_data = true"
                ),
                {"new_owner": new_owner, "prop_id": prop_id},
            )
            if result.rowcount != 1:
                print(
                    f"error: update for property {prop_id} affected {result.rowcount} rows",
                    file=sys.stderr,
                )
                raise RuntimeError(f"Unexpected rowcount for property {prop_id}")

        # Verify the result.
        verify = conn.execute(
            text(
                "SELECT owner_id, count(*) FROM properties "
                "WHERE property_type = 'flatmate' AND is_seed_data = true "
                "GROUP BY owner_id ORDER BY owner_id"
            )
        ).fetchall()
        print("APPLIED. New owner_id distribution:")
        for owner_id, count in verify:
            print(f"  user {owner_id}: {count} listings")
        print(f"Total seed flatmate listings reassigned: {len(assignments)}")


if __name__ == "__main__":
    main()
