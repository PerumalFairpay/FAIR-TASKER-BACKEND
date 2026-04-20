import asyncio
import os
from app.services.vector_store import vector_store_service
from app.core.config import QDRANT_URL, QDRANT_API_KEY

async def verify_qdrant_setup():
    print("--- Qdrant Cloud Setup Verification ---")
    
    if not QDRANT_URL or "your-qdrant" in QDRANT_URL:
        print("❌ Error: QDRANT_URL is not configured in .env")
        return
    
    if not QDRANT_API_KEY or "your-qdrant-api-key" in QDRANT_API_KEY:
        print("❌ Error: QDRANT_API_KEY is not configured in .env")
        return

    if QDRANT_API_KEY.startswith("AIzaSy"):
        print("❌ Error: Your QDRANT_API_KEY appears to be a Google/Gemini API key.")
        print("   Please use a real Qdrant API key from https://cloud.qdrant.io/")
        return

    print(f"✅ QDRANT_URL: {QDRANT_URL}")
    print(f"✅ QDRANT_API_KEY: Configured (Hidden)")

    try:
        if not vector_store_service.client:
            print("❌ Initialization failed. Check logs above for detailed error.")
            return

        # Test connection
        collections = vector_store_service.client.get_collections()
        print(f"✅ Successfully connected to Qdrant Cloud. Found {len(collections.collections)} collections.")
        
        # Check if our collection exists
        exists = False
        for col in collections.collections:
            if col.name == os.getenv("QDRANT_COLLECTION_NAME", "documents"):
                exists = True
                break
        
        if exists:
            print(f"✅ Collection '{os.getenv('QDRANT_COLLECTION_NAME', 'documents')}' exists.")
        else:
            print(f"ℹ️ Collection '{os.getenv('QDRANT_COLLECTION_NAME', 'documents')}' does not exist yet. It will be created on the first upload.")

        print("\n--- Test Passing Search ---")
        q = "test"
        results = await vector_store_service.search_documents(q)
        print(f"✅ Search function executed. (Results: {len(results)})")
        
        print("\n🚀 Setup looks good! Now try uploading a document through the UI and then ask the AI about it.")

    except Exception as e:
        print(f"❌ Connection to Qdrant Cloud failed: {str(e)}")

if __name__ == "__main__":
    asyncio.run(verify_qdrant_setup())
