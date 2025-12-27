"""
utils.py

Utility functions for the CV education extraction pipeline.
Includes CSV writing, file handling, and validation helpers.
"""

import csv
import os
from pathlib import Path
from typing import List
from datetime import datetime


def ensure_directory(path: str | Path) -> Path:
    """
    Ensure a directory exists, creating it if necessary.

    Args:
        path: Directory path

    Returns:
        Path object for the directory
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_pdf_files(directory: str | Path) -> List[Path]:
    """
    Get all PDF files in a directory.

    Args:
        directory: Directory to search

    Returns:
        List of Path objects for PDF files, sorted alphabetically
    """
    directory = Path(directory)
    if not directory.exists():
        print(f"[WARN] Directory does not exist: {directory}")
        return []

    pdf_files = list(directory.glob("*.pdf"))
    # Sort for consistent ordering
    pdf_files.sort(key=lambda p: p.name)
    return pdf_files


def write_csv(records: list, output_path: str | Path) -> bool:
    """
    Write education records to a CSV file.

    Args:
        records: List of EducationRecord objects
        output_path: Path for output CSV

    Returns:
        True if successful, False otherwise
    """
    output_path = Path(output_path)

    # Ensure output directory exists
    ensure_directory(output_path.parent)

    # Define CSV columns
    fieldnames = [
        'name',
        'cv_filename',
        'undergrad_school',
        'masters_school',
        'phd_school',
        'notes'
    ]

    try:
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
            writer.writeheader()

            for record in records:
                row = {
                    'name': record.name,
                    'cv_filename': record.cv_filename,
                    'undergrad_school': record.undergrad_school,
                    'masters_school': record.masters_school,
                    'phd_school': record.phd_school,
                    'notes': record.notes_str()
                }
                writer.writerow(row)

        print(f"[INFO] CSV written to: {output_path}")
        return True

    except Exception as e:
        print(f"[ERROR] Failed to write CSV: {e}")
        return False


def sanitize_text_for_csv(text: str) -> str:
    """
    Clean text for safe CSV inclusion.

    Args:
        text: Raw text

    Returns:
        Sanitized text
    """
    if not text:
        return ""

    # Remove newlines (replace with space)
    text = text.replace('\n', ' ').replace('\r', ' ')

    # Remove tabs
    text = text.replace('\t', ' ')

    # Collapse multiple spaces
    import re
    text = re.sub(r' {2,}', ' ', text)

    return text.strip()


def print_summary(records: list) -> None:
    """
    Print a summary of extraction results.

    Args:
        records: List of EducationRecord objects
    """
    total = len(records)
    if total == 0:
        print("\n[SUMMARY] No records processed")
        return

    # Count extraction success rates
    has_name = sum(1 for r in records if r.name)
    has_phd = sum(1 for r in records if r.phd_school)
    has_masters = sum(1 for r in records if r.masters_school)
    has_undergrad = sum(1 for r in records if r.undergrad_school)
    has_any_school = sum(1 for r in records if r.phd_school or r.masters_school or r.undergrad_school)
    has_notes = sum(1 for r in records if r.notes)

    print("\n" + "=" * 60)
    print("EXTRACTION SUMMARY")
    print("=" * 60)
    print(f"Total CVs processed:      {total}")
    print(f"Names extracted:          {has_name}/{total} ({100*has_name/total:.1f}%)")
    print(f"PhD schools found:        {has_phd}/{total} ({100*has_phd/total:.1f}%)")
    print(f"Master's schools found:   {has_masters}/{total} ({100*has_masters/total:.1f}%)")
    print(f"Undergrad schools found:  {has_undergrad}/{total} ({100*has_undergrad/total:.1f}%)")
    print(f"At least one school:      {has_any_school}/{total} ({100*has_any_school/total:.1f}%)")
    print(f"Records with notes:       {has_notes}/{total} ({100*has_notes/total:.1f}%)")
    print("=" * 60)

    # Print records that might need manual review
    needs_review = [r for r in records if not r.phd_school and not r.masters_school and not r.undergrad_school]
    if needs_review:
        print("\n[ATTENTION] CVs with no schools extracted (may need manual review):")
        for r in needs_review:
            print(f"  - {r.cv_filename}")


def log_progress(current: int, total: int, filename: str) -> None:
    """
    Log processing progress.

    Args:
        current: Current item number (1-indexed)
        total: Total number of items
        filename: Name of current file being processed
    """
    pct = 100 * current / total if total > 0 else 0
    print(f"[{current}/{total}] ({pct:.0f}%) Processing: {filename}")


def create_debug_output(record, edu_section: str, output_dir: str | Path) -> None:
    """
    Create debug output for a single record (for troubleshooting).

    Args:
        record: EducationRecord object
        edu_section: Extracted education section text
        output_dir: Directory for debug output
    """
    output_dir = Path(output_dir)
    ensure_directory(output_dir)

    debug_file = output_dir / f"{record.cv_filename}_debug.txt"

    with open(debug_file, 'w', encoding='utf-8') as f:
        f.write(f"CV Filename: {record.cv_filename}\n")
        f.write(f"Extracted Name: {record.name}\n")
        f.write("-" * 40 + "\n")
        f.write(f"Undergrad: {record.undergrad_school}\n")
        f.write(f"Master's: {record.masters_school}\n")
        f.write(f"PhD: {record.phd_school}\n")
        f.write("-" * 40 + "\n")
        f.write(f"Notes: {record.notes_str()}\n")
        f.write("=" * 40 + "\n")
        f.write("EDUCATION SECTION TEXT:\n")
        f.write("=" * 40 + "\n")
        f.write(edu_section if edu_section else "(not found)")


def validate_record(record) -> List[str]:
    """
    Validate an education record for common issues.

    Args:
        record: EducationRecord object

    Returns:
        List of validation warnings
    """
    warnings = []

    # Check for suspiciously short institution names
    for field_name, value in [
        ('undergrad_school', record.undergrad_school),
        ('masters_school', record.masters_school),
        ('phd_school', record.phd_school)
    ]:
        if value and len(value) < 5:
            warnings.append(f"{field_name} seems too short: '{value}'")

    # Check for duplicate institutions (unusual but possible)
    institutions = [record.undergrad_school, record.masters_school, record.phd_school]
    institutions = [i for i in institutions if i]  # Remove empty
    if len(institutions) != len(set(institutions)):
        warnings.append("Same institution appears for multiple degrees")

    return warnings
