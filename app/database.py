import os
from typing import AsyncGenerator, Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

load_dotenv()

DEFAULT_DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/pollingapi_dev"

DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
ASYNC_DATABASE_URL = os.getenv("ASYNC_DATABASE_URL", DATABASE_URL)

engine = create_engine(DATABASE_URL, future=True)
async_engine = create_async_engine(ASYNC_DATABASE_URL, future=True)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
AsyncSessionLocal = async_sessionmaker(bind=async_engine, expire_on_commit=False)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Provide a synchronous database session for request scope."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide an asynchronous database session for request scope."""
    async with AsyncSessionLocal() as session:
        yield session
