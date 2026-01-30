import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "fairpay_hrm_db")

SECRET_KEY = os.getenv("SECRET_KEY", "7b9d8c4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2") # Default secret for development
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

# DocuSign Configuration
DOCUSIGN_INTEGRATION_KEY = os.getenv("DOCUSIGN_INTEGRATION_KEY")
DOCUSIGN_USER_ID = os.getenv("DOCUSIGN_USER_ID")
DOCUSIGN_API_ACCOUNT_ID = os.getenv("DOCUSIGN_API_ACCOUNT_ID")
DOCUSIGN_PRIVATE_KEY_PATH = os.getenv("DOCUSIGN_PRIVATE_KEY_PATH", "private.key")
DOCUSIGN_BASE_PATH = os.getenv("DOCUSIGN_BASE_PATH", "https://demo.docusign.net/restapi")
DS_APP_URL = os.getenv("APP_URL", "http://localhost:3001") # Return URL
