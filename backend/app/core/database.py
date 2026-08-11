#imports
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


#parent class for all DB tables(models) to inherit from
class Base(DeclarativeBase):
    pass

DATABASE_URL = settings.DATABASE_URL
#checks the connection status(alive/not) before sending DB query
#it connects automatically to the database if connection is lost
engine_kwargs = {
    "pool_pre_ping": True,
}

#stops errors when multiple threads try to access the same SQLite database file at the same time
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

#engine 
engine = create_async_engine(
    DATABASE_URL,
    **engine_kwargs,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
#opens a fresh session for each request and closes it after the request is completed
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session