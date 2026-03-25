"""
One-time migration: add owner_id to services table.

Deletes all existing seed services (no real user owns them),
adds the owner_id column, FK constraint, and composite unique index.

Usage:
    python migrate_add_owner_id.py

Idempotent — safe to run multiple times.
"""
import asyncio
import os
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def migrate():
    database_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://devportal:devportal@localhost:5432/devportal",
    )
    engine = create_async_engine(database_url)

    async with engine.begin() as conn:
        # Check if owner_id column already exists
        result = await conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'services' AND column_name = 'owner_id'"
        ))
        if result.scalar_one_or_none():
            print("owner_id column already exists — migration already applied.")
            await engine.dispose()
            return

        print("Deleting seed services (no owner)...")
        result = await conn.execute(text("DELETE FROM services"))
        print(f"  Deleted {result.rowcount} rows.")

        # Drop the old unique constraint and unique index on name alone
        print("Dropping old unique constraint/index on name...")
        await conn.execute(text(
            "ALTER TABLE services DROP CONSTRAINT IF EXISTS services_name_key"
        ))
        await conn.execute(text("DROP INDEX IF EXISTS ix_services_name"))
        # Recreate as non-unique index (still useful for lookups)
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_services_name ON services(name)"
        ))

        print("Adding owner_id column...")
        await conn.execute(text(
            "ALTER TABLE services ADD COLUMN owner_id UUID NOT NULL "
            "REFERENCES users(id)"
        ))

        print("Creating index on owner_id...")
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_services_owner_id ON services(owner_id)"
        ))

        print("Creating composite unique constraint (owner_id, name)...")
        await conn.execute(text(
            "ALTER TABLE services ADD CONSTRAINT uq_service_owner_name "
            "UNIQUE (owner_id, name)"
        ))

    await engine.dispose()
    print("Migration complete.")


if __name__ == "__main__":
    asyncio.run(migrate())
