# Vectorization Approach Details
## Document Vectorizer - Technical Specification

**Version**: 1.0  
**Date**: August 2025  
**System**: Document Vectorizer with OpenAI Embeddings & Supabase Storage

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Architecture](#system-architecture)
3. [Document Processing Pipeline](#document-processing-pipeline)
4. [File Type Processing Specifications](#file-type-processing-specifications)
5. [Text Chunking Methodology](#text-chunking-methodology)
6. [Embedding Generation](#embedding-generation)
7. [Vector Storage and Indexing](#vector-storage-and-indexing)
8. [Memory Management and Constraints](#memory-management-and-constraints)
9. [Special Handling and Edge Cases](#special-handling-and-edge-cases)
10. [Configuration Parameters](#configuration-parameters)
11. [Performance Characteristics](#performance-characteristics)
12. [Quality Assurance and Monitoring](#quality-assurance-and-monitoring)

---

## 1. Executive Summary

The Document Vectorizer is a production-grade system designed to continuously monitor Google Drive folders, extract content from various document formats, and convert them into searchable vector embeddings stored in Supabase. The system uses OpenAI's `text-embedding-3-small` model to generate 1536-dimensional vectors that enable semantic search capabilities.

### Key Capabilities
- **Automated Processing**: Continuous monitoring with configurable polling intervals (default: 5 minutes)
- **Multi-Format Support**: PDF, DOCX, DOC, XLSX, XLS, CSV, TXT, and Google Workspace formats
- **Scalable Architecture**: Batch processing with rate limiting and memory management
- **Semantic Search**: Vector similarity search using cosine distance
- **Cost Control**: Built-in rate limiting and daily cost caps ($10/day default)

### Processing Capacity
- **File Size Limit**: 50MB per file
- **PDF Pages**: Maximum 1,000 pages per document
- **Excel Rows**: Maximum 100,000 rows per spreadsheet
- **Batch Size**: 100 document chunks per embedding batch
- **Vector Dimensions**: 1,536 (fixed by text-embedding-3-small model)

---

## 2. System Architecture

### Component Overview

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Google Drive   │────▶│ Document         │────▶│ Vector Store    │
│  Monitor        │     │ Extractor        │     │ Processor       │
└─────────────────┘     └──────────────────┘     └─────────────────┘
         │                       │                         │
         ▼                       ▼                         ▼
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  File Tracker   │     │ Text Splitter    │     │ OpenAI API      │
│  (Persistence)  │     │ (Chunking)       │     │ (Embeddings)    │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                                           │
                                                           ▼
                                                  ┌─────────────────┐
                                                  │ Supabase        │
                                                  │ (pgvector)      │
                                                  └─────────────────┘
```

### Data Flow
1. **Discovery**: Google Drive API polls for new/modified files
2. **Download**: Files are downloaded to temporary storage
3. **Extraction**: Content is extracted based on file type
4. **Chunking**: Text is split into manageable chunks
5. **Embedding**: Chunks are converted to vectors via OpenAI
6. **Storage**: Vectors and metadata stored in Supabase
7. **Cleanup**: Temporary files removed, memory freed

---

## 3. Document Processing Pipeline

### Stage 1: File Discovery and Filtering

```python
# File discovery process
1. Poll Google Drive folder (recursive scanning enabled)
2. Compare with file tracker (persistent state)
3. Identify new or modified files
4. Apply file size filter (50MB max)
5. Queue for processing
```

**Key Features:**
- Recursive folder traversal for nested structures
- Persistent file tracking survives restarts
- Modified time comparison for update detection
- Google Drive API caching (2-minute duration)
- Rate limiting: 10 API calls/second maximum

### Stage 2: Content Extraction

```python
# Extraction pipeline
1. Download file to temporary storage
2. Detect MIME type
3. Apply size and page limits
4. Execute type-specific extractor
5. Return structured or text content
6. Cleanup and garbage collection
```

### Stage 3: Vectorization

```python
# Vectorization process
1. Split text into chunks (RecursiveCharacterTextSplitter)
2. Create metadata for each chunk
3. Generate embeddings in batches
4. Store vectors with metadata
5. Update processing statistics
```

---

## 4. File Type Processing Specifications

### PDF Files (application/pdf)

**Extraction Method**: PyPDF2 (`pypdf`)

**Processing Details:**
- **Page Limit**: 1,000 pages maximum
- **Text Extraction**: Per-page extraction with concatenation
- **Memory Management**: Garbage collection every 50 pages
- **Error Handling**: Fallback to empty text on extraction failure
- **Special Handling**: PDF metadata preserved (page count, total pages)

**Output Structure:**
```json
{
    "type": "text",
    "content": "extracted text content...",
    "page_count": 150,
    "pages_processed": 150,
    "extraction_method": "pypdf_limited"
}
```

### Microsoft Word Documents

#### DOCX Files (application/vnd.openxmlformats-officedocument.wordprocessingml.document)

**Extraction Method**: Dual-method approach
1. **Primary**: Mammoth (preserves formatting better)
2. **Fallback**: python-docx (more reliable)

**Processing Details:**
- **Paragraph Extraction**: All non-empty paragraphs
- **Table Processing**: Tables converted to pipe-delimited text
- **Formatting**: Basic structure preserved (paragraphs, tables)
- **Memory**: Direct BytesIO processing, no temp files

**Output Structure:**
```json
{
    "type": "text",
    "content": "document text with tables...",
    "paragraph_count": 45,
    "table_count": 3,
    "extraction_method": "mammoth" | "python-docx"
}
```

#### DOC Files (application/msword)

**Extraction Method**: Mammoth with temp file
- Fallback to plain text extraction if Mammoth fails

### Excel and CSV Files

#### Excel Files (XLSX/XLS)

**Extraction Method**: Pandas with openpyxl engine

**Processing Details:**
- **Row Limit**: 100,000 rows maximum
- **Sheet Processing**: All sheets processed sequentially
- **NaN Handling**: Converted to None for JSON compatibility
- **Dual Storage**: 
  - Structured data in `document_rows` table
  - Text representation vectorized for search

**Special Features:**
- Schema extraction per sheet
- Large sheet truncation with warnings
- Memory-efficient batch processing

**Output Structure:**
```json
{
    "type": "structured",
    "content": "text representation of data",
    "data": [{"col1": "val1", "col2": "val2"}, ...],
    "schema": {"Sheet1": ["col1", "col2"]},
    "sheet_count": 3,
    "row_count": 5420,
    "extraction_method": "pandas_excel_limited"
}
```

#### CSV Files

**Extraction Method**: Pandas with encoding detection

**Processing Details:**
- **Encoding Detection**: Chardet for automatic encoding
- **Row Limit**: 100,000 rows (same as Excel)
- **Structure**: Similar to Excel single-sheet processing

### Plain Text Files

**Extraction Method**: Direct decode with encoding detection

**Processing Details:**
- **Encoding**: Auto-detection using chardet
- **Size Limit**: 50MB (global limit)
- **Error Handling**: Replace malformed characters

### Google Workspace Files

**Conversion Process:**
- Google Docs → Plain text (via export API)
- Google Sheets → CSV format
- Google Slides → Plain text

**Note**: Files are converted server-side by Google before download

### Unsupported File Types

Files with unrecognized MIME types return:
```json
{
    "type": "error",
    "content": "",
    "error": "Unsupported file type: {mime_type}",
    "extraction_method": "none"
}
```

---

## 5. Text Chunking Methodology

### Chunking Algorithm: RecursiveCharacterTextSplitter

The system uses LangChain's `RecursiveCharacterTextSplitter`, which intelligently splits text while preserving semantic coherence.

### Chunking Parameters

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| chunk_size | 400 chars | 50-2000 | Target size for each chunk |
| chunk_overlap | 50 chars | 0-500 | Overlap between consecutive chunks |
| length_function | len | - | Character counting method |

### Separator Hierarchy

The splitter attempts to split text at natural boundaries, trying each separator in order:

1. `"\n\n"` - Double newline (paragraph boundaries)
2. `"\n"` - Single newline (line boundaries)
3. `". "` - Sentence boundaries
4. `" "` - Word boundaries
5. `""` - Character level (last resort)

### Chunking Strategy

```python
# Example chunking process for a 2000-character document
Document: "This is paragraph one.\n\nThis is paragraph two..."
         ↓
Chunks: [
    "This is paragraph one.",  # Chunk 1 (clean paragraph break)
    "This is paragraph two...", # Chunk 2 (overlaps if needed)
]
```

**Benefits:**
- **Semantic Preservation**: Keeps related content together
- **Context Overlap**: Maintains continuity between chunks
- **Flexible Boundaries**: Adapts to document structure
- **Search Quality**: Better retrieval accuracy

### Metadata per Chunk

Each chunk includes:
```json
{
    "file_id": "google_drive_file_id",
    "file_title": "Document Name.pdf",
    "file_url": "https://drive.google.com/...",
    "chunk_index": 0,
    "total_chunks": 15,
    "extraction_method": "pypdf_limited"
}
```

---

## 6. Embedding Generation

### Model Specifications

**Model**: OpenAI `text-embedding-3-small`
- **Dimensions**: 1,536
- **Context Window**: 8,191 tokens
- **Cost**: $0.02 per 1M tokens
- **Performance**: Optimized for speed and cost-efficiency

### Embedding Process

```python
# Batch embedding generation
1. Collect chunks into batches (max 100)
2. Check rate limits (3000 RPM, 1M TPM)
3. Estimate token count for batch
4. Wait if rate limit would be exceeded
5. Call OpenAI embeddings API
6. Record usage for cost tracking
7. Return 1536-dimensional vectors
```

### Rate Limiting System

**Three-Tier Rate Limiting:**

1. **Request Rate**: 
   - 10 requests/minute
   - 100 requests/hour
   - 1000 requests/day

2. **Token Rate**:
   - 1,000,000 tokens/minute (OpenAI limit)
   - Token estimation before API calls

3. **Cost Control**:
   - $10/day default limit
   - Automatic shutdown on limit breach
   - Real-time cost tracking

### Vector Characteristics

**Embedding Properties:**
- **Type**: Dense float32 vectors
- **Dimensions**: 1,536 (fixed)
- **Normalization**: L2 normalized by OpenAI
- **Distance Metric**: Cosine similarity
- **Storage Size**: ~6KB per vector

---

## 7. Vector Storage and Indexing

### Database Architecture

**Supabase Tables:**

#### 1. documents (Vector Storage)
```sql
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    content TEXT,
    metadata JSONB,
    embedding vector(1536),
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Indexes:**
- Primary key index on `id`
- IVFFLAT index on `embedding` for similarity search
- GIN index on `metadata` for JSON queries

#### 2. document_metadata (File Information)
```sql
CREATE TABLE document_metadata (
    id TEXT PRIMARY KEY,  -- Google Drive file ID
    title TEXT,
    url TEXT,
    created_at TIMESTAMP,
    schema JSONB  -- For structured data
);
```

#### 3. document_rows (Structured Data)
```sql
CREATE TABLE document_rows (
    id SERIAL PRIMARY KEY,
    dataset_id TEXT,  -- References document_metadata.id
    row_data JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Similarity Search

**Search Function:**
```sql
CREATE FUNCTION match_documents(
    query_embedding vector(1536),
    match_count int
)
RETURNS TABLE (
    content TEXT,
    metadata JSONB,
    similarity float
)
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        documents.content,
        documents.metadata,
        1 - (documents.embedding <=> query_embedding) AS similarity
    FROM documents
    ORDER BY documents.embedding <=> query_embedding
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;
```

**Search Process:**
1. Generate embedding for search query
2. Calculate cosine distance to all vectors
3. Return top-k most similar documents
4. Include metadata for filtering/context

---

## 8. Memory Management and Constraints

### File Size Limits

| File Type | Size Limit | Page/Row Limit | Rationale |
|-----------|------------|----------------|-----------|
| All Files | 50MB | - | Memory protection |
| PDF | 50MB | 1,000 pages | Processing time |
| Excel/CSV | 50MB | 100,000 rows | Memory usage |
| Text/Doc | 50MB | - | Global limit |

### Memory Optimization Strategies

1. **Streaming Processing**:
   - Large files processed in chunks
   - BytesIO for in-memory processing
   - Immediate cleanup after processing

2. **Garbage Collection**:
   ```python
   # Explicit GC triggers
   - After each file processing
   - Every 50 PDF pages
   - Every 10,000 Excel rows
   - On processing errors
   ```

3. **Resource Limits** (Docker):
   - Memory: 4GB limit
   - CPU: 2.0 cores limit
   - Shared memory: 1GB

4. **File Tracker Persistence**:
   - Stored in `/app/data/tracker/processed_files.json`
   - Survives container restarts
   - Prevents reprocessing

### Memory Usage Monitoring

```python
# Memory logging at key points
- Before file processing
- After content extraction
- After vectorization
- On error conditions
```

---

## 9. Special Handling and Edge Cases

### URL and Hyperlink Processing

**Current Behavior:**
- URLs in document text are preserved as-is
- No special extraction or following of links
- Google Drive webViewLink stored in metadata
- No hyperlink text extraction from PDFs

**Metadata Storage:**
```json
{
    "file_url": "https://drive.google.com/file/d/.../view",
    "file_id": "1ABC...XYZ",
    "file_title": "Document with links.pdf"
}
```

### Structured Data Dual Processing

Excel and CSV files receive special treatment:

1. **Structured Storage**: Raw rows in `document_rows` table
2. **Vector Storage**: Text representation for semantic search
3. **Schema Preservation**: Column names stored in metadata

**Benefits:**
- Enables both structured queries and semantic search
- Preserves data relationships
- Allows reconstruction of original structure

### Error Recovery Mechanisms

1. **Extraction Failures**:
   - Fallback extraction methods (e.g., Mammoth → python-docx)
   - Error result with detailed message
   - File marked as processed to prevent loops

2. **API Failures**:
   - Exponential backoff (4-10 seconds)
   - Maximum 3 retry attempts
   - Rate limit recovery with wait times

3. **Memory Errors**:
   - Immediate garbage collection
   - Process restart capability
   - Docker health checks and auto-restart

### Google Drive Integration

**Special Features:**
- Recursive folder scanning
- File modification tracking
- Google Workspace format conversion
- Shared drive support

**Caching Strategy:**
- File listings cached for 2 minutes
- Reduces API calls by ~60%
- Cache invalidation on folder changes

---

## 10. Configuration Parameters

### Runtime Configurable Settings

Settings that can be modified via UI and persist across restarts:

| Setting | Default | Range | UI Configurable |
|---------|---------|-------|-----------------|
| polling_interval | 300s | 30-86400s | ✅ |
| chunk_size | 400 | 50-2000 | ✅ |
| chunk_overlap | 50 | 0-500 | ✅ |
| batch_size | 100 | 1-1000 | ✅ |
| max_retries | 3 | 1-10 | ✅ |

### Environment Variables

Set in `.env.tnt` file:

```bash
# Core Settings
GOOGLE_DRIVE_FOLDER_ID=your_folder_id
OPENAI_API_KEY=sk-...
SUPABASE_URL=https://...supabase.co
SUPABASE_KEY=eyJ...

# Rate Limiting
RATE_LIMIT_ENABLED=true
MAX_REQUESTS_PER_MINUTE=8
MAX_REQUESTS_PER_HOUR=80
MAX_REQUESTS_PER_DAY=800
MAX_DAILY_COST_USD=10.00

# Processing
MONITOR_INTERVAL=300  # Overridden by runtime settings
BATCH_SIZE=5
CHUNK_SIZE=300
CHUNK_OVERLAP=50

# Resource Limits
MAX_FILE_SIZE_MB=50
MAX_PDF_PAGES=1000
MAX_EXCEL_ROWS=100000
```

### Performance Tuning

**Conservative Settings** (Stability):
```
polling_interval=300
batch_size=5
chunk_size=300
max_retries=3
```

**Aggressive Settings** (Speed):
```
polling_interval=60
batch_size=100
chunk_size=500
max_retries=1
```

---

## 11. Performance Characteristics

### Processing Speed

**Typical Throughput:**
- **PDF**: ~10 pages/second
- **DOCX**: ~5 documents/minute
- **Excel**: ~1,000 rows/second
- **Embeddings**: ~100 chunks/minute

### Resource Usage

**Per File Type:**
| File Type | Memory Usage | Processing Time | CPU Usage |
|-----------|--------------|-----------------|-----------|
| PDF (100 pages) | ~200MB | ~10 seconds | 40% |
| DOCX (50 pages) | ~100MB | ~5 seconds | 30% |
| Excel (10k rows) | ~300MB | ~15 seconds | 60% |
| Text (1MB) | ~50MB | ~2 seconds | 20% |

### Scalability Limits

**System Capacity:**
- **Files/Hour**: ~500 (depends on size/type)
- **Vectors/Day**: ~100,000 (with rate limits)
- **Storage**: ~1GB per 100,000 vectors
- **Concurrent Files**: 1 (sequential processing)

### Cost Analysis

**OpenAI API Costs:**
- Embedding: $0.02 per 1M tokens
- Average document: ~5,000 tokens
- Cost per document: ~$0.0001
- Daily budget: $10 (default)
- Documents per dollar: ~10,000

---

## 12. Quality Assurance and Monitoring

### Processing Validation

**Automatic Checks:**
1. File size validation before download
2. Content extraction verification
3. Chunk count validation
4. Embedding dimension check (must be 1536)
5. Database insertion confirmation

### Monitoring Metrics

**Dashboard Displays:**
- Total documents processed
- Total vectors created
- Processing errors
- Current processing queue
- API rate limit status
- Daily cost accumulation

### Error Tracking

**Logged Error Types:**
- Extraction failures (by file type)
- API rate limit breaches
- Memory limit exceeded
- Database connection errors
- File size limit violations

### Success Metrics

**Key Performance Indicators:**
- **Processing Success Rate**: Target >95%
- **Average Processing Time**: <30s per document
- **Vector Quality**: Semantic search accuracy >80%
- **System Uptime**: >99%
- **Cost Efficiency**: <$0.001 per document

### Health Checks

**Automated Monitoring:**
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:5555/health"]
  interval: 30s
  timeout: 10s
  retries: 3
```

**Health Endpoint Checks:**
- Google Drive connectivity
- Supabase connection
- OpenAI API availability
- Memory usage <80%
- Processing queue status

---

## Appendix A: Common Issues and Solutions

### Issue: Large PDFs Timeout
**Solution**: Implement streaming PDF processing or increase timeout limits

### Issue: Excel Formulas Lost
**Solution**: Formulas are evaluated to values; preserve formulas in metadata if needed

### Issue: Special Characters Corrupted
**Solution**: Encoding detection handles most cases; UTF-8 fallback for edge cases

### Issue: Duplicate Processing
**Solution**: File tracker prevents reprocessing; check `/app/data/tracker/processed_files.json`

### Issue: Rate Limit Exceeded
**Solution**: Adjust batch size, implement backoff, or increase daily limits

---

## Appendix B: Future Enhancements

### Planned Improvements
1. **OCR Support**: For scanned PDFs and images
2. **Parallel Processing**: Multiple files simultaneously
3. **Custom Embeddings**: Support for alternative models
4. **Incremental Updates**: Process only changed portions
5. **Language Detection**: Multi-language support
6. **URL Following**: Extract content from embedded links
7. **Table Extraction**: Better structure preservation
8. **Compression**: Reduce storage requirements

---

## Conclusion

The Document Vectorizer implements a robust, production-ready pipeline for converting various document formats into searchable vector embeddings. The system balances performance, reliability, and cost-effectiveness while providing extensive configurability and monitoring capabilities. The architecture supports both current requirements and future enhancements, making it a sustainable solution for document processing and semantic search needs.

---

**Document Version**: 1.0  
**Last Updated**: November 2024  
**Maintained By**: TNT Document Vectorizer Team