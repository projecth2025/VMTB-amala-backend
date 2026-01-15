import fitz  # PyMuPDF
from pathlib import Path
from PIL import Image
import io
import os

def convert_image_to_jpeg(input_path, output_folder):
    """Convert image files (PNG, BMP, GIF, TIFF, WEBP, etc.) to JPEG"""
    try:
        img = Image.open(input_path)
        
        # Convert RGBA to RGB if needed
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        output_path = output_folder / f"{input_path.stem}.jpeg"
        img.save(output_path, "JPEG", quality=95)
        print(f"Saved: {output_path.name}")
        return True
    except Exception as e:
        print(f"Error converting image: {e}")
        return False

def convert_pdf_to_jpeg(input_path, output_folder, dpi=300):
    """Convert PDF pages to JPEG images"""
    try:
        pdf_doc = fitz.open(input_path)
        print(f"Converting {len(pdf_doc)} pages from PDF...")
        
        for page_num in range(len(pdf_doc)):
            page = pdf_doc[page_num]
            zoom = dpi / 72
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            
            output_filename = f"{input_path.stem}_page_{page_num + 1}.jpeg"
            output_path = output_folder / output_filename
            pix.save(output_path, "jpeg")
            print(f"Saved: {output_filename}")
        
        total_pages = len(pdf_doc)
        pdf_doc.close()
        return True
    except Exception as e:
        print(f"Error converting PDF: {e}")
        return False

def convert_document_to_jpeg(input_path, output_folder, dpi=300):
    """Convert document files (DOCX, DOC, PPT, PPTX, XLS, XLSX) to JPEG using PyMuPDF"""
    try:
        # PyMuPDF can open many document formats directly
        doc = fitz.open(input_path)
        print(f"Converting {len(doc)} pages from document...")
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            zoom = dpi / 72
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            
            output_filename = f"{input_path.stem}_page_{page_num + 1}.jpeg"
            output_path = output_folder / output_filename
            pix.save(output_path, "jpeg")
            print(f"Saved: {output_filename}")
        
        total_pages = len(doc)
        doc.close()
        return True
    except Exception as e:
        print(f"Error converting document: {e}")
        return False

def convert_svg_to_jpeg(input_path, output_folder):
    """Convert SVG to JPEG"""
    try:
        from cairosvg import svg2png
        
        # Convert SVG to PNG first, then to JPEG
        png_data = svg2png(url=str(input_path))
        img = Image.open(io.BytesIO(png_data))
        
        if img.mode in ('RGBA', 'LA'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[-1])
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        output_path = output_folder / f"{input_path.stem}.jpeg"
        img.save(output_path, "JPEG", quality=95)
        print(f"Saved: {output_path.name}")
        return True
    except ImportError:
        print("SVG conversion requires cairosvg. Install with: pip install cairosvg")
        return False
    except Exception as e:
        print(f"Error converting SVG: {e}")
        return False

def universal_to_jpeg(input_path, output_folder=None, dpi=300):
    """
    Convert any file format to JPEG.
    
    Args:
        input_path: Path to the input file
        output_folder: Folder to save JPEG images (default: same as input location)
        dpi: Resolution for document conversions (default: 300)
    """
    input_path = Path(input_path)
    
    if not input_path.exists():
        print(f"Error: File not found at {input_path}")
        return
    
    # Set output folder
    if output_folder is None:
        output_folder = input_path.parent / "jpeg_output"
    else:
        output_folder = Path(output_folder)
    
    output_folder.mkdir(parents=True, exist_ok=True)
    
    # Get file extension
    ext = input_path.suffix.lower()
    
    print(f"\nProcessing: {input_path.name}")
    print(f"Output folder: {output_folder}\n")
    
    # Image formats
    image_formats = {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.tif', 
                    '.webp', '.ico', '.ppm', '.pgm', '.pbm', '.pnm', '.dib'}
    
    # Document formats that PyMuPDF can handle
    document_formats = {'.pdf', '.xps', '.epub', '.mobi', '.fb2', '.cbz', 
                       '.svg', '.txt'}
    
    # Microsoft Office formats (PyMuPDF 1.19+ can handle these)
    office_formats = {'.docx', '.doc', '.pptx', '.ppt', '.xlsx', '.xls'}
    
    success = False
    
    if ext in image_formats:
        success = convert_image_to_jpeg(input_path, output_folder)
    
    elif ext == '.pdf':
        success = convert_pdf_to_jpeg(input_path, output_folder, dpi)
    
    elif ext in document_formats or ext in office_formats:
        success = convert_document_to_jpeg(input_path, output_folder, dpi)
    
    elif ext == '.svg':
        success = convert_svg_to_jpeg(input_path, output_folder)
    
    else:
        # Try as image first
        print(f"Unknown format '{ext}', trying as image...")
        success = convert_image_to_jpeg(input_path, output_folder)
        
        if not success:
            # Try as document
            print(f"Trying as document...")
            success = convert_document_to_jpeg(input_path, output_folder, dpi)
    
    if success:
        print(f"\n✓ Conversion complete! Check {output_folder}")
    else:
        print(f"\n✗ Failed to convert {input_path.name}")
        print(f"If this is a specialized format, you may need additional libraries.")

if __name__ == "__main__":
    # Example usage
    input_file = "d.png"  # Can be PDF, PNG, DOCX, etc.
    output_dir = "jpeg_output"     # Optional: specify output folder
    
    universal_to_jpeg(input_file, output_folder=output_dir, dpi=300)