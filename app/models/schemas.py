"""
Pydantic schemas for request/response validation.
"""
from pydantic import BaseModel
from typing import Optional, Dict, List


class UploadURLRequest(BaseModel):
    """Request to get S3 upload URLs"""
    data: List[str]


class UploadURLResponse(BaseModel):
    """Response containing S3 upload URLs"""
    upload_urls: Dict[str, str]


class ExtractionRequest(BaseModel):
    """Request to extract information from documents"""
    clinical_data: Dict[str, List[str]]
    additional_data: Optional[str] = None


class ExtractionResponse(BaseModel):
    """Response from extraction API"""
    job_id: str
    status: str


class JobStatusResponse(BaseModel):
    """Response from job status check"""
    status: str
    result: Optional[Dict] = None


class ProcessCaseResponse(BaseModel):
    """Final response from /process-case endpoint"""
    status: str
    summary_markdown: Optional[str] = None


class ErrorResponse(BaseModel):
    """Error response format"""
    status: str
    message: str
