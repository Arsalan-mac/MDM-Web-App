from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

settings = get_settings()

engine: AsyncEngine = create_async_engine(settings.database_url, pool_pre_ping=True)

# Sessions bound to the base engine operate against whatever schema Postgres
# resolves by default (search_path) - used for public-schema access.
PublicSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)


async def get_public_session() -> AsyncSession:
    async with PublicSessionLocal() as session:
        yield session
