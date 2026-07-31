from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.core.config import settings

# Create SQLAlchemy Engine
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    echo=False,
)

# Create SessionLocal class for DB sessions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Declarative Base Class for ORM models
Base = declarative_base()


# FastAPI Dependency for Database Session
def get_db() -> Generator:
    """
    Dependency that provides a database session to API route handlers.
    Ensures session clean up after request completion.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
