from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import settings

# check_same_thread is a SQLite-only connect arg — psycopg2 rejects it outright,
# so it has to be conditional now that production runs on Postgres.
is_sqlite = settings.database_url.startswith("sqlite")

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if is_sqlite else {},
    # Render puts the service to sleep when idle and Supabase's pooler drops idle
    # connections; without pre-ping the first query after a wake-up hits a dead
    # socket and fails.
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
