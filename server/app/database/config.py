import os
from pathlib import Path
from dotenv import load_dotenv

# Locate and load the .env file from the server directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_PATH = BASE_DIR / ".env"

if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
else:
    load_dotenv()

# Read DATABASE_URL from environment variables
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://neondb_owner:YOUR_PASSWORD@ep-sample-123456.us-east-2.aws.neon.tech/neondb?sslmode=require"
)
