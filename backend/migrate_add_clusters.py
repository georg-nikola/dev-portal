"""
One-time migration: create clusters table and add cluster_id to services.

Usage:
    python migrate_add_clusters.py

Idempotent — safe to run multiple times.
"""
import asyncio
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def migrate():
    database_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://devportal:devportal@localhost:5432/devportal",
    )
    engine = create_async_engine(database_url)

    async with engine.begin() as conn:
        # Check if clusters table already exists
        result = await conn.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_name = 'clusters'"
        ))
        if not result.scalar_one_or_none():
            print("Creating clusters table...")
            await conn.execute(text("""
                CREATE TABLE clusters (
                    id UUID PRIMARY KEY,
                    owner_id UUID NOT NULL REFERENCES users(id),
                    name VARCHAR(100) NOT NULL,
                    api_server_url VARCHAR(500),
                    encrypted_token TEXT,
                    encrypted_kubeconfig TEXT,
                    namespace_filter VARCHAR(500),
                    is_in_cluster BOOLEAN NOT NULL DEFAULT FALSE,
                    auto_discover BOOLEAN NOT NULL DEFAULT FALSE,
                    last_discovered_at TIMESTAMPTZ,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ,
                    CONSTRAINT uq_cluster_owner_name UNIQUE (owner_id, name)
                )
            """))
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_clusters_owner_id ON clusters(owner_id)"
            ))
            print("  clusters table created.")
        else:
            print("clusters table already exists — skipping.")

        # Check if cluster_id column exists on services
        result = await conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'services' AND column_name = 'cluster_id'"
        ))
        if not result.scalar_one_or_none():
            print("Adding cluster_id column to services...")
            await conn.execute(text(
                "ALTER TABLE services ADD COLUMN cluster_id UUID "
                "REFERENCES clusters(id) ON DELETE SET NULL"
            ))
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_services_cluster_id ON services(cluster_id)"
            ))
            print("  cluster_id column added.")
        else:
            print("cluster_id column already exists — skipping.")

    await engine.dispose()
    print("Migration complete.")


if __name__ == "__main__":
    asyncio.run(migrate())
