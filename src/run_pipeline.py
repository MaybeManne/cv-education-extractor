#!/usr/bin/env python3
"""
run_pipeline.py

Main entry point for the CV education extraction pipeline.

Usage:
    python3 src/run_pipeline.py

This script:
1. Reads all PDF files from data/raw_cvs/
2. Extracts text using pdfplumber
3. Parses education sections using rule-based regex
4. Outputs results to data/output/education.csv

All processing is done locally - no APIs or external services.
"""

import sys
from pathlib import Path

# Add src to path for imports (in case running from project root)
SRC_DIR = Path(__file__).parent
PROJECT_ROOT = SRC_DIR.parent
sys.path.insert(0, str(SRC_DIR))

from extract_text import extract_text_from_pdf
from parse_education import parse_education, find_education_section
from utils import (
    get_pdf_files,
    write_csv,
    print_summary,
    log_progress,
    ensure_directory,
    validate_record,
)


# =============================================================================
# CONFIGURATION
# =============================================================================

# Input/output paths (relative to project root)
INPUT_DIR = PROJECT_ROOT / "data" / "raw_cvs"
OUTPUT_DIR = PROJECT_ROOT / "data" / "output"
OUTPUT_CSV = OUTPUT_DIR / "education.csv"

# Set to True to generate debug files for each CV
DEBUG_MODE = False
DEBUG_DIR = OUTPUT_DIR / "debug"


# =============================================================================
# MAIN PIPELINE
# =============================================================================

def process_single_cv(pdf_path: Path) -> dict:
    """
    Process a single CV file.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        Dictionary with 'record' (EducationRecord) and 'edu_section' (str)
    """
    # Step 1: Extract text from PDF
    text = extract_text_from_pdf(pdf_path)

    if not text:
        # Return empty record with error note
        from parse_education import EducationRecord
        record = EducationRecord(cv_filename=pdf_path.name)
        record.notes.append("ERROR: Could not extract text from PDF")
        return {'record': record, 'edu_section': None}

    # Step 2: Parse education
    record = parse_education(text, filename=pdf_path.name)

    # Step 3: Get education section for debugging
    edu_section = find_education_section(text)

    # Step 4: Validate and add any warnings
    warnings = validate_record(record)
    for warning in warnings:
        record.notes.append(f"VALIDATION: {warning}")

    return {'record': record, 'edu_section': edu_section}


def run_pipeline():
    """
    Run the complete extraction pipeline.

    Processes all PDFs in INPUT_DIR and writes results to OUTPUT_CSV.
    """
    print("=" * 60)
    print("CV EDUCATION EXTRACTION PIPELINE")
    print("=" * 60)
    print(f"Input directory:  {INPUT_DIR}")
    print(f"Output file:      {OUTPUT_CSV}")
    print("=" * 60)

    # Check input directory exists
    if not INPUT_DIR.exists():
        print(f"[ERROR] Input directory does not exist: {INPUT_DIR}")
        print("Please create the directory and add PDF files.")
        sys.exit(1)

    # Get all PDF files
    pdf_files = get_pdf_files(INPUT_DIR)

    if not pdf_files:
        print(f"[ERROR] No PDF files found in: {INPUT_DIR}")
        sys.exit(1)

    print(f"\nFound {len(pdf_files)} PDF files to process.\n")

    # Ensure output directory exists
    ensure_directory(OUTPUT_DIR)

    if DEBUG_MODE:
        ensure_directory(DEBUG_DIR)
        print(f"Debug mode enabled. Debug files will be written to: {DEBUG_DIR}\n")

    # Process each CV
    records = []
    for i, pdf_path in enumerate(pdf_files, start=1):
        log_progress(i, len(pdf_files), pdf_path.name)

        result = process_single_cv(pdf_path)
        record = result['record']
        edu_section = result['edu_section']

        records.append(record)

        # Debug output if enabled
        if DEBUG_MODE:
            from utils import create_debug_output
            create_debug_output(record, edu_section or "", DEBUG_DIR)

    # Write results to CSV
    print("\nWriting results to CSV...")
    success = write_csv(records, OUTPUT_CSV)

    if not success:
        print("[ERROR] Failed to write output CSV")
        sys.exit(1)

    # Print summary
    print_summary(records)

    print(f"\nDone! Results saved to: {OUTPUT_CSV}")

    # Return records for potential programmatic use
    return records


def main():
    """Entry point."""
    try:
        run_pipeline()
    except KeyboardInterrupt:
        print("\n[INTERRUPTED] Pipeline stopped by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\n[FATAL ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
