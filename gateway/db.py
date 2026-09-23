import os

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
DATABASE_REPLICA_URL = os.getenv("DATABASE_REPLICA_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set")

engine = create_async_engine(DATABASE_URL)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

_replica_engine = (
    create_async_engine(DATABASE_REPLICA_URL) if DATABASE_REPLICA_URL else engine
)
AsyncReplicaSessionLocal = async_sessionmaker(_replica_engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass
