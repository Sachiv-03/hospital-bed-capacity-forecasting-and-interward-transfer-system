# Re-export database objects from database.py for backward compatibility
from app.database.database import engine, SessionLocal, Base, get_db

__all__ = ["engine", "SessionLocal", "Base", "get_db"]
