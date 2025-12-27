"""
parse_education.py

Simple, conservative rule-based parsing of education from CV text.
Extracts undergraduate, master's, and PhD degree information.

Design principles:
1. Be conservative - only extract what we're confident about
2. One degree type = one institution (no duplication)
3. Extract from the same line when possible
4. Leave blank and explain when uncertain
"""

import re
from dataclasses import dataclass, field
from typing import Optional, List, Tuple


@dataclass
class EducationRecord:
    """Structured education data extracted from a CV."""
    name: str = ""
    cv_filename: str = ""
    undergrad_school: str = ""
    masters_school: str = ""
    phd_school: str = ""
    notes: list = field(default_factory=list)

    def notes_str(self) -> str:
        """Return notes as semicolon-separated string."""
        return "; ".join(self.notes) if self.notes else ""


# ============================================================================
# SECTION DETECTION
# ============================================================================

# Headers that indicate start of education section
EDUCATION_HEADERS = [
    r'^EDUCATION\s*[:.]?\s*$',
    r'^EDUCATIONAL\s+BACKGROUND\s*[:.]?\s*$',
    r'^EARNED\s+DEGREES\s*[:.]?\s*$',
    r'^I\.\s*EARNED\s+DEGREES',
    r'^DEGREES\s*[:.]?\s*$',
    r'^ACADEMIC\s+BACKGROUND\s*[:.]?\s*$',
    r'^ACADEMIC\s+QUALIFICATIONS?\s*[:.]?\s*$',
    r'^Employment\s+and\s+Education\s*[:.]?\s*$',
]

# Headers that indicate end of education section
END_HEADERS = [
    r'^EXPERIENCE',
    r'^EMPLOYMENT',
    r'^PROFESSIONAL\s+EXPERIENCE',
    r'^POSITIONS',
    r'^ACADEMIC\s+POSITIONS',
    r'^PUBLICATIONS',
    r'^RESEARCH',
    r'^TEACHING',
    r'^AWARDS',
    r'^HONORS',
    r'^GRANTS',
    r'^SERVICE',
    r'^FELLOWSHIPS',
    r'^SELECTED\s+PAPERS',
    r'^II\.',
    r'^III\.',
]


# ============================================================================
# DEGREE CLASSIFICATION
# ============================================================================

def classify_degree(line: str) -> Optional[str]:
    """
    Determine if a line contains a degree and what type.

    Returns: 'phd', 'masters', 'undergrad', or None
    """
    line_upper = line.upper()

    # PhD patterns (check first - highest priority)
    phd_patterns = [
        r'\bPH\.?\s*D\.?\b',  # Ph.D., PhD, Ph D
        r'\bDOCTOR\s+OF\s+PHILOSOPHY\b',
        r'\bDOCTORATE\b',
        r'\bD\.?\s*B\.?\s*A\.?\b',  # D.B.A., DBA
    ]
    for p in phd_patterns:
        if re.search(p, line_upper):
            return 'phd'

    # Master's patterns
    masters_patterns = [
        r'\bM\.?\s*B\.?\s*A\.?\b',  # M.B.A., MBA
        r'\bM\.?\s*S\.?\b(?!\s*c)',  # M.S. but not MSc followed by other text
        r'\bM\.?\s*A\.?\b',  # M.A., MA
        r'\bM\.?\s*SC\.?\b',
        r'\bM\.?\s*ENG\.?\b',
        r'\bM\.?\s*PHIL\.?\b',
        r'\bMASTER\s+OF\b',
        r'\bMASTER\'?S\s+(?:DEGREE|IN)\b',
        r'\bLICENTIAAT\b',  # Belgian equivalent of master's
    ]
    for p in masters_patterns:
        if re.search(p, line_upper):
            return 'masters'

    # Undergrad patterns
    undergrad_patterns = [
        r'\bB\.?\s*A\.?\b',  # B.A., BA
        r'\bB\.?\s*S\.?\b',  # B.S., BS
        r'\bB\.?\s*SC\.?\b',
        r'\bB\.?\s*S\.?\s*B\.?\b',  # B.S.B.
        r'\bB\.?\s*TECH\.?\b',  # B.Tech
        r'\bBACHELOR\s+OF\s+TECHNOLOGY\b',
        r'\bBACHELOR\s+OF\s+SCIENCE\b',
        r'\bBACHELOR\s+OF\s+ARTS\b',
        r'\bBACHELOR\b',
        r'\bKANDIDAAT\b',  # Belgian equivalent of bachelor's
        r'\bA\.?\s*B\.?\b',  # Artium Baccalaureus (Harvard style)
    ]
    for p in undergrad_patterns:
        if re.search(p, line_upper):
            return 'undergrad'

    return None


def classify_all_degrees(line: str) -> List[str]:
    """
    Determine ALL degree types on a single line.
    Handles cases like "B.A., M.A., Economics, Yale University"

    Returns: List of degree types found (e.g., ['undergrad', 'masters'])
    """
    line_upper = line.upper()
    found = []

    # PhD patterns
    phd_patterns = [
        r'\bPH\.?\s*D\.?\b',
        r'\bDOCTOR\s+OF\s+PHILOSOPHY\b',
        r'\bDOCTORATE\b',
        r'\bD\.?\s*B\.?\s*A\.?\b',
    ]
    for p in phd_patterns:
        if re.search(p, line_upper):
            found.append('phd')
            break

    # Master's patterns
    masters_patterns = [
        r'\bM\.?\s*B\.?\s*A\.?\b',
        r'\bM\.?\s*S\.?\b(?!\s*c)',
        r'\bM\.?\s*A\.?\b',
        r'\bM\.?\s*SC\.?\b',
        r'\bM\.?\s*ENG\.?\b',
        r'\bM\.?\s*PHIL\.?\b',
        r'\bMASTER\s+OF\b',
        r'\bLICENTIAAT\b',
    ]
    for p in masters_patterns:
        if re.search(p, line_upper):
            found.append('masters')
            break

    # Undergrad patterns
    undergrad_patterns = [
        r'\bB\.?\s*A\.?\b',
        r'\bB\.?\s*S\.?\b',
        r'\bB\.?\s*SC\.?\b',
        r'\bB\.?\s*S\.?\s*B\.?\b',
        r'\bB\.?\s*TECH\.?\b',
        r'\bBACHELOR\b',
        r'\bKANDIDAAT\b',
        r'\bA\.?\s*B\.?\b',
    ]
    for p in undergrad_patterns:
        if re.search(p, line_upper):
            found.append('undergrad')
            break

    return found


def is_employment_line(line: str) -> bool:
    """Check if a line describes employment rather than education."""
    employment_indicators = [
        r'\bProfessor\b',
        r'\bAssistant\s+Professor\b',
        r'\bAssociate\s+Professor\b',
        r'\bLecturer\b',
        r'\bInstructor\b',
        r'\bDirector\b',
        r'\bManager\b',
        r'\bConsultant\b',
        r'\bEngineer\b',
        r'\b\d{4}\s*[-–]\s*(Present|present|\d{4})\b',  # Date ranges like "2001-Present"
    ]
    for p in employment_indicators:
        if re.search(p, line, re.IGNORECASE):
            # But make sure it's not also a degree line
            if not classify_degree(line):
                return True
    return False


# ============================================================================
# INSTITUTION EXTRACTION
# ============================================================================

def extract_institution(line: str) -> Optional[str]:
    """
    Extract institution name from a line.

    Handles formats like:
    - "Ph.D., Economics, University of Chicago, 1987"
    - "University of Pennsylvania (Wharton School)"
    - "Stanford University, June 2001"
    - "StanfordUniversity" (no spaces)
    """
    # Handle diacritical marks that might be separated (Turkish, etc.)
    # ˘ (breve) and ¸ (cedilla) sometimes appear after letters
    line = line.replace('g˘', 'ğ').replace('c¸', 'ç').replace('˘', '').replace('¸', '')

    # Handle PDFs without spaces (CamelCase)
    if re.search(r'[a-z][A-Z]', line):
        line = re.sub(r'([a-z])([A-Z])', r'\1 \2', line)
        # Also fix common patterns
        line = re.sub(r'(\w)(University|Institute|College)', r'\1 \2', line)

    # Known institution patterns (ordered by specificity)
    patterns = [
        # Specific well-known schools first (full names)
        r'(Texas\s+A\s*&?\s*M\s+University)',
        r'(Massachusetts\s+Institute\s+of\s+Technology)',
        r'(Indian\s+Institute\s+of\s+Technology)',
        r'(Georgia\s+Institute\s+of\s+Technology)',
        r'(Catholic\s+University\s+(?:of\s+)?[A-Za-z]+)',
        r'(Oklahoma\s+City\s+University)',
        r'(Southern\s+Methodist\s+University)',
        r'(Stanford\s+University)',
        r'(Yale\s+University)',
        r'(Harvard\s+University)',
        r'(Northwestern\s+University)',
        r'(Syracuse\s+University)',
        r'(Emory\s+University)',
        r'(Bo[gğ]azi[cç]i\s*University)',  # Boğaziçi University (Turkish)
        r'(MIT)\b',
        # "University of X" pattern
        r'(University\s+of\s+[A-Z][A-Za-z\s\-]+?)(?:,|\s+\d{4}|;|\s*$)',
        # "X University" pattern - capture words before University
        r'([A-Z][A-Za-z\.\s\-]+?\s+University)(?:,|\s+\d{4}|;|\s*$)',
        # "X College" pattern
        r'([A-Z][A-Za-z\s\-&]+\s+College)(?:,|\s+\d{4}|;|\s*$)',
        # Schools with "School" keyword (like Wharton School)
        r'(The\s+Wharton\s+School)',
    ]

    for pattern in patterns:
        match = re.search(pattern, line, re.IGNORECASE)
        if match:
            institution = match.group(1).strip()
            # Clean up
            institution = re.sub(r'\s+', ' ', institution)
            institution = institution.rstrip('.,;:')
            if len(institution) >= 3:
                return institution

    return None


def extract_institution_with_school(line: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract both institution and specific school/college name.

    Returns: (institution, school_name) e.g., ("University of Pennsylvania", "Wharton School")
    """
    institution = extract_institution(line)
    school_name = None

    # Look for school names in parentheses or after comma
    school_patterns = [
        r'\(([A-Z][A-Za-z\s]+School[^)]*)\)',  # (Wharton School)
        r',\s*([A-Z][A-Za-z\s]+School\s+of\s+[A-Za-z]+)',  # , Kellogg School of Management
        r'([A-Z][A-Za-z]+\s+School\s+of\s+(?:Business|Management|Law))',
        r'([A-Z][A-Za-z]+\s+Business\s+School)',
    ]

    for pattern in school_patterns:
        match = re.search(pattern, line)
        if match:
            school_name = match.group(1).strip()
            break

    return institution, school_name


# ============================================================================
# NAME EXTRACTION
# ============================================================================

def extract_name(text: str) -> str:
    """
    Extract the person's name from the CV.
    Usually at the very top.
    """
    lines = text.strip().split('\n')

    for line in lines[:10]:
        line = line.strip()
        if not line:
            continue

        # Skip common non-name lines
        skip_patterns = [
            r'@',  # Email
            r'\d{3}[-.\s]?\d{3}',  # Phone
            r'http|www\.',  # URL
            r'^curriculum\s+vitae',
            r'^cv\s*$',
            r'^resume',
            r'^address',
            r'^phone',
            r'^updated',
        ]
        if any(re.search(p, line, re.IGNORECASE) for p in skip_patterns):
            continue

        # Name should be mostly letters, 2-5 words
        words = line.split()
        if 2 <= len(words) <= 5:
            alpha_count = sum(1 for c in line if c.isalpha() or c.isspace() or c in '.-,')
            if alpha_count / max(len(line), 1) > 0.85:
                # Clean up
                name = re.sub(r',?\s*(Ph\.?D\.?|MBA|MD|JD).*$', '', line, flags=re.IGNORECASE)
                name = name.strip()
                if name:
                    return name

    return ""


# ============================================================================
# MAIN PARSING LOGIC
# ============================================================================

def find_education_section(text: str) -> Optional[str]:
    """Find and extract the education section from CV text."""
    lines = text.split('\n')

    # Find education header
    # Skip table of contents entries (lines with "......" or page numbers)
    start_idx = None
    for i, line in enumerate(lines):
        line_stripped = line.strip()

        # Skip TOC entries (have dots like "Education ........ 3")
        if '....' in line_stripped or re.search(r'\.\s*\d+\s*$', line_stripped):
            continue

        for pattern in EDUCATION_HEADERS:
            if re.match(pattern, line_stripped, re.IGNORECASE):
                start_idx = i
                break
        if start_idx is not None:
            break

    if start_idx is None:
        return None

    # Find end of section
    end_idx = len(lines)
    for i in range(start_idx + 1, len(lines)):
        line_stripped = lines[i].strip()
        if not line_stripped:
            continue
        for pattern in END_HEADERS:
            if re.match(pattern, line_stripped, re.IGNORECASE):
                end_idx = i
                break
        if end_idx != len(lines):
            break

    # Extract section
    section_lines = lines[start_idx + 1:end_idx]
    return '\n'.join(section_lines).strip()


def parse_degrees(edu_section: str) -> List[dict]:
    """
    Parse education section into individual degree entries.

    Handles both single-line formats:
        "Ph.D., Economics, University of Chicago, 1987"

    And multi-line formats:
        "The Wharton School, University of Pennsylvania"
        "Doctor of Philosophy, Marketing"

    Returns list of dicts: {'type': 'phd'/'masters'/'undergrad', 'institution': str, 'line': str}
    """
    if not edu_section:
        return []

    degrees = []
    all_lines = [l.strip() for l in edu_section.split('\n') if l.strip()]

    # First pass: Find all lines with degrees and try to extract institution
    # Keep track of which lines have degrees for multi-line handling
    degree_lines = []
    for i, line in enumerate(all_lines):
        if is_employment_line(line):
            continue

        # Check for multiple degrees on same line (e.g., "B.A., M.A., Yale")
        degree_types = classify_all_degrees(line)
        if degree_types:
            institution = extract_institution(line)
            for deg_type in degree_types:
                degree_lines.append({
                    'index': i,
                    'type': deg_type,
                    'institution': institution,
                    'line': line
                })

    # Second pass: For degrees without institution, check ORIGINAL adjacent lines
    for d in degree_lines:
        if d['institution']:
            continue  # Already has institution

        idx = d['index']

        # Check previous line in original text (not filtered)
        if idx > 0:
            prev_line = all_lines[idx - 1]
            if not is_employment_line(prev_line):
                inst = extract_institution(prev_line)
                if inst:
                    d['institution'] = inst
                    d['line'] = f"{prev_line} / {d['line']}"
                    continue

        # Check next line in original text
        if idx + 1 < len(all_lines):
            next_line = all_lines[idx + 1]
            if not is_employment_line(next_line):
                inst = extract_institution(next_line)
                if inst:
                    d['institution'] = inst
                    d['line'] = f"{d['line']} / {next_line}"

    # Build final list
    for d in degree_lines:
        if d['institution']:
            degrees.append({
                'type': d['type'],
                'institution': d['institution'],
                'line': d['line']
            })

    return degrees


def parse_education(text: str, filename: str = "") -> EducationRecord:
    """
    Main entry point: parse education from CV text.
    """
    record = EducationRecord(cv_filename=filename)

    if not text:
        record.notes.append("No text provided")
        return record

    # Extract name
    record.name = extract_name(text)
    if not record.name:
        record.notes.append("Could not extract name")

    # Find education section
    edu_section = find_education_section(text)
    if not edu_section:
        record.notes.append("No education section found")
        return record

    # Parse degrees
    degrees = parse_degrees(edu_section)

    if not degrees:
        record.notes.append("No degrees found in education section")
        return record

    # Assign degrees to fields
    # Track what we've assigned to avoid duplicates
    phd_found = []
    masters_found = []
    undergrad_found = []

    for d in degrees:
        if d['type'] == 'phd':
            phd_found.append(d['institution'])
        elif d['type'] == 'masters':
            masters_found.append(d['institution'])
        elif d['type'] == 'undergrad':
            undergrad_found.append(d['institution'])

    # Assign PhD
    if len(phd_found) == 1:
        record.phd_school = phd_found[0]
    elif len(phd_found) > 1:
        # Multiple PhDs - use first, note others
        record.phd_school = phd_found[0]
        record.notes.append(f"Multiple PhDs listed: {', '.join(phd_found)}")
    else:
        record.notes.append("No PhD found")

    # Assign Master's
    if len(masters_found) == 1:
        record.masters_school = masters_found[0]
    elif len(masters_found) > 1:
        # Multiple master's - use first, note others
        record.masters_school = masters_found[0]
        record.notes.append(f"Multiple master's degrees: {', '.join(masters_found)}")
    else:
        record.notes.append("No master's degree found")

    # Assign Undergrad
    if len(undergrad_found) == 1:
        record.undergrad_school = undergrad_found[0]
    elif len(undergrad_found) > 1:
        # Multiple undergrad - use first, note others
        record.undergrad_school = undergrad_found[0]
        if len(set(undergrad_found)) > 1:
            record.notes.append(f"Multiple undergrad degrees: {', '.join(undergrad_found)}")
        else:
            record.notes.append(f"Multiple undergrad degrees at same institution")
    else:
        record.notes.append("No undergrad degree found")

    return record
