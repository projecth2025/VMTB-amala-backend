"""
Test script to send files from data/ folder to the FastAPI backend.
"""
import requests
from pathlib import Path

# Backend URL
API_URL = "http://127.0.0.1:8000/process-case"

# Data folder
DATA_FOLDER = Path("data")

def test_process_case():
    """Send all files from data/ folder to the backend"""
    
    # Get all files from data folder
    files_to_send = list(DATA_FOLDER.glob("*"))
    
    if not files_to_send:
        print("❌ No files found in data/ folder")
        return
    
    print(f"📁 Found {len(files_to_send)} file(s):")
    for f in files_to_send:
        print(f"   - {f.name}")
    
    # Prepare files for upload
    files = []
    for file_path in files_to_send:
        with open(file_path, "rb") as f:
            files.append(("files", (file_path.name, f, "application/octet-stream")))
    
    try:
        print("\n🚀 Sending request to backend...")
        
        # Open files and send
        with open(files_to_send[0], "rb") as f1:
            file_objects = []
            for file_path in files_to_send:
                file_objects.append(("files", open(file_path, "rb")))
            
            response = requests.post(API_URL, files=file_objects, timeout=300)
            
            # Close all files
            for _, f in file_objects:
                f.close()
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n✅ Success! Status: {result.get('status')}")
            
            if result.get('summary_markdown'):
                print("\n📄 Markdown Summary:\n")
                print(result.get('summary_markdown'))
            else:
                print(f"Response: {result}")
        else:
            print(f"\n❌ Error: {response.status_code}")
            print(response.text)
            
    except requests.exceptions.ConnectionError:
        print("❌ Connection Error: Backend not running")
        print("   Run: uvicorn app.main:app --reload")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    test_process_case()
