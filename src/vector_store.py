import json
from typing import List, Dict, Any, Optional
from datetime import datetime
import hashlib

from supabase import create_client, Client
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document as LangchainDocument
from langchain_openai import OpenAIEmbeddings
import openai
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import settings
from src.rate_limiter import get_rate_limiter, estimate_tokens
from src.rate_limiter_api import rate_limiter as api_rate_limiter

logger = structlog.get_logger()


class VectorStore:
    """Manage document vectorization and storage in Supabase."""
    
    def __init__(self):
        # Initialize Supabase client
        self.supabase: Client = create_client(
            settings.supabase_url,
            settings.supabase_key
        )
        
        # Initialize OpenAI client
        openai.api_key = settings.openai_api_key
        
        # Initialize embeddings
        self.embeddings = OpenAIEmbeddings(
            openai_api_key=settings.openai_api_key,
            model=settings.openai_embedding_model
        )
        
        # Initialize text splitter
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        
        logger.info("Vector store initialized")
    
    @retry(
        stop=stop_after_attempt(settings.max_retries),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def process_document(
        self,
        extracted_content: Dict[str, Any],
        file_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process a document and store it in the vector database.
        
        Args:
            extracted_content: Extracted content from document
            file_metadata: Google Drive file metadata
        
        Returns:
            Processing result with statistics
        """
        file_id = file_metadata['id']
        file_name = file_metadata['name']
        
        try:
            logger.info(f"Processing document: {file_name} (ID: {file_id})")
            
            # Clean up old data first
            self._delete_existing_data(file_id)
            
            # Store metadata
            self._upsert_metadata(file_metadata, extracted_content)
            
            # Process based on content type
            if extracted_content['type'] == 'structured':
                result = self._process_structured_data(
                    extracted_content,
                    file_metadata
                )
            else:
                result = self._process_text_content(
                    extracted_content,
                    file_metadata
                )
            
            logger.info(f"Successfully processed {file_name}: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error processing document {file_name}: {e}")
            raise
    
    def _delete_existing_data(self, file_id: str):
        """Delete existing data for a file before re-processing."""
        try:
            # Delete from documents table (vectors)
            # Using raw SQL for JSONB query to avoid syntax issues
            try:
                # Use parameterized query for safety
                delete_response = self.supabase.rpc(
                    'delete_vectors_by_file_id',
                    {'target_file_id': file_id}
                ).execute()
                
                if delete_response.data:
                    logger.info(f"Deleted existing vectors for {file_id}")
            except:
                # If RPC doesn't exist, skip deletion
                logger.debug(f"Could not delete existing vectors for {file_id}")
            
            # Delete from document_rows table (structured data)
            rows_response = self.supabase.table(
                settings.supabase_rows_table
            ).delete().eq('dataset_id', file_id).execute()
            
            if rows_response.data:
                logger.info(f"Deleted {len(rows_response.data)} existing rows for {file_id}")
                
        except Exception as e:
            logger.warning(f"Error deleting existing data: {e}")
    
    def _upsert_metadata(
        self,
        file_metadata: Dict[str, Any],
        extracted_content: Dict[str, Any]
    ):
        """Upsert document metadata."""
        try:
            metadata_record = {
                'id': file_metadata['id'],
                'title': file_metadata['name'],
                'url': file_metadata.get('webViewLink', ''),
                'created_at': datetime.utcnow().isoformat(),
                'schema': json.dumps(extracted_content.get('schema', {}))
                if extracted_content.get('schema') else None
            }
            
            response = self.supabase.table(
                settings.supabase_metadata_table
            ).upsert(metadata_record).execute()
            
            logger.debug(f"Upserted metadata for {file_metadata['name']}")
            
        except Exception as e:
            logger.error(f"Error upserting metadata: {e}")
            raise
    
    def _process_text_content(
        self,
        extracted_content: Dict[str, Any],
        file_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process text content and create vectors."""
        content = extracted_content.get('content', '')
        
        if not content:
            return {
                'status': 'skipped',
                'reason': 'No content to process',
                'chunks': 0
            }
        
        # Split text into chunks
        chunks = self.text_splitter.split_text(content)
        
        # Create documents with metadata
        documents = []
        for i, chunk in enumerate(chunks):
            doc_metadata = {
                'file_id': file_metadata['id'],
                'file_title': file_metadata['name'],
                'file_url': file_metadata.get('webViewLink', ''),
                'chunk_index': i,
                'total_chunks': len(chunks),
                'extraction_method': extracted_content.get('extraction_method', 'unknown')
            }
            
            doc = LangchainDocument(
                page_content=chunk,
                metadata=doc_metadata
            )
            documents.append(doc)
        
        # Add documents to vector store in batches using direct Supabase insert
        batch_size = settings.batch_size
        total_added = 0
        rate_limiter = get_rate_limiter()
        
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]
            
            # Check rate limit before making API call
            allowed, error_msg = api_rate_limiter.check_rate_limit('embedding')
            if not allowed:
                logger.error(f"Rate limit exceeded: {error_msg}")
                raise Exception(error_msg)
            
            # Estimate tokens and wait if needed for rate limiting
            texts = [doc.page_content for doc in batch]
            estimated_tokens = sum(estimate_tokens(text) for text in texts)
            rate_limiter.wait_if_needed(estimated_tokens)
            
            # Generate embeddings for the batch
            embeddings = self.embeddings.embed_documents(texts)
            
            # Record API usage for cost tracking
            api_rate_limiter.record_usage('embedding', len(texts))
            
            # Record actual usage (approximate)
            rate_limiter.record_usage(estimated_tokens)
            
            # Prepare records for insertion
            records = []
            for doc, embedding in zip(batch, embeddings):
                record = {
                    'content': doc.page_content,
                    'metadata': doc.metadata,
                    'embedding': embedding
                }
                records.append(record)
            
            # Insert directly into Supabase
            try:
                self.supabase.table(settings.supabase_documents_table).insert(records).execute()
                total_added += len(batch)
                logger.debug(f"Added batch of {len(batch)} documents")
            except Exception as e:
                logger.error(f"Error inserting vectors: {e}")
                # Try inserting one by one if batch fails
                for record in records:
                    try:
                        self.supabase.table(settings.supabase_documents_table).insert(record).execute()
                        total_added += 1
                    except Exception as single_error:
                        logger.error(f"Failed to insert single document: {single_error}")
        
        return {
            'status': 'success',
            'chunks': len(chunks),
            'vectors_created': total_added,
            'content_length': len(content)
        }
    
    def _process_structured_data(
        self,
        extracted_content: Dict[str, Any],
        file_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process structured data (tables/spreadsheets)."""
        import numpy as np
        import pandas as pd
        
        data_rows = extracted_content.get('data', [])
        schema = extracted_content.get('schema', {})
        
        # Store raw data rows
        if data_rows:
            for row in data_rows:
                # Clean NaN/NaT values before JSON serialization
                cleaned_row = {}
                for key, value in row.items():
                    if pd.isna(value) or value is pd.NaT:
                        cleaned_row[key] = None
                    elif isinstance(value, (np.integer, np.floating)):
                        cleaned_row[key] = float(value)
                    elif isinstance(value, np.ndarray):
                        cleaned_row[key] = value.tolist()
                    elif isinstance(value, (pd.Timestamp, datetime)):
                        cleaned_row[key] = value.isoformat() if hasattr(value, 'isoformat') else str(value)
                    else:
                        cleaned_row[key] = value
                
                row_record = {
                    'dataset_id': file_metadata['id'],
                    'row_data': json.dumps(cleaned_row)
                }
                
                self.supabase.table(
                    settings.supabase_rows_table
                ).insert(row_record).execute()
        
        # Also vectorize the text representation
        text_content = extracted_content.get('content', '')
        if text_content:
            text_result = self._process_text_content(
                {'content': text_content, 'type': 'text'},
                file_metadata
            )
        else:
            text_result = {'vectors_created': 0}
        
        return {
            'status': 'success',
            'rows_stored': len(data_rows),
            'vectors_created': text_result.get('vectors_created', 0),
            'schema_fields': len(schema) if isinstance(schema, dict) else 0
        }
    
    @retry(
        stop=stop_after_attempt(settings.max_retries),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def search_similar(
        self,
        query: str,
        k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar documents in the vector store.
        
        Args:
            query: Search query
            k: Number of results to return
            filter_metadata: Optional metadata filters
        
        Returns:
            List of similar documents with scores
        """
        try:
            # Generate embedding for the query
            query_embedding = self.embeddings.embed_query(query)
            
            # Use Supabase RPC function for similarity search
            # This assumes you have a match_documents function in Supabase
            results = self.supabase.rpc(
                'match_documents',
                {
                    'query_embedding': query_embedding,
                    'match_count': k
                }
            ).execute()
            
            formatted_results = []
            for doc in results.data:
                formatted_results.append({
                    'content': doc.get('content', ''),
                    'metadata': doc.get('metadata', {}),
                    'score': doc.get('similarity', 0)
                })
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            raise
    
    def get_document_stats(self) -> Dict[str, Any]:
        """Get statistics about stored documents."""
        try:
            # Count documents
            doc_count = self.supabase.table(
                settings.supabase_metadata_table
            ).select('id', count='exact').execute()
            
            # Count vectors
            vector_count = self.supabase.table(
                settings.supabase_documents_table
            ).select('id', count='exact').execute()
            
            return {
                'total_documents': doc_count.count if hasattr(doc_count, 'count') else 0,
                'total_vectors': vector_count.count if hasattr(vector_count, 'count') else 0,
                'avg_vectors_per_doc': (
                    vector_count.count / doc_count.count 
                    if doc_count.count and hasattr(doc_count, 'count') else 0
                )
            }
            
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {
                'total_documents': 0,
                'total_vectors': 0,
                'avg_vectors_per_doc': 0
            }