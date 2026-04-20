import os
import asyncio
from qdrant_client import QdrantClient
from dotenv import load_dotenv

load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "fairpay_qdrant")

def view_docs():
    if not QDRANT_URL or not QDRANT_API_KEY:
        print("❌ Qdrant credentials missing in .env")
        return

    try:
        client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, prefer_grpc=True)
        
        # Scroll through points to see what's inside
        points, next_page_offset = client.scroll(
            collection_name=QDRANT_COLLECTION_NAME,
            limit=20,
            with_payload=True,
            with_vectors=False
        )

        if not points:
            print(f"📭 No documents found in collection '{QDRANT_COLLECTION_NAME}'.")
            print("Try uploading a PDF or Docx in the UI first!")
            return

        print(f"📂 Found {len(points)} segments in Qdrant Cloud:")
        print("-" * 50)
        
        # Keep track of unique document names we've seen
        seen_docs = set()
        for p in points:
            name = p.payload.get('name', 'Unknown')
            doc_id = p.payload.get('document_id', 'Unknown')
            if doc_id not in seen_docs:
                print(f"📄 Document: {name} (ID: {doc_id})")
                seen_docs.add(doc_id)
        
        print("-" * 50)
        print(f"Total chunks/segments: {len(points)}")

    except Exception as e:
        print(f"❌ Failed to query Qdrant: {e}")

if __name__ == "__main__":
    view_docs()
