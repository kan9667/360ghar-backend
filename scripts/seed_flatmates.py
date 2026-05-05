#!/usr/bin/env python
"""CLI script to seed flatmates test data.

Usage:
    python scripts/seed_flatmates.py
    python -m scripts.seed_flatmates
"""

import asyncio
import os
import sys

# Ensure the project root is on sys.path so ``app`` is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def _run() -> None:
    from app.core.logging import setup_logging
    from scripts.seed_flatmates_data import seed_flatmates_data

    setup_logging()
    print("Seeding flatmates data...")
    stats = await seed_flatmates_data()
    print("\nSeed results:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    print("Done.")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
