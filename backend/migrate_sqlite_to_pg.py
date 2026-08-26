"""One-off migration: copy the local SQLite data into Postgres (Supabase).

Run once, from the `backend/` directory, with DATABASE_URL already pointing at
Supabase (i.e. after you've updated .env):

    python migrate_sqlite_to_pg.py

Safe to abort: it refuses to run if the target already holds rows, so it can
never double-import.
"""

import sys

from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database import Base
from app.models.source import Source
from app.models.spot import Spot, Tag, spot_tags

SQLITE_URL = "sqlite:///./travel_spots.db"


def column_values(row) -> dict:
    """Every mapped column of an ORM row, including its primary key.

    IDs are carried over deliberately: spots.source_id points at sources.id, and
    remapping them would mean rewriting those references.
    """
    return {c.key: getattr(row, c.key) for c in inspect(row).mapper.column_attrs}


def main() -> None:
    target_url = settings.database_url
    if target_url.startswith("sqlite"):
        sys.exit(
            "DATABASE_URL 仍指向 SQLite。請先在 .env 填入 Supabase 的連線字串再執行。"
        )

    source_engine = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})
    target_engine = create_engine(target_url, pool_pre_ping=True)

    Base.metadata.create_all(bind=target_engine)

    OldSession = sessionmaker(bind=source_engine)
    NewSession = sessionmaker(bind=target_engine)

    with OldSession() as old, NewSession() as new:
        existing = new.query(Source).count() + new.query(Spot).count()
        if existing:
            sys.exit(
                f"目標資料庫已有 {existing} 筆資料，為避免重複匯入而中止。"
                "確定要重來的話，請先清空 sources / spots / tags 三張表。"
            )

        # sources first — spots.source_id references it
        sources = old.query(Source).order_by(Source.id).all()
        for row in sources:
            new.add(Source(**column_values(row)))
        new.flush()

        spots = old.query(Spot).order_by(Spot.id).all()
        for row in spots:
            new.add(Spot(**column_values(row)))
        new.flush()

        tags = old.query(Tag).order_by(Tag.id).all()
        for row in tags:
            new.add(Tag(**column_values(row)))
        new.flush()

        # The many-to-many table has no ORM class, so copy it as raw rows
        links = old.execute(select(spot_tags)).all()
        if links:
            new.execute(
                spot_tags.insert(),
                [{"spot_id": spot_id, "tag_id": tag_id} for spot_id, tag_id in links],
            )

        # Inserting explicit IDs leaves Postgres' sequences at 1, so the next
        # insert would collide on the primary key. Fast-forward them.
        for table in ("sources", "spots", "tags"):
            new.execute(
                text(
                    f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                    f"COALESCE((SELECT MAX(id) FROM {table}), 0) + 1, false)"
                )
            )

        new.commit()

    print(
        f"完成：sources {len(sources)} 筆、spots {len(spots)} 筆、"
        f"tags {len(tags)} 筆、關聯 {len(links)} 筆"
    )


if __name__ == "__main__":
    main()
