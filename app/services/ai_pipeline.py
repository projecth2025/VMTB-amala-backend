"""
AI Pipeline orchestrator for processing medical documents through external APIs.
Handles the complete workflow: extraction, job polling, and result retrieval.
"""
import requests
import time
from typing import Dict, List, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class AIPipeline:
    """Orchestrates API calls for document processing"""

    # API Endpoints
    GET_UPLOAD_URLS_ENDPOINT = "https://pxyanaujf9.execute-api.ap-south-1.amazonaws.com/dev/get-upload-urls"
    EXTRACT_ENDPOINT = "https://pxyanaujf9.execute-api.ap-south-1.amazonaws.com/dev/extract"
    JOB_STATUS_ENDPOINT = "https://pxyanaujf9.execute-api.ap-south-1.amazonaws.com/dev/job-status"

    # Configuration
    POLL_INTERVAL = 5  # seconds
    MAX_POLL_ATTEMPTS = 120  # 10 minutes max wait time
    REQUEST_TIMEOUT = 30  # seconds

    def __init__(self):
        """Initialize the AI pipeline"""
        pass

    @staticmethod
    def call_extract_api(clinical_data: Dict[str, List[str]], 
                         additional_data: Optional[str] = None) -> str:
        """
        Call the extract API to start processing.
        
        STEP 7️⃣: Call Extract API
        
        Args:
            clinical_data: Grouped images by document
            additional_data: Optional text content
            
        Returns:
            job_id: ID for polling status
            
        Raises:
            Exception: If API call fails
        """
        payload = {"clinical_data": clinical_data}
        
        if additional_data:
            payload["additional_data"] = additional_data
        
        try:
            print(f"\n{'='*60}")
            print("📤 CALLING EXTRACT API")
            print(f"{'='*60}")
            print(f"Endpoint: {AIPipeline.EXTRACT_ENDPOINT}")
            print(f"Payload: {payload}")
            
            logger.info("Calling extract API...")
            response = requests.post(
                AIPipeline.EXTRACT_ENDPOINT,
                json=payload,
                timeout=AIPipeline.REQUEST_TIMEOUT
            )
            response.raise_for_status()
            
            data = response.json()
            print(f"\n📥 EXTRACT API RESPONSE")
            print(f"Status Code: {response.status_code}")
            print(f"Response: {data}")
            print(f"{'='*60}\n")
            
            job_id = data.get("job_id")
            status = data.get("status")
            
            if not job_id:
                raise Exception("No job_id returned from extract API")
            
            logger.info(f"Extract API returned job_id: {job_id}, status: {status}")
            return job_id
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Extract API call failed: {e}")
            raise Exception(f"Failed to call extract API: {str(e)}")

    @staticmethod
    def poll_job_status(job_id: str) -> str:
        """
        Poll the job status API until completion.
        
        STEP 8️⃣: Poll Job Status
        
        Args:
            job_id: The job ID to poll
            
        Returns:
            final_summary: The markdown summary
            
        Raises:
            Exception: If polling times out or API fails
        """
        attempt = 0
        
        while attempt < AIPipeline.MAX_POLL_ATTEMPTS:
            try:
                params = {"job_id": job_id}
                print(f"\n⏳ POLLING JOB STATUS (Attempt {attempt + 1}/{AIPipeline.MAX_POLL_ATTEMPTS})")
                print(f"Endpoint: {AIPipeline.JOB_STATUS_ENDPOINT}")
                print(f"Job ID: {job_id}")
                
                logger.info(f"Polling job status (attempt {attempt + 1}/{AIPipeline.MAX_POLL_ATTEMPTS})...")
                
                response = requests.get(
                    AIPipeline.JOB_STATUS_ENDPOINT,
                    params=params,
                    timeout=AIPipeline.REQUEST_TIMEOUT
                )
                response.raise_for_status()
                
                data = response.json()
                status = data.get("status")
                
                print(f"📥 JOB STATUS RESPONSE")
                print(f"Status Code: {response.status_code}")
                print(f"Job Status: {status}")
                print(f"Full Response: {data}")
                
                logger.info(f"Job status: {status}")
                
                if status == "completed":
                    result = data.get("result", {})
                    final_summary = result.get("final_summary")
                    
                    if not final_summary:
                        raise Exception("No final_summary in completed result")
                    
                    logger.info("Job completed successfully")
                    return final_summary
                
                elif status == "failed":
                    error_message = data.get("error", "Unknown error")
                    raise Exception(f"Job failed: {error_message}")
                
                # Status is 'processing', wait and retry
                time.sleep(AIPipeline.POLL_INTERVAL)
                attempt += 1
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Job status API call failed: {e}")
                raise Exception(f"Failed to poll job status: {str(e)}")
        
        # Polling timed out after MAX_POLL_ATTEMPTS (120 attempts)
        logger.error(f"Job polling timed out after {AIPipeline.MAX_POLL_ATTEMPTS} attempts ({AIPipeline.MAX_POLL_ATTEMPTS * AIPipeline.POLL_INTERVAL} seconds)")
        raise TimeoutError(f"Job polling timed out after {AIPipeline.MAX_POLL_ATTEMPTS} attempts")

    @staticmethod
    def build_clinical_data_from_s3_keys(s3_keys_by_doc: Dict[int, List[str]]) -> Dict[str, List[str]]:
        """
        Build the clinical_data structure for the extract API.
        
        STEP 5️⃣: Build clinical_data
        
        Args:
            s3_keys_by_doc: Dictionary mapping doc index to list of S3 keys
                           e.g., {0: ["key1", "key2"], 1: ["key3", "key4"]}
            
        Returns:
            Dictionary with string keys ("1", "2", etc.) and S3 key lists as values
        """
        clinical_data = {}
        
        for doc_index, s3_keys in s3_keys_by_doc.items():
            # Convert to 1-based indexing for API
            key = str(doc_index + 1)
            clinical_data[key] = s3_keys
        
        logger.info(f"Built clinical_data with {len(clinical_data)} documents")
        return clinical_data
