from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from app.database.config import DATABASE_URL

# Create SQLAlchemy Engine for Neon PostgreSQL with SSL & Pool Recycling
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
    echo=False,
)

# Create SessionLocal class for DB sessions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Declarative Base Class for ORM models
Base = declarative_base()


# FastAPI Dependency for Database Session
def get_db() -> Generator:
    """
    FastAPI dependency that yields a database session per request.
    Handles rollback on errors and ensures cleanup after request completion.
    """
    db = SessionLocal()
    try:
        yield db
    except SQLAlchemyError:
        db.rollback()
        raise
    finally:
        db.close()
