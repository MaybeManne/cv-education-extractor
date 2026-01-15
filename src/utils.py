"""
utils.py

Utility functions for the CV education extraction pipeline.

OUTPUT SCHEMA (per Blake's requirements):
- Each row = one CV
- Columns are fully normalized, one variable per column
- Multiple degrees at same level use numbered columns (undergrad_1_*, undergrad_2_*)
- No dissertations or professional certifications

Column layout:
  person_name, cv_filename,
  undergrad_1_degree, undergrad_1_major, undergrad_1_school, undergrad_1_year,
  undergrad_2_degree, undergrad_2_major, undergrad_2_school, undergrad_2_year,
  masters_1_degree, masters_1_major, masters_1_school, masters_1_year,
  masters_2_degree, masters_2_major, masters_2_school, masters_2_year,
  phd_degree, phd_major, phd_school, phd_year,
  notes
"""

import csv
from pathlib import Path
from typing import List


def ensure_directory(path: str | Path) -> Path:
    """Ensure a directory exists, creating it if necessary."""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_pdf_files(directory: str | Path) -> List[Path]:
    """Get all PDF files in a directory, sorted alphabetically."""
    directory = Path(directory)
    if not directory.exists():
        print(f"[WARN] Directory does not exist: {directory}")
        return []
    pdf_files = list(directory.glob("*.pdf"))
    pdf_files.sort(key=lambda p: p.name)
    return pdf_files


# ============================================================================
# CSV OUTPUT - Normalized schema with numbered columns
# ============================================================================

# Define the exact column order for the output CSV
# This is the authoritative schema definition
CSV_COLUMNS = [
    # Identification
    'person_name',
    'cv_filename',

    # Undergrad degrees (up to 2)
    'undergrad_1_degree',
    'undergrad_1_major',
    'undergrad_1_school',
    'undergrad_1_year',
    'undergrad_2_degree',
    'undergrad_2_major',
    'undergrad_2_school',
    'undergrad_2_year',

    # Master's degrees (up to 2)
    'masters_1_degree',
    'masters_1_major',
    'masters_1_school',
    'masters_1_year',
    'masters_2_degree',
    'masters_2_major',
    'masters_2_school',
    'masters_2_year',

    # PhD (typically just one)
    'phd_degree',
    'phd_major',
    'phd_school',
    'phd_year',

    # Notes/warnings
    'notes',
]


def write_csv(records: list, output_path: str | Path) -> bool:
    """
    Write education records to CSV with normalized columns.

    Each level (undergrad, masters) supports up to 2 degrees with numbered columns.
    PhD typically has just one set of columns.

    All fields are quoted to handle commas and special characters in values.
    """
    output_path = Path(output_path)
    ensure_directory(output_path.parent)

    try:
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(
                f,
                fieldnames=CSV_COLUMNS,
                quoting=csv.QUOTE_ALL,
                extrasaction='ignore'  # Silently ignore extra keys
            )
            writer.writeheader()

            for record in records:
                row = build_csv_row(record)
                writer.writerow(row)

        print(f"[INFO] CSV written to: {output_path}")
        return True

    except Exception as e:
        print(f"[ERROR] Failed to write CSV: {e}")
        import traceback
        traceback.print_exc()
        return False


def build_csv_row(record) -> dict:
    """
    Build a single CSV row from an EducationRecord.

    This function handles:
    - Separating degrees by level
    - Numbering multiple degrees at the same level
    - Leaving unused columns blank
    - Collecting notes about the extraction
    """
    row = {col: '' for col in CSV_COLUMNS}  # Start with all blank

    # Identification
    row['person_name'] = record.name or ''
    row['cv_filename'] = record.cv_filename or ''

    # Get degrees by level
    undergrad_degrees = record.get_degrees_by_level('undergrad')
    masters_degrees = record.get_degrees_by_level('masters')
    phd_degrees = record.get_degrees_by_level('phd')

    # Fill undergrad columns (up to 2)
    for i, degree in enumerate(undergrad_degrees[:2], start=1):
        row[f'undergrad_{i}_degree'] = degree.degree_type
        row[f'undergrad_{i}_major'] = degree.field
        row[f'undergrad_{i}_school'] = degree.institution
        row[f'undergrad_{i}_year'] = degree.year

    # Fill masters columns (up to 2)
    for i, degree in enumerate(masters_degrees[:2], start=1):
        row[f'masters_{i}_degree'] = degree.degree_type
        row[f'masters_{i}_major'] = degree.field
        row[f'masters_{i}_school'] = degree.institution
        row[f'masters_{i}_year'] = degree.year

    # Fill PhD columns (just one set, take the first if multiple)
    if phd_degrees:
        phd = phd_degrees[0]
        row['phd_degree'] = phd.degree_type
        row['phd_major'] = phd.field
        row['phd_school'] = phd.institution
        row['phd_year'] = phd.year

    # Build notes
    notes = list(record.notes) if hasattr(record, 'notes') else []

    # Note if more degrees were found than we have columns for
    if len(undergrad_degrees) > 2:
        notes.append(f"{len(undergrad_degrees)} undergrad degrees found, only first 2 shown")
    if len(masters_degrees) > 2:
        notes.append(f"{len(masters_degrees)} masters degrees found, only first 2 shown")
    if len(phd_degrees) > 1:
        notes.append(f"{len(phd_degrees)} PhD degrees found, only first shown")

    row['notes'] = '; '.join(notes) if notes else ''

    return row


# ============================================================================
# SUMMARY AND LOGGING
# ============================================================================

def print_summary(records: list) -> None:
    """Print extraction summary statistics."""
    total = len(records)
    if total == 0:
        print("\n[SUMMARY] No records processed")
        return

    # Calculate statistics
    has_name = sum(1 for r in records if r.name)
    has_phd = sum(1 for r in records if r.get_degrees_by_level('phd'))
    has_masters = sum(1 for r in records if r.get_degrees_by_level('masters'))
    has_undergrad = sum(1 for r in records if r.get_degrees_by_level('undergrad'))
    has_any = sum(1 for r in records if r.degrees)
    no_education = sum(1 for r in records if not r.degrees)

    # Print summary table
    print("\n" + "=" * 60)
    print("EXTRACTION SUMMARY")
    print("=" * 60)
    print(f"Total CVs processed:      {total}")
    print(f"Names extracted:          {has_name}/{total} ({100*has_name/total:.1f}%)")
    print(f"PhD found:                {has_phd}/{total} ({100*has_phd/total:.1f}%)")
    print(f"Master's found:           {has_masters}/{total} ({100*has_masters/total:.1f}%)")
    print(f"Undergrad found:          {has_undergrad}/{total} ({100*has_undergrad/total:.1f}%)")
    print(f"At least one degree:      {has_any}/{total} ({100*has_any/total:.1f}%)")
    print("-" * 60)
    print(f"NO EDUCATION FOUND:       {no_education}/{total} ({100*no_education/total:.1f}%)")
    print("=" * 60)

    # List CVs with no education (limited to first 20)
    if no_education > 0:
        needs_review = [r for r in records if not r.degrees]
        print(f"\n[ATTENTION] {no_education} CV(s) with no degrees extracted:")
        for r in needs_review[:20]:
            print(f"  - {r.cv_filename}")
        if len(needs_review) > 20:
            print(f"  ... and {len(needs_review) - 20} more")

    # Count multiple degrees at same level
    multi_undergrad = sum(1 for r in records if len(r.get_degrees_by_level('undergrad')) > 1)
    multi_masters = sum(1 for r in records if len(r.get_degrees_by_level('masters')) > 1)
    multi_phd = sum(1 for r in records if len(r.get_degrees_by_level('phd')) > 1)

    if multi_undergrad or multi_masters or multi_phd:
        print(f"\n[INFO] Multiple degrees at same level:")
        if multi_undergrad:
            print(f"  - Multiple undergrad: {multi_undergrad}")
        if multi_masters:
            print(f"  - Multiple masters: {multi_masters}")
        if multi_phd:
            print(f"  - Multiple PhD: {multi_phd}")


def log_progress(current: int, total: int, filename: str) -> None:
    """Log processing progress with percentage."""
    pct = 100 * current / total if total > 0 else 0
    print(f"[{current}/{total}] ({pct:.0f}%) Processing: {filename}")


# ============================================================================
# VALIDATION
# ============================================================================

def validate_record(record) -> List[str]:
    """
    Validate an education record and return any warnings.

    Checks for anomalies that might indicate extraction issues:
    - Same institution across multiple degree levels
    - Unusual patterns that might be false positives
    """
    warnings = []

    # Check for same institution appearing for multiple degree levels
    # This isn't necessarily wrong (people do get multiple degrees from same school)
    # but it's worth flagging for review
    institutions_by_level = {}
    for degree in record.degrees:
        if degree.institution:
            inst_lower = degree.institution.lower()
            if degree.level not in institutions_by_level:
                institutions_by_level[degree.level] = set()
            institutions_by_level[degree.level].add(inst_lower)

    # Find institutions that appear in multiple levels
    all_institutions = []
    for level, insts in institutions_by_level.items():
        all_institutions.extend(insts)

    if len(all_institutions) != len(set(all_institutions)):
        warnings.append("Same institution appears for multiple degree levels")

    return warnings
