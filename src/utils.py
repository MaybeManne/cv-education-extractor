"""
utils.py

Utility functions for the CV education extraction pipeline.
"""

import csv
from pathlib import Path
from typing import List


def ensure_directory(path: str | Path) -> Path:
    """Ensure a directory exists."""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_pdf_files(directory: str | Path) -> List[Path]:
    """Get all PDF files in a directory, sorted."""
    directory = Path(directory)
    if not directory.exists():
        print(f"[WARN] Directory does not exist: {directory}")
        return []
    pdf_files = list(directory.glob("*.pdf"))
    pdf_files.sort(key=lambda p: p.name)
    return pdf_files


def format_degree(degree) -> str:
    """Format a single degree for CSV output."""
    parts = []

    # Degree type is always first
    if degree.degree_type:
        parts.append(degree.degree_type)

    # Field of study
    if degree.field:
        parts.append(degree.field)

    # School within institution (if different from institution)
    if degree.school:
        parts.append(degree.school)

    # Institution
    if degree.institution:
        parts.append(degree.institution)

    # Year
    if degree.year:
        parts.append(f"({degree.year})")

    # Dissertation (PhD only) - add on new line for readability
    if degree.dissertation:
        parts.append(f'[Dissertation: "{degree.dissertation}"]')

    return ", ".join(parts) if parts else ""


def write_csv(records: list, output_path: str | Path) -> bool:
    """
    Write education records to CSV with detailed degree information.

    Columns:
    - name: Person's name
    - cv_filename: Source PDF filename
    - phd: Full PhD details (degree, field, school, institution, year)
    - masters: Full master's details (may have multiple, separated by |)
    - undergrad: Full undergrad details (may have multiple, separated by |)
    - notes: Any extraction notes
    """
    output_path = Path(output_path)
    ensure_directory(output_path.parent)

    fieldnames = [
        'name',
        'cv_filename',
        'phd',
        'masters',
        'undergrad',
        'notes'
    ]

    try:
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
            writer.writeheader()

            for record in records:
                # Format degrees by level
                phd_degrees = record.get_degrees_by_level('phd')
                masters_degrees = record.get_degrees_by_level('masters')
                undergrad_degrees = record.get_degrees_by_level('undergrad')

                phd_str = " | ".join(format_degree(d) for d in phd_degrees) if phd_degrees else ""
                masters_str = " | ".join(format_degree(d) for d in masters_degrees) if masters_degrees else ""
                undergrad_str = " | ".join(format_degree(d) for d in undergrad_degrees) if undergrad_degrees else ""

                # Add notes for missing degrees
                notes = record.notes.copy() if hasattr(record, 'notes') else []
                if not phd_degrees:
                    notes.append("No PhD found")
                if not masters_degrees:
                    notes.append("No master's degree found")
                if not undergrad_degrees:
                    notes.append("No undergrad degree found")

                row = {
                    'name': record.name,
                    'cv_filename': record.cv_filename,
                    'phd': phd_str,
                    'masters': masters_str,
                    'undergrad': undergrad_str,
                    'notes': "; ".join(notes) if notes else ""
                }
                writer.writerow(row)

        print(f"[INFO] CSV written to: {output_path}")
        return True

    except Exception as e:
        print(f"[ERROR] Failed to write CSV: {e}")
        return False


def print_summary(records: list) -> None:
    """Print extraction summary."""
    total = len(records)
    if total == 0:
        print("\n[SUMMARY] No records processed")
        return

    has_name = sum(1 for r in records if r.name)
    has_phd = sum(1 for r in records if r.get_degrees_by_level('phd'))
    has_masters = sum(1 for r in records if r.get_degrees_by_level('masters'))
    has_undergrad = sum(1 for r in records if r.get_degrees_by_level('undergrad'))
    has_any = sum(1 for r in records if r.degrees)

    print("\n" + "=" * 60)
    print("EXTRACTION SUMMARY")
    print("=" * 60)
    print(f"Total CVs processed:      {total}")
    print(f"Names extracted:          {has_name}/{total} ({100*has_name/total:.1f}%)")
    print(f"PhD found:                {has_phd}/{total} ({100*has_phd/total:.1f}%)")
    print(f"Master's found:           {has_masters}/{total} ({100*has_masters/total:.1f}%)")
    print(f"Undergrad found:          {has_undergrad}/{total} ({100*has_undergrad/total:.1f}%)")
    print(f"At least one degree:      {has_any}/{total} ({100*has_any/total:.1f}%)")
    print("=" * 60)

    # Show CVs needing review
    needs_review = [r for r in records if not r.degrees]
    if needs_review:
        print("\n[ATTENTION] CVs with no degrees extracted:")
        for r in needs_review:
            print(f"  - {r.cv_filename}")


def log_progress(current: int, total: int, filename: str) -> None:
    """Log processing progress."""
    pct = 100 * current / total if total > 0 else 0
    print(f"[{current}/{total}] ({pct:.0f}%) Processing: {filename}")


def validate_record(record) -> List[str]:
    """
    Validate an education record and return any warnings.

    Returns list of warning messages.
    """
    warnings = []

    # Check for same institution appearing for multiple degree levels
    institutions_by_level = {}
    for degree in record.degrees:
        if degree.institution:
            if degree.level not in institutions_by_level:
                institutions_by_level[degree.level] = set()
            institutions_by_level[degree.level].add(degree.institution.lower())

    # Check if any institution appears across multiple levels
    all_institutions = []
    for level, insts in institutions_by_level.items():
        all_institutions.extend(insts)

    if len(all_institutions) != len(set(all_institutions)):
        warnings.append("Same institution appears for multiple degrees")

    return warnings
