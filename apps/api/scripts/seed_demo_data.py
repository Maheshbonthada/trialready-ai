"""Seeds one demo site + protocol so a fresh local environment has something to
click through immediately. Synthetic data only — see docs/compliance-checklist.md.

Usage: `python scripts/seed_demo_data.py` (from apps/api, with DATABASE_URL set
or the default docker-compose one already running).
"""

from __future__ import annotations

import asyncio

from trialready_api.db.models import Protocol, Site
from trialready_api.db.session import get_session_factory


async def main() -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        site = Site(
            name="Riverside Clinical Research (Demo)",
            principal_investigator_name="Dr. Amara Okafor",
            contact_email="demo-coordinator@example.com",
        )
        session.add(site)
        await session.flush()

        protocol = Protocol(
            site_id=site.id,
            sponsor_name="Acme Pharmaceuticals",
            protocol_number="ACM-204",
            title="A Phase 2 Study of Compound X in Adults (demo/synthetic)",
        )
        session.add(protocol)
        await session.commit()

        print(f"Seeded site {site.id} / protocol {protocol.id}")
        print(f"Try: POST /api/v1/protocols/{protocol.id}/documents (multipart file upload)")
        print(f"Then: POST /api/v1/protocols/{protocol.id}/gap-check")


if __name__ == "__main__":
    asyncio.run(main())
