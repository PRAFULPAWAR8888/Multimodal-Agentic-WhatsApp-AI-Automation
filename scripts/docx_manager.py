import argparse
from pathlib import Path
from docx import Document

def read_docx(filepath: str) -> str:
    """Reads all text paragraphs from a .docx file."""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {filepath}")
    
    doc = Document(filepath)
    text = []
    for paragraph in doc.paragraphs:
        if paragraph.text.strip():
            text.append(paragraph.text)
            
    # Also attempt to read from tables
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                if cell.text.strip():
                    text.append(cell.text)
                    
    return "\n".join(text)

def write_docx(filepath: str, text: str, overwrite: bool = False):
    """Writes text to a .docx file. Appends by default, or overwrites if specified."""
    path = Path(filepath)
    if path.exists() and not overwrite:
        doc = Document(filepath)
    else:
        doc = Document()
        
    for line in text.split("\n"):
        doc.add_paragraph(line)
        
    doc.save(filepath)
    print(f"Successfully saved to {filepath}")

def replace_text_in_docx(filepath: str, target: str, replacement: str, save_path: str = None):
    """Replaces a specific target string with a replacement string in a .docx file."""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {filepath}")
        
    save_path = save_path or filepath
    doc = Document(filepath)
    
    replacements_made = 0
    # Search and replace in paragraphs
    for paragraph in doc.paragraphs:
        if target in paragraph.text:
            paragraph.text = paragraph.text.replace(target, replacement)
            replacements_made += 1
            
    # Search and replace in tables
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                if target in cell.text:
                    cell.text = cell.text.replace(target, replacement)
                    replacements_made += 1
                    
    doc.save(save_path)
    print(f"Replaced {replacements_made} instances of '{target}'. Saved to {save_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Read, write, and update .docx files.")
    subparsers = parser.add_subparsers(dest="action", required=True)
    
    # Read command
    read_parser = subparsers.add_parser("read", help="Read text from a docx file")
    read_parser.add_argument("filepath", help="Path to the .docx file")
    
    # Write command
    write_parser = subparsers.add_parser("write", help="Write or append text to a docx file")
    write_parser.add_argument("filepath", help="Path to the .docx file")
    write_parser.add_argument("text", help="Text to write")
    write_parser.add_argument("--overwrite", action="store_true", help="Overwrite existing file instead of appending")
    
    # Replace command
    replace_parser = subparsers.add_parser("replace", help="Replace text in a docx file")
    replace_parser.add_argument("filepath", help="Path to the .docx file")
    replace_parser.add_argument("target", help="Text to search for")
    replace_parser.add_argument("replacement", help="Text to replace with")
    replace_parser.add_argument("--save-path", help="Optional path to save the modified file (defaults to overwriting)")
    
    args = parser.parse_args()
    
    if args.action == "read":
        try:
            content = read_docx(args.filepath)
            print("--- DOCX CONTENT ---")
            print(content)
            print("--------------------")
        except Exception as e:
            print(f"Error reading docx: {e}")
            
    elif args.action == "write":
        try:
            write_docx(args.filepath, args.text, args.overwrite)
        except Exception as e:
            print(f"Error writing docx: {e}")
            
    elif args.action == "replace":
        try:
            replace_text_in_docx(args.filepath, args.target, args.replacement, args.save_path)
        except Exception as e:
            print(f"Error updating docx: {e}")
