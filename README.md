# Medical Document Processing Backend

A complete FastAPI backend for processing medical documents, converting them to images, uploading to S3, and extracting information using AI APIs.

## Features

- ✅ **Document Support**: PDF, PNG, JPG, JPEG, WEBP, and more
- ✅ **Automatic Conversion**: Converts PDFs and images to JPEG format using existing converter
- ✅ **S3 Integration**: Uploads images to AWS S3 using pre-signed URLs
- ✅ **AI Processing**: Orchestrates external AI APIs for document extraction
- ✅ **Job Polling**: Polls extraction job status until completion
- ✅ **Supabase Integration**: Updates case summaries directly in database
- ✅ **Async Workflow**: Non-blocking processing for better UX

## Project Structure

```
backend/
├── app/
│   ├── main.py                 # FastAPI application setup
│   ├── api/
│   │   └── routes.py           # API endpoints
│   ├── services/
│   │   ├── ai_pipeline.py      # AI API orchestration
│   │   ├── uploader.py         # S3 upload handling
│   │   └── supabase_service.py # Supabase database operations
│   ├── utils/
│   │   └── temp_storage.py     # Temporary file management
│   └── models/
│       └── schemas.py          # Pydantic request/response models
├── converter/                   # EXISTING converter (DO NOT MODIFY)
│   ├── converter.py
│   └── requirements.txt
├── requirements.txt            # Backend dependencies
├── .env.example                # Environment variables template
└── README.md                   # This file
```

## Installation

### 1. Install Backend Dependencies

```bash
pip install -r requirements.txt
```

### 2. Environment Configuration

Create a `.env` file in the `Backend` directory:

```bash
cp .env.example .env
```

Edit `.env` with your Supabase credentials:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key-here
```

⚠️ **IMPORTANT**: Use the **service role key** (not anon key) for backend operations.

Optional: For SVG support:
```bash
pip install cairosvg
```

## Running the Backend

### Start the API Server

```bash
uvicorn app.main:app --reload
```

The server will start at `http://127.0.0.1:8000`

### API Documentation

Once running, access the interactive documentation:
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

## API Endpoints

### Health Check

```
GET /health
```

Returns service health status.

### Process Medical Case

```
POST /process-case
Content-Type: multipart/form-data
```

**Request:**
- `files`: Multiple files (PDF, images, optional TXT)
- `case_id`: UUID of the case in Supabase (required)
- `user_id`: UUID of the user (required)

**Response:**
```json
{
  "status": "processing_started",
  "summary_markdown": null
}
```

**Error Response:**
```json
{
  "status": "error",
  "message": "Error description"
}
```

## Testing with Postman

1. Create a new POST request to `http://127.0.0.1:8000/process-case`
2. Go to **Body** tab
3. Select **form-data**
4. Add key `files` with type **File** and upload multiple PDFs/images
5. Add key `case_id` with type **Text** and a valid UUID
6. Add key `user_id` with type **Text** and a valid UUID
7. Click **Send**

## Processing Flow

The backend implements a 10-step processing pipeline:

### STEP 1️⃣ – Save Uploaded Files
Files are saved temporarily to `/tmp/uploads/<request_id>/raw/`

### STEP 2️⃣ – Convert Documents
Uses the existing converter to generate JPEG images from PDFs and images.
Preserves file ordering.

### STEP 3️⃣ – Get Upload URLs
Calls external API to get pre-signed S3 URLs:
```
POST https://pxyanaujf9.execute-api.ap-south-1.amazonaws.com/dev/get-upload-urls
```

### STEP 4️⃣ – Upload to S3
Uploads all JPEG images using pre-signed URLs.

### STEP 5️⃣ – Build Clinical Data
Groups images by original document:
```json
{
  "clinical_data": {
    "1": ["s3_key_1", "s3_key_2"],
    "2": ["s3_key_3", "s3_key_4"]
  }
}
```

### STEP 6️⃣ – Handle Additional Data
If TXT files are present, their content is concatenated and added.

### STEP 7️⃣ – Call Extract API
Sends data to extraction API:
```
POST https://pxyanaujf9.execute-api.ap-south-1.amazonaws.com/dev/extract
```

### STEP 8️⃣ – Poll Job Status
Polls status every 5 seconds until completion:
```
GET https://pxyanaujf9.execute-api.ap-south-1.amazonaws.com/dev/job-status?job_id=<job_id>
```

### STEP 9️⃣ – Update Supabase
Updates the case in Supabase database:
- Sets `summary` field with markdown content
- Sets `processing` to `false`
- Updates `updated_at` timestamp

### STEP 🔟 – Return Response
Returns `processing_started` status to frontend.
Frontend does NOT receive the summary directly.

## Architecture Flow

```
Frontend (React + Supabase)
   ↓
   1. Creates case in Supabase (summary=null, processing=true)
   ↓
   2. Sends files + case_id to Backend
   ↓
Backend (FastAPI)
   ↓
   3. Converts → Uploads → AI Processing
   ↓
   4. Updates Supabase with summary
   ↓
   5. Returns "processing_started"
   ↓
Frontend
   ↓
   6. Shows success message
   ↓
   7. User refreshes later to see summary
```

## Error Handling

The API handles errors gracefully:
- **No files uploaded**: Returns 400 error
- **Converter failure**: Returns error with details
- **Upload failure**: Returns error with failed files
- **API failure**: Returns error from external API
- **Job timeout**: Returns timeout error after max attempts

## Configuration

Key configuration values (in `app/services/ai_pipeline.py`):

```python
GET_UPLOAD_URLS_ENDPOINT = "https://pxyanaujf9.execute-api.ap-south-1.amazonaws.com/dev/get-upload-urls"
EXTRACT_ENDPOINT = "https://pxyanaujf9.execute-api.ap-south-1.amazonaws.com/dev/extract"
JOB_STATUS_ENDPOINT = "https://pxyanaujf9.execute-api.ap-south-1.amazonaws.com/dev/job-status"

POLL_INTERVAL = 5  # seconds
MAX_POLL_ATTEMPTS = 120  # 10 minutes max
REQUEST_TIMEOUT = 30  # seconds
```

## Temporary Storage

Uploaded files are stored in `/tmp/uploads/` during processing and cleaned up after completion.

Directory structure:
```
/tmp/uploads/
└── {request_id}/
    ├── raw/           # Original uploaded files
    └── converted/     # Generated JPEG images
```

## Logging

All operations are logged to console. Debug information includes:
- File upload details
- Conversion progress
- S3 upload status
- API call details
- Polling progress
- Errors and exceptions

## Important Notes

⚠️ **DO NOT MODIFY THE CONVERTER**
- The `converter/converter.py` is external and pre-built
- Always call it as-is from the routes
- Do not duplicate conversion logic elsewhere

✅ **REUSE EXISTING CONVERTER**
- Import `universal_to_jpeg` from `converter.converter`
- Pass file paths and output directory
- Trust the converter to handle all formats

## Future Extensions

This backend is designed to be easily extended:

- **Database Integration**: Add SQLAlchemy models for persisting results
- **Frontend**: Add a React/Vue frontend for UI
- **Supabase**: Integrate for user authentication and data storage
- **Webhooks**: Add callback support for async processing
- **Caching**: Cache S3 URLs and API responses

## Dependencies

- **fastapi**: Web framework
- **uvicorn**: ASGI server
- **requests**: HTTP client
- **pydantic**: Data validation
- **python-multipart**: Multipart form parsing
- **PyMuPDF**: PDF conversion (via converter)
- **Pillow**: Image processing (via converter)

## License

Internal project - All rights reserved.
