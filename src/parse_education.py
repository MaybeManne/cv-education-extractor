"""
parse_education.py

Extracts detailed education information from CV text.
For each degree: type, institution, school/college, field of study, year.
"""

import re
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class Degree:
    """A single degree with full details."""
    degree_type: str = ""      # e.g., "Ph.D.", "MBA", "B.S."
    institution: str = ""       # e.g., "University of Pennsylvania"
    school: str = ""            # e.g., "Wharton School" (within institution)
    field: str = ""             # e.g., "Marketing", "Economics"
    year: str = ""              # e.g., "2009", "1987"
    level: str = ""             # "phd", "masters", "undergrad"
    dissertation: str = ""      # Dissertation title/topic (PhD only)
    raw_text: str = ""          # Original text for verification

    def __str__(self) -> str:
        """Format degree for display."""
        parts = [self.degree_type]
        if self.field:
            parts.append(self.field)
        if self.school:
            parts.append(self.school)
        if self.institution:
            parts.append(self.institution)
        if self.year:
            parts.append(f"({self.year})")
        return ", ".join(parts)


@dataclass
class EducationRecord:
    """All education data for a person."""
    name: str = ""
    cv_filename: str = ""
    degrees: List[Degree] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def get_degrees_by_level(self, level: str) -> List[Degree]:
        """Get all degrees at a given level."""
        return [d for d in self.degrees if d.level == level]

    def format_degrees(self, level: str) -> str:
        """Format all degrees at a level for CSV output."""
        degs = self.get_degrees_by_level(level)
        if not degs:
            return ""
        return " | ".join(str(d) for d in degs)


# ============================================================================
# SECTION DETECTION
# ============================================================================

EDUCATION_HEADERS = [
    r'^EDUCATION\s*[:.]?\s*$',
    r'^EDUCATIONAL\s+BACKGROUND\s*[:.]?\s*$',
    r'^EARNED\s+DEGREES\s*[:.]?\s*$',
    r'^I\.\s*EARNED\s+DEGREES',
    r'^DEGREES\s*[:.]?\s*$',
    r'^ACADEMIC\s+BACKGROUND\s*[:.]?\s*$',
    r'^Employment\s+and\s+Education\s*[:.]?\s*$',
]

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
# DEGREE PATTERNS
# ============================================================================

# Map degree abbreviations to (display_name, level)
# Patterns use word boundaries and require periods or specific structure to avoid false matches
DEGREE_PATTERNS = {
    # Doctoral - most specific first
    r'\bPh\.?\s*D\.': ('Ph.D.', 'phd'),
    r'\bPhD\b': ('Ph.D.', 'phd'),
    r'\bDoctor\s+of\s+Philosophy': ('Ph.D.', 'phd'),
    r'\bD\.B\.A\.': ('D.B.A.', 'phd'),
    r'\bDBA\b': ('D.B.A.', 'phd'),
    r'\bDoctor\s+of\s+Business\s+Administration': ('D.B.A.', 'phd'),

    # Master's - require periods or word boundary after
    r'\bM\.B\.A\.': ('MBA', 'masters'),
    r'\bMBA\b': ('MBA', 'masters'),
    r'\bMaster\s+of\s+Business\s+Administration': ('MBA', 'masters'),
    r'\bM\.S\.': ('M.S.', 'masters'),
    r'\bMS\b(?!\s*\d)': ('M.S.', 'masters'),  # MS not followed by number
    r'\bMaster\s+of\s+Science': ('M.S.', 'masters'),
    r'\bM\.A\.': ('M.A.', 'masters'),
    r'\bMA\b(?!\s*\d)': ('M.A.', 'masters'),  # MA not followed by number
    r'\bMaster\s+of\s+Arts': ('M.A.', 'masters'),
    r'\bM\.Sc\.': ('M.Sc.', 'masters'),
    r'\bMSc\b': ('M.Sc.', 'masters'),
    r'\bM\.Phil\.': ('M.Phil.', 'masters'),
    r'\bMPhil\b': ('M.Phil.', 'masters'),
    r'\bLicentiaat\b': ('Licentiaat', 'masters'),

    # Bachelor's - require periods or word boundary after
    # Use negative lookbehind to avoid matching B.A. within M.B.A. or B.S. within M.B.S.
    r'(?<![M\.])\bB\.A\.': ('B.A.', 'undergrad'),
    r'(?<!M)\bBA\b(?!\s*\d)': ('B.A.', 'undergrad'),  # BA not followed by number
    r'\bBachelor\s+of\s+Arts': ('B.A.', 'undergrad'),
    r'(?<![M\.])\bB\.S\.(?!B)': ('B.S.', 'undergrad'),  # B.S. but not B.S.B.
    r'(?<!M)\bBS\b(?!\s*\d)': ('B.S.', 'undergrad'),  # BS not followed by number
    r'\bBachelor\s+of\s+Science': ('B.S.', 'undergrad'),
    r'\bB\.S\.B\.': ('B.S.B.', 'undergrad'),
    r'\bBSB\b': ('B.S.B.', 'undergrad'),
    r'\bB\.Sc\.': ('B.Sc.', 'undergrad'),
    r'\bBSc\b': ('B.Sc.', 'undergrad'),
    r'\bB\.Tech\.': ('B.Tech.', 'undergrad'),
    r'\bBTech\b': ('B.Tech.', 'undergrad'),
    r'\bBachelor\s+of\s+Technology': ('B.Tech.', 'undergrad'),
    r'\bB\.Eng\.': ('B.Eng.', 'undergrad'),
    r'\bBEng\b': ('B.Eng.', 'undergrad'),
    r'\bA\.B\.': ('A.B.', 'undergrad'),
    r'\bAB\b(?=\s*[,\d])': ('A.B.', 'undergrad'),  # AB followed by comma or year
    r'\bKandidaat\b': ('Kandidaat', 'undergrad'),
}


def extract_degree_info(line: str) -> List[dict]:
    """
    Extract all degree information from a line.

    Returns list of dicts with: degree_type, level, field
    """
    degrees_found = []
    line_upper = line.upper()

    # Check each degree pattern
    for pattern, (degree_type, level) in DEGREE_PATTERNS.items():
        if re.search(pattern, line, re.IGNORECASE):
            # Found a degree - try to extract field
            field = extract_field(line, degree_type)
            degrees_found.append({
                'degree_type': degree_type,
                'level': level,
                'field': field
            })

    # Deduplicate by (degree_type, level) - allow multiple different degrees at same level
    # e.g., "B.A., Mathematics, B.S., Economics" should keep both
    seen = set()
    unique = []
    for d in degrees_found:
        key = (d['degree_type'], d['level'])
        if key not in seen:
            seen.add(key)
            unique.append(d)

    return unique


def extract_field(line: str, degree_type: str) -> str:
    """Extract field of study from a degree line."""
    # Normalize CamelCase first
    line = normalize_text(line)

    # Create flexible pattern that matches both "B.A." and "BA" formats
    # Remove periods and create pattern that matches with or without them
    degree_base = degree_type.replace('.', '')  # "B.A." -> "BA"
    # Build pattern: B\.?A\.? to match "BA", "B.A.", "B.A", etc.
    degree_pattern = r'\.?\s*'.join(degree_base)  # "BA" -> "B\.?\s*A"
    degree_pattern = r'\b' + degree_pattern + r'\.?'

    # Common patterns:
    # "Ph.D. in Marketing"
    # "Ph.D., Marketing"
    # "Ph.D., Economics, University of..."
    # "MBA in Strategy and Marketing"
    # "BA, Political Science and Economics, University of..."
    # "Kandidaat in de Sociologie" (Dutch/Belgian)
    # "Licentiaat in de Psychologie" (Dutch/Belgian)

    # Pattern 0: Dutch/Belgian "in de [Field]" pattern
    # Handles: "Kandidaat in de Sociologie", "Licentiaat in de Psychologie"
    match = re.search(rf'{degree_pattern}\s+in\s+de\s+([A-Za-z]+)',
                      line, re.IGNORECASE)
    if match:
        field = match.group(1).strip()
        if len(field) > 2:
            return field

    # Pattern 1: "Degree in/of Field" - include "and" in field names
    # Handles: "MBA in Strategy and Marketing", "Ph.D. in Economics"
    # Note: Don't include comma in field chars to avoid capturing institution
    match = re.search(rf'{degree_pattern}\s+(?:in|of)\s+([A-Za-z][A-Za-z\s&]+?)(?:\s*,|\s+\d{{4}}|\s+[A-Z][a-z]+\s+University|\s+[A-Z][a-z]+\s+School|\s*$)',
                      line, re.IGNORECASE)
    if match:
        field = match.group(1).strip().rstrip(',')
        if len(field) > 2 and len(field) < 60:
            return clean_field(field)

    # Pattern 2: "Degree, Field, Institution" or "Degree, Field, Year"
    match = re.search(rf'{degree_pattern}\s*,\s*([A-Za-z\s&]+?)(?:,|\s+\d{{4}})',
                      line, re.IGNORECASE)
    if match:
        field = match.group(1).strip()
        # Make sure it's not an institution name
        if not any(w in field.lower() for w in ['university', 'college', 'institute', 'school']):
            if len(field) > 2 and len(field) < 50:
                return clean_field(field)

    # Pattern 3: "Degree Field, School/Institution" (space after degree, no comma before field)
    # Handles: "Ph.D. Management and Organizations, Kellogg School"
    match = re.search(rf'{degree_pattern}\s+([A-Za-z][A-Za-z\s&]+?)(?:,|\s+\d{{4}})',
                      line, re.IGNORECASE)
    if match:
        field = match.group(1).strip()
        # Make sure it's not an institution name or school name
        if not any(w in field.lower() for w in ['university', 'college', 'institute', 'school', 'summa', 'magna', 'cum laude', 'honors']):
            if len(field) > 2 and len(field) < 50:
                return clean_field(field)

    # Pattern 4: Multiple degrees sharing a field "B.A., M.A., Economics"
    # Look for field after the degree in a multi-degree line
    match = re.search(rf'{degree_pattern}\s*,\s*(?:M\.?A\.?|B\.?A\.?|M\.?S\.?|B\.?S\.?)\s*,\s*([A-Za-z\s&]+?)(?:,|\s+\d{{4}})',
                      line, re.IGNORECASE)
    if match:
        field = match.group(1).strip()
        if not any(w in field.lower() for w in ['university', 'college', 'institute', 'school']):
            if len(field) > 2 and len(field) < 50:
                return clean_field(field)

    # Pattern 5: Full degree name with field "Doctor of Philosophy, Marketing"
    # or "Bachelor of Technology, Mechanical Engineering"
    full_degree_patterns = [
        (r'Doctor\s+of\s+Philosophy\s*,\s*([A-Za-z\s&]+?)(?:\s*$|,|\d{4})', 'phd'),
        (r'Master\s+of\s+(?:Science|Arts|Business)\s*,\s*([A-Za-z\s&]+?)(?:\s*$|,|\d{4})', 'masters'),
        (r'Bachelor\s+of\s+(?:Science|Arts|Technology|Engineering)\s*,\s*([A-Za-z\s&]+?)(?:\s*$|,|\d{4})', 'undergrad'),
    ]
    for pattern, _ in full_degree_patterns:
        match = re.search(pattern, line, re.IGNORECASE)
        if match:
            field = match.group(1).strip()
            if not any(w in field.lower() for w in ['university', 'college', 'institute', 'school']):
                if len(field) > 2 and len(field) < 50:
                    return clean_field(field)

    return ""


def extract_field_from_context(lines: List[str], degree_line_idx: int, degree_type: str) -> Optional[str]:
    """
    Extract field from nearby lines when not on the degree line itself.

    Handles patterns like:
    - "AcademicArea: Operations, Information & Technology" (on separate line)
    - "Concentration: Experimental Psychology"
    - "Major: Economics"
    """
    # Search within a few lines after the degree entry
    search_range = min(degree_line_idx + 4, len(lines))

    for i in range(degree_line_idx + 1, search_range):
        line = normalize_text(lines[i].strip())

        # Skip bullet points and empty-ish lines
        if line in ['•', '-', ''] or len(line) < 5:
            continue

        # Pattern: "AcademicArea:" or "Academic Area:"
        match = re.search(r'Academic\s*Area[:\s]+([A-Za-z,\s&]+?)(?:\s*$|•)', line, re.IGNORECASE)
        if match:
            field = match.group(1).strip().rstrip(',.')
            # Clean up spacing (e.g., "Operations,Information" -> "Operations, Information")
            field = re.sub(r',(?!\s)', ', ', field)
            field = re.sub(r'&(?!\s)', ' & ', field)
            if len(field) > 2:
                return field

        # Pattern: "Concentration:" or "Major:" or "Specialization:"
        match = re.search(r'(?:Concentration|Major|Specialization|Field)[:\s]+([A-Za-z\s&]+?)(?:\s*$|,|\d{4})',
                         line, re.IGNORECASE)
        if match:
            field = match.group(1).strip()
            if len(field) > 2 and len(field) < 50:
                return field

    return None


def clean_field(field: str) -> str:
    """Clean up extracted field name."""
    # Remove common prefixes/suffixes
    field = re.sub(r'^(in|of)\s+', '', field, flags=re.IGNORECASE)
    field = re.sub(r'\s+(from|at)\s*$', '', field, flags=re.IGNORECASE)
    field = field.strip(' ,.')
    return field


# ============================================================================
# INSTITUTION EXTRACTION
# ============================================================================

def normalize_text(line: str) -> str:
    """Normalize text for extraction (handle special chars, CamelCase)."""
    # Handle Turkish diacritics
    line = line.replace('g˘', 'ğ').replace('c¸', 'ç').replace('˘', '').replace('¸', '')

    # Handle common lowercase connector words BEFORE CamelCase normalization
    # e.g., "PricingwithDemand" -> "PricingWithDemand" -> "Pricing With Demand"
    # This capitalizes the connector word so CamelCase detection will add space
    connector_words = ['with', 'under', 'from', 'into', 'over', 'about']
    for word in connector_words:
        # Match: lowercase letter + connector + uppercase letter
        pattern = rf'([a-z])({word})([A-Z])'
        # Replace with capitalized connector to trigger CamelCase spacing
        line = re.sub(pattern, lambda m: m.group(1) + m.group(2).capitalize() + m.group(3), line)

    # Handle CamelCase (PDFs without spaces)
    if re.search(r'[a-z][A-Z]', line):
        line = re.sub(r'([a-z])([A-Z])', r'\1 \2', line)
        line = re.sub(r'(\w)(University|Institute|College|School)', r'\1 \2', line)

    # Lowercase connector words that should not be capitalized in titles
    for word in connector_words:
        line = re.sub(rf'\b{word.capitalize()}\b', word, line)

    return line


def extract_institution(line: str) -> Optional[str]:
    """Extract institution name from a line."""
    line = normalize_text(line)

    # Handle compound institutions first (e.g., "Oklahoma City University – Moscow State University")
    # These are joint programs between two universities
    compound_match = re.search(
        r'([A-Z][A-Za-z\s]+(?:University|Institute|College))\s*[–-]\s*([A-Z][A-Za-z\s]+(?:University|Institute|College)(?:\s*\([^)]+\))?)',
        line
    )
    if compound_match:
        inst1 = compound_match.group(1).strip()
        inst2 = compound_match.group(2).strip()
        return f"{inst1} / {inst2}"

    # Known institution patterns
    patterns = [
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
        r'(Moscow\s+State\s+University(?:\s*\([^)]+\))?)',
        r'(Bo[gğ]azi[cç]i\s*University)',
        r'(University\s+of\s+[A-Z][A-Za-z\s\-]+?)(?:,|\s+\d{4}|;|\s*$)',
        r'([A-Z][A-Za-z\.\s\-]+?\s+University(?:\s*\([^)]+\))?)(?:,|\s+\d{4}|;|\s*$)',
        r'([A-Z][A-Za-z\s\-&]+\s+College)(?:,|\s+\d{4}|;|\s*$)',
    ]

    for pattern in patterns:
        match = re.search(pattern, line, re.IGNORECASE)
        if match:
            institution = match.group(1).strip()
            institution = re.sub(r'\s+', ' ', institution)
            institution = institution.rstrip('.,;:')
            if len(institution) >= 3:
                return institution

    return None


def extract_school(line: str) -> Optional[str]:
    """Extract school/college name within an institution."""
    patterns = [
        r'(Wharton\s+School)',
        r'(Kellogg\s+School\s+of\s+Management)',
        r'(Booth\s+School\s+of\s+Business)',
        r'(Graduate\s+School\s+of\s+Business)',
        r'(Goizueta\s+Business\s+School)',
        r'(Fuqua\s+School\s+of\s+Business)',
        r'(Ross\s+School\s+of\s+Business)',
        r'(Stern\s+School\s+of\s+Business)',
        r'(Sloan\s+School)',
        r'(Haas\s+School)',
        r'(Johnson\s+(?:Graduate\s+)?School)',
        r'(Darden\s+School)',
        r'(Scheller\s+College)',
        r'(Newhouse\s+School[^,]*)',
        r'([A-Z][a-z]+\s+School\s+of\s+(?:Business|Management|Law|Medicine|Engineering))',
        r'([A-Z][a-z]+\s+Business\s+School)',
    ]

    line = normalize_text(line)

    for pattern in patterns:
        match = re.search(pattern, line, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    return None


def extract_year(line: str) -> Optional[str]:
    """Extract graduation year from a line."""
    # Check for date range pattern first: "August 2008 - June 2012" or "2008-2012"
    # In date ranges, the END year is the graduation year
    range_match = re.search(r'\b(19[5-9]\d|20[0-3]\d)\s*[-–]\s*(?:\w+\s+)?(19[5-9]\d|20[0-3]\d)\b', line)
    if range_match:
        return range_match.group(2)  # Return the END year

    # Look for 4-digit years between 1950-2030
    matches = re.findall(r'\b(19[5-9]\d|20[0-3]\d)\b', line)
    if matches:
        # Check if there's a pattern like "Distinguished alumnus, 2017" after the degree year
        # In that case, return the first year
        if len(matches) > 1 and re.search(r'alumnus|award|honor', line, re.IGNORECASE):
            return matches[0]
        # Otherwise return the last year (usually graduation year for single dates)
        return matches[-1]
    return None


def extract_dissertation(lines: List[str], phd_line_idx: int) -> Optional[str]:
    """
    Extract dissertation title/topic for a PhD degree.

    Looks for explicit dissertation mentions in the education section.
    Only returns if explicitly stated - never guesses.

    Common patterns:
    - "Dissertation: [title]"
    - "Thesis: [title]"
    - "Dissertation title: [title]"
    - "Topic: [topic]"
    - Lines in quotes following PhD entry
    """
    # Search within a few lines after the PhD entry
    search_range = min(phd_line_idx + 5, len(lines))

    for i in range(phd_line_idx, search_range):
        line = normalize_text(lines[i].strip())

        # Pattern 1: "Dissertation:" or "Thesis:" prefix
        match = re.search(r'(?:Dissertation|Thesis)\s*(?:title)?[:\s]+["\u201c]?(.+?)["\u201d]?\s*$',
                         line, re.IGNORECASE)
        if match:
            title = match.group(1).strip().strip('""\u201c\u201d')
            if len(title) > 10:  # Reasonable title length
                return title

        # Pattern 2: "Topic:" prefix
        match = re.search(r'Topic[:\s]+["\u201c]?(.+?)["\u201d]?\s*$', line, re.IGNORECASE)
        if match:
            title = match.group(1).strip().strip('""\u201c\u201d')
            if len(title) > 10:
                return title

        # Pattern 3: Quoted text on a line by itself (likely dissertation title)
        # Only if it follows the PhD line closely
        if i > phd_line_idx and i <= phd_line_idx + 2:
            match = re.match(r'^["\u201c](.+)["\u201d]$', line)
            if match:
                title = match.group(1).strip()
                if len(title) > 15:  # Dissertation titles are usually longer
                    return title

    return None


# ============================================================================
# NAME EXTRACTION
# ============================================================================

def extract_name(text: str) -> str:
    """Extract person's name from CV."""
    lines = text.strip().split('\n')

    for line in lines[:10]:
        line = line.strip()
        if not line:
            continue

        # Skip non-name lines
        skip_patterns = [
            r'@', r'\d{3}[-.\s]?\d{3}', r'http|www\.',
            r'^curriculum\s+vitae', r'^cv\s*$', r'^resume',
            r'^address', r'^phone', r'^updated',
        ]
        if any(re.search(p, line, re.IGNORECASE) for p in skip_patterns):
            continue

        # Name: mostly letters, 2-5 words
        words = line.split()
        if 2 <= len(words) <= 5:
            alpha_count = sum(1 for c in line if c.isalpha() or c.isspace() or c in '.-,')
            if alpha_count / max(len(line), 1) > 0.85:
                name = re.sub(r',?\s*(Ph\.?D\.?|MBA|MD|JD).*$', '', line, flags=re.IGNORECASE)
                return name.strip()

    return ""


# ============================================================================
# EMPLOYMENT DETECTION
# ============================================================================

def is_employment_line(line: str) -> bool:
    """Check if line describes employment."""
    patterns = [
        r'\bProfessor\b',
        r'\bAssistant\s+Professor\b',
        r'\bAssociate\s+Professor\b',
        r'\bLecturer\b',
        r'\bDirector\b',
        r'\bManager\b',
        r'\bConsultant\b',
        r'\b\d{4}\s*[-–]\s*(Present|present|\d{4})\b',
    ]
    for p in patterns:
        if re.search(p, line, re.IGNORECASE):
            # But not if it also has a degree
            if not any(re.search(dp, line, re.IGNORECASE) for dp in DEGREE_PATTERNS.keys()):
                return True
    return False


# ============================================================================
# MAIN PARSING
# ============================================================================

def find_education_section(text: str) -> Optional[str]:
    """Find and extract education section."""
    lines = text.split('\n')

    start_idx = None
    for i, line in enumerate(lines):
        line_stripped = line.strip()

        # Skip TOC entries
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

    section_lines = lines[start_idx + 1:end_idx]
    return '\n'.join(section_lines).strip()


def parse_education(text: str, filename: str = "") -> EducationRecord:
    """Main parsing function."""
    record = EducationRecord(cv_filename=filename)

    if not text:
        record.notes.append("No text provided")
        return record

    record.name = extract_name(text)
    if not record.name:
        record.notes.append("Could not extract name")

    edu_section = find_education_section(text)
    if not edu_section:
        record.notes.append("No education section found")
        return record

    # Parse degrees
    all_lines = [l.strip() for l in edu_section.split('\n') if l.strip()]

    # Track institutions for multi-line handling
    pending_institution = None
    pending_school = None
    pending_year = None

    for i, line in enumerate(all_lines):
        if is_employment_line(line):
            continue

        # Check for degrees on this line
        degree_infos = extract_degree_info(line)

        if degree_infos:
            # Found degree(s) - extract institution from this line or nearby
            institution = extract_institution(line)
            school = extract_school(line)
            year = extract_year(line)

            # If no year on degree line, check previous line
            if not year and i > 0:
                prev_line = all_lines[i - 1]
                year = extract_year(prev_line)

            # Use pending year if still none
            if not year and pending_year:
                year = pending_year

            # If no institution on degree line, check previous line
            if not institution and i > 0:
                prev_line = all_lines[i - 1]
                if not is_employment_line(prev_line):
                    institution = extract_institution(prev_line)
                    if not school:
                        school = extract_school(prev_line)

            # Use pending institution if still none
            if not institution and pending_institution:
                institution = pending_institution
                school = school or pending_school

            for deg_info in degree_infos:
                # Extract dissertation for PhD degrees only
                dissertation = None
                if deg_info['level'] == 'phd':
                    dissertation = extract_dissertation(all_lines, i)

                # If no field found on degree line, check nearby context lines
                field = deg_info['field']
                if not field:
                    field = extract_field_from_context(all_lines, i, deg_info['degree_type']) or ""

                degree = Degree(
                    degree_type=deg_info['degree_type'],
                    level=deg_info['level'],
                    field=field,
                    institution=institution or "",
                    school=school or "",
                    year=year or "",
                    dissertation=dissertation or "",
                    raw_text=line
                )
                record.degrees.append(degree)

            pending_institution = None
            pending_school = None
            pending_year = None
        else:
            # No degree - check if this is an institution line (with year)
            inst = extract_institution(line)
            if inst:
                pending_institution = inst
                pending_school = extract_school(line)
                pending_year = extract_year(line)

    if not record.degrees:
        record.notes.append("No degrees found in education section")

    return record
