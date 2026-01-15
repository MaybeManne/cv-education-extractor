#!/usr/bin/env python3
"""
run_pipeline.py

Main entry point for the CV education extraction pipeline.

Usage:
    python3 src/run_pipeline.py

DESIGN:
- Processes all PDFs in data/raw_cvs/
- Extracts text using pdfplumber
- Parses education using degree-first anchoring (searches entire document)
- Outputs to data/output/education.csv

ROBUSTNESS:
- Each CV is processed in isolation (one failure doesn't crash pipeline)
- Errors are logged but don't stop processing
- Designed to handle 500+ CVs

All processing is done locally - no APIs or external services.
"""

import sys
import traceback
from pathlib import Path

# Add src to path for imports (in case running from project root)
SRC_DIR = Path(__file__).parent
PROJECT_ROOT = SRC_DIR.parent
sys.path.insert(0, str(SRC_DIR))

from extract_text import extract_text_from_pdf
from parse_education import parse_education, EducationRecord
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

INPUT_DIR = PROJECT_ROOT / "data" / "raw_cvs"
OUTPUT_DIR = PROJECT_ROOT / "data" / "output"
OUTPUT_CSV = OUTPUT_DIR / "education.csv"

# Set to True to enable verbose debug output
DEBUG_MODE = False


# =============================================================================
# PROCESSING
# =============================================================================

def process_single_cv(pdf_path: Path) -> dict:
    """
    Process a single CV file.

    Wrapped in try/except to ensure one CV failure doesn't crash the pipeline.

    Returns dict with:
    - 'record': EducationRecord with extracted data
    - 'error': Error message if processing failed, None otherwise
    """
    try:
        # Step 1: Extract text from PDF
        text = extract_text_from_pdf(pdf_path)

        if not text:
            # PDF couldn't be read - create empty record with error note
            record = EducationRecord(cv_filename=pdf_path.name)
            record.notes.append("ERROR: Could not extract text from PDF")
            return {'record': record, 'error': "No text extracted"}

        # Step 2: Parse education (scans entire document for degree patterns)
        record = parse_education(text, filename=pdf_path.name)

        # Step 3: Add validation warnings
        warnings = validate_record(record)
        for warning in warnings:
            record.notes.append(f"VALIDATION: {warning}")

        return {'record': record, 'error': None}

    except Exception as e:
        # Log the error but don't crash
        error_msg = f"{type(e).__name__}: {str(e)}"
        record = EducationRecord(cv_filename=pdf_path.name)
        record.notes.append(f"EXCEPTION: {error_msg}")
        return {'record': record, 'error': error_msg}


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

    # Validate input directory
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

    # Process each CV
    records = []
    errors = []

    for i, pdf_path in enumerate(pdf_files, start=1):
        log_progress(i, len(pdf_files), pdf_path.name)

        result = process_single_cv(pdf_path)
        record = result['record']
        error = result['error']

        records.append(record)

        if error:
            errors.append((pdf_path.name, error))

        # Debug output
        if DEBUG_MODE and record.degrees:
            print(f"    Found {len(record.degrees)} degree(s):")
            for d in record.degrees:
                print(f"      - {d}")

    # Write results to CSV
    print("\nWriting results to CSV...")
    success = write_csv(records, OUTPUT_CSV)

    if not success:
        print("[ERROR] Failed to write output CSV")
        sys.exit(1)

    # Print summary
    print_summary(records)

    # Report errors if any
    if errors:
        print(f"\n[WARN] {len(errors)} CV(s) had processing errors:")
        for filename, error in errors[:10]:
            print(f"  - {filename}: {error[:80]}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more errors")

    print(f"\nDone! Results saved to: {OUTPUT_CSV}")

    return records


def main():
    """Entry point with global exception handling."""
    try:
        run_pipeline()
    except KeyboardInterrupt:
        print("\n[INTERRUPTED] Pipeline stopped by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\n[FATAL ERROR] {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
