import csv
import sys
from pathlib import Path

def txt_to_csv(input_file, output_file, delimiter=','):
    """Convert a text file to CSV."""
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    with open(str(output_file), 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Line Number', 'Content'])
        for i, line in enumerate(lines, 1):
            writer.writerow([i, line.strip()])
    
    print(f"✓ Converted {input_file} to {output_file}")

def pdf_to_csv(input_file, output_file):
    """Convert a PDF file to CSV."""
    try:
        import PyPDF2
    except ImportError:
        print("Error: PyPDF2 is required. Install it with: pip install PyPDF2")
        return
    
    with open(input_file, 'rb') as f:
        pdf = PyPDF2.PdfReader(f)
        
        with open(str(output_file), 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Page', 'Content'])
            
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text()
                writer.writerow([page_num, text.strip()])
    
    print(f"✓ Converted {input_file} to {output_file}")

def docx_to_csv(input_file, output_file):
    """Convert a DOCX file to CSV."""
    try:
        from docx import Document
    except ImportError:
        print("Error: python-docx is required. Install it with: pip install python-docx")
        return
    
    doc = Document(input_file)
    
    with open(str(output_file), 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Paragraph Number', 'Content'])
        
        for i, para in enumerate(doc.paragraphs, 1):
            if para.text.strip():
                writer.writerow([i, para.text.strip()])
    
    print(f"✓ Converted {input_file} to {output_file}")

def document_to_csv(input_file, output_file=None):
    """
    Convert a document (TXT, PDF, DOCX) to CSV format.
    
    Args:
        input_file: Path to the input document
        output_file: Path to the output CSV (optional, auto-generated if not provided)
    """
    input_path = Path(input_file)
    
    if not input_path.exists():
        print(f"Error: File '{input_file}' not found.")
        return
    
    # Generate output filename in the same folder as input file
    output_path = input_path.parent / (input_path.stem + '.csv')
    
    # Determine file type and convert
    ext = input_path.suffix.lower()
    
    if ext == '.txt':
        txt_to_csv(input_file, output_path)
    elif ext == '.pdf':
        pdf_to_csv(input_file, output_path)
    elif ext == '.docx':
        docx_to_csv(input_file, output_path)
    else:
        print(f"Error: Unsupported file format '{ext}'")
        print("Supported formats: .txt, .pdf, .docx")
        return
    
    print(f"CSV file created: {output_path}")

if __name__ == "__main__":
    # Developer: Enter your file name here
    input_file = " "  # Change this to your document path
    
    document_to_csv(input_file)
