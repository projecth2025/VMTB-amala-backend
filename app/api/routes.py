"""
API routes for medical document processing.
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from typing import List, Optional
import logging
import sys
from pathlib import Path

# Add parent directory to path to import converter
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from converter.converter import universal_to_jpeg

from app.utils.temp_storage import TempStorage
from app.services.uploader import S3Uploader
from app.services.ai_pipeline import AIPipeline
from app.services.supabase_service import SupabaseService
from app.models.schemas import ProcessCaseResponse, ErrorResponse

logger = logging.getLogger(__name__)

router = APIRouter()
temp_storage = TempStorage()

# Path to store converted images
IMAGES_OUTPUT_DIR = Path(__file__).parent.parent.parent / "converter" / "images"
IMAGES_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def separate_files(raw_files: List[Path]) -> tuple[List[Path], List[Path]]:
    """
    Separate document files from text files.
    
    Args:
        raw_files: List of all uploaded files
        
    Returns:
        Tuple of (document_files, txt_files)
    """
    document_extensions = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tiff", ".xps", ".epub"}
    txt_extensions = {".txt"}
    
    documents = []
    text_files = []
    
    for file_path in raw_files:
        ext = file_path.suffix.lower()
        if ext in txt_extensions:
            text_files.append(file_path)
        elif ext in document_extensions:
            documents.append(file_path)
        else:
            # Try to treat as document
            documents.append(file_path)
    
    return documents, text_files


def build_s3_keys_by_document(image_paths: List[Path], original_documents: List[Path]) -> tuple[dict, dict]:
    """
    Group S3 keys by original document and track image-to-document mapping.
    
    The converter outputs images in order. We need to figure out which images
    came from which document.
    
    Args:
        image_paths: List of converted JPEG image paths (ordered)
        original_documents: List of original document file paths
        
    Returns:
        Tuple of (s3_keys_by_doc_dict, image_filenames_dict)
        where s3_keys_by_doc_dict[0] = ["img1", "img2"] for first doc
    """
    s3_keys_by_doc = {}
    image_filenames = []
    
    # For now, simple approach: assign images to documents in order
    # This is a simplification; in production you'd track this during conversion
    images_per_doc = len(image_paths) // len(original_documents) if original_documents else 0
    
    if not original_documents:
        # No documents, shouldn't happen but handle gracefully
        for img_path in image_paths:
            image_filenames.append(img_path.name)
        return s3_keys_by_doc, image_filenames
    
    if images_per_doc == 0:
        # More documents than images (unlikely but possible)
        images_per_doc = 1
    
    img_idx = 0
    for doc_idx, doc_path in enumerate(original_documents):
        s3_keys_by_doc[doc_idx] = []
        
        # Assign images to this document
        for _ in range(images_per_doc):
            if img_idx < len(image_paths):
                img_path = image_paths[img_idx]
                # Extract S3 key from filename
                s3_key = img_path.stem  # Remove .jpeg extension
                s3_keys_by_doc[doc_idx].append(s3_key)
                image_filenames.append(img_path.name)
                img_idx += 1
        
        # Handle last document getting remaining images
        if doc_idx == len(original_documents) - 1:
            while img_idx < len(image_paths):
                img_path = image_paths[img_idx]
                s3_key = img_path.stem
                s3_keys_by_doc[doc_idx].append(s3_key)
                image_filenames.append(img_path.name)
                img_idx += 1
    
    return s3_keys_by_doc, image_filenames


@router.post("/process-case", response_model=ProcessCaseResponse, tags=["Processing"])
async def process_case(
    files: List[UploadFile] = File(...),
    case_id: str = Form(...),
    user_id: str = Form(...),
    additional_data: Optional[str] = Form(None)
) -> dict:
    """
    Process medical case documents and update summary in Supabase.
    
    Accepts PDFs, images, and optional TXT files.
    Converts documents to JPEGs, uploads to S3, calls AI APIs, and updates Supabase.
    
    UPDATED FLOW:
    1. Save uploaded files temporarily
    2. Convert documents using existing converter
    3. Get S3 upload URLs
    4. Upload images to S3
    5. Build clinical_data structure
    6. Handle additional data (doctor-written notes sent separately)
    7. Call extract API
    8. Poll job status until completion
    9. Update Supabase with summary
    10. Return processing_started status
    
    Args:
        files: Multiple uploaded files (PDFs, images, text files)
        case_id: UUID of the case in Supabase
        user_id: UUID of the user (for logging/validation)
        additional_data: Doctor-written text notes (sent directly to AI, not converted)
        
    Returns:
        ProcessCaseResponse with status "processing_started"
    """
    request_id = None
    
    try:
        # STEP 1️⃣: Validate and save uploaded files
        if not files:
            raise HTTPException(status_code=400, detail="No files uploaded")
        
        logger.info(f"Received {len(files)} files for processing")
        
        # Create request directory
        request_id = temp_storage.create_request_directory()
        logger.info(f"Created request directory: {request_id}")
        
        # Save all files
        saved_files = []
        for file in files:
            if not file.filename:
                continue
            
            content = await file.read()
            file_path = temp_storage.save_uploaded_file(request_id, content, file.filename)
            saved_files.append(file_path)
            logger.info(f"Saved file: {file.filename}")
        
        if not saved_files:
            raise Exception("No valid files were saved")
        
        # Separate documents from text files
        raw_files = temp_storage.get_raw_files(request_id)
        document_files, text_files = separate_files(raw_files)
        
        if not document_files:
            raise Exception("No document files found (PDF or image files required)")
        
        print(f"\n{'='*60}")
        print("📋 FILES SEPARATION")
        print(f"{'='*60}")
        print(f"Total Files: {len(raw_files)}")
        print(f"Documents: {len(document_files)}")
        for doc in document_files:
            print(f"   - {doc.name}")
        print(f"Text Files: {len(text_files)}")
        for txt in text_files:
            print(f"   - {txt.name}")
        print(f"{'='*60}\n")
        
        logger.info(f"Found {len(document_files)} document(s) and {len(text_files)} text file(s)")
        
        # STEP 2️⃣: Convert documents using existing converter
        # Store images in converter/images folder
        print(f"\n{'='*60}")
        print("🔄 CONVERTING DOCUMENTS TO JPEG")
        print(f"{'='*60}")
        print(f"Output Directory: {IMAGES_OUTPUT_DIR}")
        
        for doc_path in document_files:
            print(f"\n📄 Converting: {doc_path.name}")
            logger.info(f"Converting document: {doc_path.name}")
            universal_to_jpeg(str(doc_path), str(IMAGES_OUTPUT_DIR), dpi=300)
        
        # Get converted JPEG images from the output directory (ordered)
        image_paths = sorted(IMAGES_OUTPUT_DIR.glob("*.jpeg"))
        
        if not image_paths:
            raise Exception("No JPEG images were generated from documents")
        
        print(f"\n✅ Generated {len(image_paths)} JPEG image(s)")
        print(f"{'='*60}\n")
        
        for img in image_paths:
            print(f"   - {img.name}")
        
        logger.info(f"Generated {len(image_paths)} JPEG image(s)")
        
        # Rename images to match API expected format (i1.jpeg, i2.jpeg, etc.)
        print(f"\n📝 Renaming images to standard format...")
        renamed_paths = []
        for idx, img_path in enumerate(image_paths, start=1):
            new_name = f"i{idx}.jpeg"
            new_path = img_path.parent / new_name
            img_path.rename(new_path)
            renamed_paths.append(new_path)
            print(f"   {img_path.name} → {new_name}")
        
        image_paths = renamed_paths
        
        # STEP 3️⃣: Get S3 upload URLs
        image_filenames = [img.name for img in image_paths]
        upload_urls, s3_keys = S3Uploader.get_upload_urls(
            image_filenames,
            AIPipeline.GET_UPLOAD_URLS_ENDPOINT
        )
        logger.info(f"Got {len(upload_urls)} upload URL(s)")
        
        # STEP 4️⃣: Upload images to S3
        print(f"\n{'='*60}")
        print("⬆️ UPLOADING IMAGES TO S3")
        print(f"{'='*60}\n")
        
        s3_keys_mapping = S3Uploader.upload_all_images(image_paths, upload_urls, s3_keys)
        
        print(f"\n✅ S3 UPLOAD COMPLETE")
        print(f"Total Uploaded: {len(s3_keys_mapping)}")
        print(f"{'='*60}\n")
        
        logger.info(f"Successfully uploaded {len(s3_keys_mapping)} image(s) to S3")
        
        # STEP 5️⃣: Build clinical_data structure
        # Group S3 keys by original document
        # s3_keys_mapping is {filename: s3_key} from API response
        # We need to group them by document order
        
        clinical_data_dict = {}
        doc_count = 1
        current_doc_group = []
        
        # Sort filenames to maintain order
        sorted_filenames = sorted(s3_keys_mapping.keys())
        
        for filename in sorted_filenames:
            s3_key = s3_keys_mapping[filename]
            current_doc_group.append(s3_key)
            
            # Check if this is the last file of a document
            # For simplicity, group by original document from image_paths
            # This needs to track which images came from which document
        
        # Better approach: use the original document grouping
        # Build mapping from original documents to their images
        clinical_data = {}
        img_idx = 0
        
        for doc_idx, doc_path in enumerate(document_files):
            doc_key = str(doc_idx + 1)
            clinical_data[doc_key] = []
            
            # Find how many images belong to this document
            # by checking the original naming from conversion
            # For now, collect all images in order
            for filename in sorted_filenames:
                s3_key = s3_keys_mapping[filename]
                clinical_data[doc_key].append(s3_key)
        
        # Simpler approach: since we renamed all files to i1.jpeg, i2.jpeg, etc.
        # and API response contains s3_key which is the actual S3 path,
        # just group sequentially
        clinical_data = {"1": []}
        for filename in sorted_filenames:
            s3_key = s3_keys_mapping[filename]
            clinical_data["1"].append(s3_key)
        
        print(f"\n{'='*60}")
        print("📊 CLINICAL DATA STRUCTURE")
        print(f"{'='*60}")
        print(f"Documents: {len(clinical_data)}")
        for doc_key, keys in clinical_data.items():
            print(f"   Document {doc_key}: {len(keys)} image(s)")
            for key in keys:
                print(f"      - {key}")
        print(f"{'='*60}\n")
        
        logger.info(f"Built clinical_data with {len(clinical_data)} document group(s)")
        
        # STEP 6️⃣: Handle additional data (doctor-written notes)
        # This data is sent directly from frontend, NOT from text files
        # Text files are processed as documents, not as additional_data
        final_additional_data = None
        
        # Use additional_data parameter from form if provided
        if additional_data:
            final_additional_data = additional_data
            logger.info(f"Using additional_data from form: {len(additional_data)} characters")
            print(f"\n📝 ADDITIONAL DATA RECEIVED")
            print(f"{'='*60}")
            print(f"Length: {len(additional_data)} characters")
            print(f"Content preview: {additional_data[:100]}...")
            print(f"{'='*60}\n")
        
        # Also read any text files that were uploaded
        if text_files:
            text_contents = []
            for txt_file in text_files:
                try:
                    with open(txt_file, "r", encoding="utf-8") as f:
                        content = f.read()
                        text_contents.append(content)
                    logger.info(f"Read text file: {txt_file.name}")
                except Exception as e:
                    logger.warning(f"Failed to read {txt_file.name}: {e}")
            
            if text_contents:
                text_data = "\n\n".join(text_contents)
                # Combine with form additional_data if both exist
                if final_additional_data:
                    final_additional_data = final_additional_data + "\n\n" + text_data
                else:
                    final_additional_data = text_data
                logger.info(f"Combined {len(text_contents)} text file(s)")
        
        # STEP 7️⃣: Call extract API
        job_id = AIPipeline.call_extract_api(clinical_data, final_additional_data)
        logger.info(f"Extraction started with job_id: {job_id}")
        
        # STEP 8️⃣: Poll job status until completion
        print(f"\n{'='*60}")
        print("🔍 POLLING FOR EXTRACTION RESULTS")
        print(f"{'='*60}\n")
        
        try:
            final_summary = AIPipeline.poll_job_status(job_id)
            logger.info("Extraction completed successfully")
        except TimeoutError as timeout_err:
            # AI model did not return response after 120 attempts
            logger.error(f"AI processing timed out for case {case_id}: {timeout_err}")
            print(f"\n{'='*60}")
            print("❌ AI PROCESSING TIMEOUT")
            print(f"{'='*60}")
            print(f"Job ID: {job_id}")
            print(f"Case ID: {case_id}")
            print(f"Status: Failed after 120 attempts")
            print(f"{'='*60}\n")
            
            # Update Supabase with failure status
            SupabaseService.update_case_failed(case_id)
            
            return {
                "status": "error",
                "message": "Case creation failed - AI processing timed out after 120 attempts"
            }
        
        print(f"\n{'='*60}")
        print("✅ EXTRACTION COMPLETE")
        print(f"{'='*60}")
        print(f"Job ID: {job_id}")
        print(f"Status: Success")
        print(f"Case ID: {case_id}")
        print(f"{'='*60}\n")
        
        # STEP 9️⃣: Update Supabase with summary
        print(f"\n{'='*60}")
        print("💾 UPDATING SUPABASE")
        print(f"{'='*60}")
        print(f"Case ID: {case_id}")
        print(f"Summary length: {len(final_summary)} characters")
        
        success = SupabaseService.update_case_summary(case_id, final_summary)
        
        if success:
            print(f"✅ Successfully updated Supabase")
            logger.info(f"Successfully updated Supabase for case {case_id}")
        else:
            print(f"❌ Failed to update Supabase")
            logger.error(f"Failed to update Supabase for case {case_id}")
        
        print(f"{'='*60}\n")
        
        # STEP 🔟: Return processing_started response
        response = {
            "status": "processing_started",
            "summary_markdown": None
        }
        
        print(f"\n{'='*60}")
        print("📤 RESPONSE")
        print(f"{'='*60}")
        print(f"Status: processing_started")
        print(f"Summary saved to Supabase: {success}")
        print(f"{'='*60}\n")
        
        logger.info(f"Process completed successfully for request {request_id}, case {case_id}")
        return response
        
    except Exception as e:
        logger.error(f"Error processing case: {str(e)}")
        return {
            "status": "error",
            "message": str(e)
        }
    
    finally:
        # Cleanup temporary files
        if request_id:
            temp_storage.cleanup_request(request_id)
            logger.info(f"Cleaned up temporary files for request {request_id}")
        
        # Cleanup converted JPEG images
        try:
            for img_file in IMAGES_OUTPUT_DIR.glob("*.jpeg"):
                img_file.unlink()
            logger.info("Cleaned up converted JPEG images")
        except Exception as e:
            logger.warning(f"Failed to cleanup JPEG images: {e}")
