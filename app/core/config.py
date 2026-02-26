import os
from dotenv import load_dotenv

load_dotenv()

# ====================================================
# MongoDB Environment Variables
# ====================================================
DATABASE_URL = os.getenv("DATABASE_URL")
DATABASE_NAME = os.getenv("DATABASE_NAME","fairpay_hrm_db")

# ====================================================
# JWT Environment Variables
# ====================================================
JWT_SECRET = os.getenv("SECRET_KEY")
JWT_ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 1440))

# ====================================================
# Redis Environment Variables
# ====================================================
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")
REDIS_URL = os.getenv("REDIS_URL")

# ====================================================
# AI Environment Variables
# ====================================================
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# ====================================================
# AWS Environment Variables
# ====================================================
AWS_BUCKET_NAME = os.getenv("AWS_BUCKET_NAME")
AWS_REGION = os.getenv("AWS_REGION")
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")
AWS_USE_PATH = os.getenv("AWS_USE_PATH", "dev-uploads")

# ====================================================
# Storage Environment Variables
# ====================================================
API_URL = os.getenv("API_URL")

# ====================================================
# Qdrant Environment Variables
# ====================================================
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "documents")

# ====================================================
# Google Environment Variables
# ====================================================
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
