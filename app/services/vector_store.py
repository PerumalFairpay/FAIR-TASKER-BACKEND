import os
import requests
from typing import List, Optional
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from app.core.config import QDRANT_URL, QDRANT_API_KEY, QDRANT_COLLECTION_NAME
import pypdf
from docx import Document as DocxDocument
import io
import logging

logger = logging.getLogger(__name__)

class VectorStoreService:
    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        self.embeddings = GoogleGenerativeAIEmbeddings(
            model="models/gemini-embedding-001",
            google_api_key=self.api_key
        )
        
        if QDRANT_URL and QDRANT_API_KEY:
            try:
                self.client = QdrantClient(
                    url=QDRANT_URL,
                    api_key=QDRANT_API_KEY,
                    prefer_grpc=True,
                )
                
                # Ensure collection exists
                collection_name = QDRANT_COLLECTION_NAME or "documents"
                try:
                    info = self.client.get_collection(collection_name=collection_name)
                    # Check for dimension mismatch
                    if info.config.params.vectors.size != 3072:
                        logger.warning(f"Dimension mismatch (expected 3072, got {info.config.params.vectors.size}). Recreating collection.")
                        self.client.delete_collection(collection_name=collection_name)
                        raise ValueError("Recreate")
                except Exception:
                    logger.info(f"Creating collection: {collection_name}")
                    from qdrant_client.http import models as rest
                    self.client.create_collection(
                        collection_name=collection_name,
                        vectors_config=rest.VectorParams(
                            size=3072, # Dimensions for models/gemini-embedding-001
                            distance=rest.Distance.COSINE,
                        ),
                    )
                    
                # Ensure payload indexes exist for filtering
                try:
                    from qdrant_client.http import models as rest
                    self.client.create_payload_index(
                        collection_name=collection_name,
                        field_name="metadata.document_id",
                        field_schema=rest.PayloadSchemaType.KEYWORD,
                    )
                    self.client.create_payload_index(
                        collection_name=collection_name,
                        field_name="metadata.category_id",
                        field_schema=rest.PayloadSchemaType.KEYWORD,
                    )
                    logger.info("Payload indices created successfully.")
                except Exception as e:
                    # Ignore if index already exists
                    if "already exists" not in str(e).lower():
                        logger.warning(f"Note: Payload index creation skipped or failed: {e}")

                self.vector_store = QdrantVectorStore(
                    client=self.client,
                    collection_name=collection_name,
                    embedding=self.embeddings,
                )
            except Exception as e:
                logger.error(f"Failed to initialize Qdrant Cloud: {str(e)}")
                self.client = None
                self.vector_store = None
        else:
            self.client = None
            self.vector_store = None
            logger.warning("Qdrant Cloud configuration is missing. Vector store will not be available.")

    async def index_document(self, file_url: str, metadata: dict, file_type: str = None):
        """Extract text from file and index it in Qdrant."""
        if not self.vector_store:
            logger.warning("Vector store not initialized, skipping indexing.")
            return

        try:
            logger.info(f"Starting indexing for document: {metadata.get('name')} ({file_url})")
            
            # 1. Get file content directly from storage to avoid local HTTP issues
            from app.helper.file_handler import file_handler
            file_id = file_url.split("/")[-1]
            file_data = file_handler.get_file(file_id)
            
            file_content = None
            if isinstance(file_data, dict) and "Body" in file_data:
                # S3 Storage
                file_content = file_data["Body"].read()
                logger.info("Fetched file content from S3.")
            else:
                # Check for local file path
                local_info = file_handler.get_file_info(file_id)
                if local_info and os.path.exists(local_info):
                    with open(local_info, "rb") as f:
                        file_content = f.read()
                    logger.info(f"Read file content from local path: {local_info}")
                else:
                    # Final fallback to requests if path/id resolution fails
                    logger.info(f"Attempting fallback download via HTTP: {file_url}")
                    response = requests.get(file_url, timeout=10)
                    if response.status_code == 200:
                        file_content = response.content
                    else:
                        logger.error(f"Failed to fetch file. Status: {response.status_code}")
                        return

            if not file_content:
                logger.error("Could not retrieve file content for indexing.")
                return

            # 2. Extract text based on file type
            text = ""
            filename = metadata.get("name", "").lower() or file_url.lower()
            
            if file_type == "application/pdf" or filename.endswith(".pdf"):
                logger.info("Extracting text from PDF...")
                pdf_reader = pypdf.PdfReader(io.BytesIO(file_content))
                for page in pdf_reader.pages:
                    text += (page.extract_text() or "") + "\n"
            elif file_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document" or filename.endswith(".docx"):
                logger.info("Extracting text from DOCX...")
                doc = DocxDocument(io.BytesIO(file_content))
                for para in doc.paragraphs:
                    text += para.text + "\n"
            else:
                # Try as plain text
                try:
                    text = file_content.decode("utf-8")
                    logger.info("Extracted as plain text.")
                except:
                    logger.warning(f"Unsupported/Binary file type for indexing: {file_type}")
                    return

            if not text.strip():
                logger.warning(f"No text extracted from document: {metadata.get('name')}")
                return

            logger.info(f"Extracted {len(text)} characters. Chunking...")

            # 3. Chunk text
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000, 
                chunk_overlap=200
            )
            chunks = text_splitter.split_text(text)
            logger.info(f"Created {len(chunks)} chunks.")

            # 4. Create documents with metadata
            docs = [
                Document(page_content=chunk, metadata={**metadata, "chunk_index": i})
                for i, chunk in enumerate(chunks)
            ]

            # 5. Add to Qdrant
            self.vector_store.add_documents(docs)
            logger.info(f"Successfully indexed document: {metadata.get('name')} in Qdrant.")

        except Exception as e:
            logger.error(f"Error indexing document {metadata.get('name')}: {str(e)}", exc_info=True)

    async def search_documents(self, query: str, filter_dict: dict = None, limit: int = 5) -> List[dict]:
        """Search for relevant document snippets."""
        if not self.vector_store:
            return []

        try:
            # Qdrant filtering can be complex, for now we do simple similarity search
            # We can expand this later to use metadata filtering
            results = self.vector_store.similarity_search(query, k=limit)
            
            return [
                {
                    "content": res.page_content,
                    "metadata": res.metadata
                }
                for res in results
            ]
        except Exception as e:
            logger.error(f"Search failed: {str(e)}")
            return []

    async def delete_document(self, document_id: str):
        """Delete all vectors associated with a document ID."""
        if not self.client:
            return

        try:
            from qdrant_client.http import models as rest
            self.client.delete(
                collection_name=QDRANT_COLLECTION_NAME,
                points_selector=rest.Filter(
                    must=[
                        rest.FieldCondition(
                            key="metadata.document_id",
                            match=rest.MatchValue(value=document_id),
                        ),
                    ]
                ),
            )
            logger.info(f"Deleted vectors for document_id: {document_id}")
        except Exception as e:
            logger.error(f"Failed to delete vectors: {str(e)}")

vector_store_service = VectorStoreService()
