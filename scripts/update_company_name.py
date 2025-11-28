#!/usr/bin/env python3
"""
Script to update company name from "بان" (bany) to "لبنداري" (elbendary) in Word documents.
"""

from docx import Document
from pathlib import Path
import sys

def replace_text_in_paragraph(paragraph, old_text, new_text):
    """Replace text in a paragraph while preserving formatting."""
    if old_text not in paragraph.text:
        return
    
    # Get all runs and their text
    runs = paragraph.runs
    full_text = ''.join([run.text for run in runs])
    
    if old_text not in full_text:
        return
    
    # Build a list of (text, run_index) tuples
    run_texts = []
    for i, run in enumerate(runs):
        run_texts.append((run.text, i))
    
    # Find all occurrences of old_text across runs
    # For simplicity, we'll rebuild the paragraph preserving the first run's style
    paragraph.clear()
    
    # Split the full text and rebuild
    parts = full_text.split(old_text)
    
    # Add the first part with formatting from first run if available
    if parts[0]:
        run = paragraph.add_run(parts[0])
        if runs:
            # Copy formatting from first run
            first_run = runs[0]
            run.bold = first_run.bold
            run.italic = first_run.italic
            run.underline = first_run.underline
            if first_run.font.size:
                run.font.size = first_run.font.size
            if first_run.font.color.rgb:
                run.font.color.rgb = first_run.font.color.rgb
    
    # Add the new text and remaining parts
    for part in parts[1:]:
        # Add new text with formatting from first run
        new_run = paragraph.add_run(new_text)
        if runs:
            first_run = runs[0]
            new_run.bold = first_run.bold
            new_run.italic = first_run.italic
            new_run.underline = first_run.underline
            if first_run.font.size:
                new_run.font.size = first_run.font.size
            if first_run.font.color.rgb:
                new_run.font.color.rgb = first_run.font.color.rgb
        
        # Add remaining part
        if part:
            part_run = paragraph.add_run(part)
            if runs:
                first_run = runs[0]
                part_run.bold = first_run.bold
                part_run.italic = first_run.italic
                part_run.underline = first_run.underline
                if first_run.font.size:
                    part_run.font.size = first_run.font.size
                if first_run.font.color.rgb:
                    part_run.font.color.rgb = first_run.font.color.rgb

def replace_text_in_table(table, old_text, new_text):
    """Replace text in all cells of a table."""
    for row in table.rows:
        for cell in row.cells:
            for paragraph in cell.paragraphs:
                replace_text_in_paragraph(paragraph, old_text, new_text)

def update_company_name(docx_path, old_name_ar="بان", new_name_ar="لبنداري", 
                        old_name_en="Bany", new_name_en="Elbendary"):
    """
    Update company name in a Word document.
    
    Args:
        docx_path: Path to the Word document
        old_name_ar: Old Arabic company name (default: "بان")
        new_name_ar: New Arabic company name (default: "لبنداري")
        old_name_en: Old English company name (default: "Bany")
        new_name_en: New English company name (default: "Elbendary")
    """
    docx_path = Path(docx_path)
    
    if not docx_path.exists():
        raise FileNotFoundError(f"File not found: {docx_path}")
    
    print(f"Opening document: {docx_path}")
    doc = Document(docx_path)
    
    # Replace in paragraphs
    for paragraph in doc.paragraphs:
        replace_text_in_paragraph(paragraph, old_name_ar, new_name_ar)
        replace_text_in_paragraph(paragraph, old_name_en, new_name_en)
    
    # Replace in tables
    for table in doc.tables:
        replace_text_in_table(table, old_name_ar, new_name_ar)
        replace_text_in_table(table, old_name_en, new_name_en)
    
    # Save the document
    print(f"Saving updated document: {docx_path}")
    doc.save(docx_path)
    print("Update completed successfully!")

if __name__ == "__main__":
    # Path to the document
    doc_path = Path(__file__).parent.parent / "ai" / "rag" / "data" / "bany_developer_profile.docx"
    
    try:
        update_company_name(doc_path)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

