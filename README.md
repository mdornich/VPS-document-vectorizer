# Google Drive Vectorization

A Python application that monitors a Google Drive folder, extracts content from documents, and stores them as searchable vectors in Supabase.

## Features

- 📁 **Automatic folder monitoring** - Continuously monitors Google Drive folders for new/updated files
- 🔄 **Nested folder support** - Recursively processes files in subfolders
- 📄 **Multi-format support** - Handles PDF, Word (DOC/DOCX), Excel (XLS/XLSX), CSV, and text files
- 🔍 **Vector search** - Creates searchable embeddings using OpenAI's text-embedding-3-small model
- 💾 **Structured data storage** - Preserves spreadsheet structure in addition to vectors
- 🐳 **Docker deployment** - Production-ready containerized deployment

## Quick Start

```bash
# Clone and enter directory
cd /Users/mitchdornich/document-vectorizer

# Set up environment
cp .env.example .env
# Edit .env with your credentials

# Run with Docker
docker-compose up -d --build

# View logs
docker-compose logs -f
```

## Author

Created with assistance from Claude
