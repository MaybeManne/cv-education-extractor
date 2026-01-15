"""
parse_education.py - ULTRA-STRICT EDITION

NON-NEGOTIABLE RULES:
1. NO HALLUCINATION - Only extract explicitly written text in tight context
2. DEGREE-ANCHORED ONLY - No degree token = no record, even if university appears
3. SCHOOL VALIDATION - Must contain University/College/Institute/School OR be on allow-list
4. YEAR VALIDATION - 4 digits 1950-2035 ONLY, no months/dates
5. MULTI-DEGREE HANDLING - Keep separate, don't collapse into fake degrees

EXTRACTION STRATEGY:
- Scan entire document for degree tokens (not just EDUCATION section)
- Tight context window: same line, ±1-2 lines for year/field, ±5 lines for school
- Reject employment lines, publication lines, course headers
- Conservative name extraction from top 15 lines only
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Set


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class Degree:
    """A single degree with explicit fields only."""
    degree_type: str = ""      # e.g., "Ph.D.", "MBA", "B.S."
    field: str = ""            # e.g., "Finance" - ONLY if explicit
    institution: str = ""      # MUST contain University/College/Institute/School
    year: str = ""             # MUST be 4 digits
    level: str = ""            # "phd", "masters", "undergrad"
    line_index: int = 0


@dataclass
class EducationRecord:
    """All education data for a person."""
    name: str = ""
    cv_filename: str = ""
    degrees: List[Degree] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def get_degrees_by_level(self, level: str) -> List[Degree]:
        return [d for d in self.degrees if d.level == level]


# ============================================================================
# DEGREE TOKENS - AUTHORITATIVE LIST
# ============================================================================

DEGREE_PATTERNS = [
    # DOCTORAL
    (r'\bPh\.?\s*D\.?\b', 'Ph.D.', 'phd'),
    (r'\bPHD\b', 'Ph.D.', 'phd'),
    (r'\bD\.?\s*Phil\.?\b', 'D.Phil', 'phd'),
    (r'\bDoctor\s+of\s+Philosophy\b', 'Ph.D.', 'phd'),
    (r'\bD\.?\s*B\.?\s*A\.?\b', 'D.B.A.', 'phd'),
    (r'\bDoctor\s+of\s+Business\s+Administration\b', 'D.B.A.', 'phd'),
    (r'\bEd\.?\s*D\.?\b', 'Ed.D.', 'phd'),
    (r'\bDoctor\s+of\s+Education\b', 'Ed.D.', 'phd'),

    # MASTERS
    (r'\bM\.?\s*B\.?\s*A\.?\b', 'MBA', 'masters'),
    (r'\bMaster\s+of\s+Business\s+Administration\b', 'MBA', 'masters'),
    (r'\bM\.?\s*S\.?\b(?=[\s,\.\)]|$)', 'M.S.', 'masters'),
    (r'\bS\.?\s*M\.?\b(?=[\s,\.\)]|$)', 'S.M.', 'masters'),
    (r'\bMaster\s+of\s+Science\b', 'M.S.', 'masters'),
    (r'\bM\.?\s*Sc\.?\b', 'M.Sc.', 'masters'),
    (r'\bM\.A\.?\b(?=[\s,\.\)]|$)', 'M.A.', 'masters'),
    (r'\bMA\b(?=\s+in\s)', 'M.A.', 'masters'),
    (r'\bMaster\s+of\s+Arts\b', 'M.A.', 'masters'),
    (r'\bM\.?\s*Eng\.?\b', 'M.Eng.', 'masters'),
    (r'\bM\.?\s*Phil\.?\b', 'M.Phil.', 'masters'),
    (r'\bLL\.?\s*M\.?\b', 'LL.M.', 'masters'),
    (r'\bJ\.?\s*D\.?\b', 'J.D.', 'masters'),  # JD is professional masters-level
    (r'\bJuris\s+Doctor\b', 'J.D.', 'masters'),
    (r'\bMPA\b', 'MPA', 'masters'),
    (r'\bM\.?\s*P\.?\s*A\.?\b', 'MPA', 'masters'),
    (r'\bMPP\b', 'MPP', 'masters'),
    (r'\bM\.?\s*P\.?\s*P\.?\b', 'MPP', 'masters'),
    (r'\bMPH\b', 'MPH', 'masters'),
    (r'\bM\.?\s*P\.?\s*H\.?\b', 'MPH', 'masters'),
    (r'\bMEd\b', 'MEd', 'masters'),
    (r'\bM\.?\s*Ed\.?\b', 'MEd', 'masters'),

    # BACHELORS
    (r'\bB\.?\s*S\.?\b(?=[\s,\.\)]|$)', 'B.S.', 'undergrad'),
    (r'\bS\.?\s*B\.?\b(?=[\s,\.\)]|$)', 'S.B.', 'undergrad'),
    (r'\bBachelor\s+of\s+Science\b', 'B.S.', 'undergrad'),
    (r'\bB\.?\s*Sc\.?\b', 'B.Sc.', 'undergrad'),
    (r'\bB\.A\.?\b(?=[\s,\.\)]|$)', 'B.A.', 'undergrad'),
    (r'\bBA\b(?=\s+in\s)', 'B.A.', 'undergrad'),
    (r'\bA\.?\s*B\.?\b(?=[\s,\.\)]|$)', 'A.B.', 'undergrad'),
    (r'\bBachelor\s+of\s+Arts\b', 'B.A.', 'undergrad'),
    (r'\bB\.?\s*E\.?\b(?=\s+in\s|\s*,|\s+[A-Z])', 'B.E.', 'undergrad'),
    (r'\bB\.?\s*Eng\.?\b', 'B.Eng.', 'undergrad'),
    (r'\bBBA\b', 'BBA', 'undergrad'),
    (r'\bB\.?\s*B\.?\s*A\.?\b', 'BBA', 'undergrad'),
    (r'\bB\.?\s*Com\.?\b', 'B.Com.', 'undergrad'),
]

COMPILED_DEGREE_PATTERNS = [
    (re.compile(pattern, re.IGNORECASE), display, level)
    for pattern, display, level in DEGREE_PATTERNS
]


# ============================================================================
# HARD EXCLUSIONS
# ============================================================================

EXCLUSION_PATTERNS = [
    # Employment titles
    r'\b(?:Professor|Assistant\s+Professor|Associate\s+Professor|Adjunct\s+Professor)\b',
    r'\b(?:Lecturer|Instructor|Visiting\s+Professor|Research\s+Professor)\b',
    r'\b(?:Director|Chair|Dean|Manager|Coordinator|Consultant)\b',
    r'\b(?:President|Vice\s+President|Provost|Chancellor)\b',
    r'\bPresent\b.*\d{4}',  # "Present" with year (employment)
    r'\d{4}\s*[-–—]\s*Present\b',  # Year range with Present

    # Employment context
    r'\b(?:taught|teaching|supervised|advising|mentoring)\b',
    r'\b(?:employed|appointed|hired|joined)\b',

    # Publications
    r'\bJournal\s+of\b',
    r'\bpp\.\s*\d+',
    r'\bVol\.\s*\d+',
    r'\bNo\.\s*\d+',
    r'\(\d{4}\)[,\.]?\s*$',  # Citation year at end
    r'\bReview\s+of\b',
    r'\bQuarterly\b',
    r'\bAnnual\b',
    r'\beditors?\b',
    r'\bforthcoming\b',
    r'\bpublished\b',
    r'\bworking\s+paper\b',
    r'\bmanuscript\b',
    r'[""][A-Z]',  # Quoted titles
    r'\band\b.*\band\b.*\band\b',  # Multiple "and" (author lists)
    r',\s*\d{4}\.\s*$',  # Ends with ", year."
    r'\(\s*with\s+',  # "(with" - coauthor
    r'\d+\.\s*\*?[A-Z][a-z]+,',  # "1. *Author," - publication list

    # Course headers and descriptions
    r'\bCourses\s*:\s*$',
    r'\bCourses?\b.*:',
    r'^\s*\w+\s+Courses\s*$',  # "MBA Courses"
    r'\bCourse\s+Modules?\b',
    r'\b(?:MBA|MPA|MPP|Ph\.?D\.?)\s*[-–—]?\s*(?:I|II|III|IV|1|2|3|4)\b',  # "MBA-II"
    r'\bExecutive\s+MBA\b',
    r'\bGlobal\s+(?:Executive\s+)?MBA\b',
    r'\bGEMBA\b',

    # Program mentions (not degrees)
    r'\bPh\.?\s*D\.?\s+program\b',
    r'\bMBA\s+program\b',
    r'\bprogram\s*\([A-Z]+\s+\d+',  # "program (BEPP 941)"
    r'\bused\s+in\b.*\bprograms?\b',

    # Advising/teaching context
    r'\badvisor\b',
    r'\badvise[ed]?\b',
    r'\badvise[er]\b',
    r'\bmentor\b',
    r'\bsupervis\w*\b',
    r'\bstudent\b',
    r'\byear\s+paper\b',
    r'\bPh\.?\s*D\.?\s+(?:Student|Fellow|Candidate)\b',
    r'\bdissertation\s+committee\b',

    # Workshops/training/certifications
    r'\bWorkshop\b',
    r'\bSeminar\b',
    r'\bTraining\b',
    r'\bConference\b',
    r'\bCertificat(?:e|ion)\b',
    r'\bCFA\b(?!\s+Institute)',  # CFA certification (unless "CFA Institute")
    r'\bCFP\b',
    r'\bCPA\b',
    r'\bCMA\b',
    r'\bFRM\b',

    # Committee/service
    r'\bCommittee\b',
    r'\bBoard\b',
    r'\bSenate\b',

    # Dissertation/thesis references
    r'\bDissertation\s*:',
    r'\bThesis\s*:',

    # Awards
    r'\bAward\b',
    r'\bPrize\b',
    r'\bFellow\s+of\b',
    r'\bRecipient\b',
    r'\bScholarship\b',
]

COMPILED_EXCLUSION_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in EXCLUSION_PATTERNS
]


# ============================================================================
# SCHOOL VALIDATION
# ============================================================================

# School must contain one of these OR match allow-list
INSTITUTION_KEYWORDS = {'university', 'college', 'institute', 'school'}

# Known institutions (allow-list for non-standard names)
KNOWN_INSTITUTIONS = {
    'MIT', 'Caltech', 'INSEAD', 'Wharton', 'Kellogg', 'Booth', 'HEC', 'LSE',
    'UCLA', 'NYU', 'USC', 'CUNY', 'SUNY',
}

# Employment tokens that disqualify a school candidate
EMPLOYMENT_TOKENS = {
    'professor', 'assistant', 'associate', 'adjunct', 'visiting',
    'lecturer', 'instructor', 'director', 'chair', 'dean',
    'president', 'provost', 'chancellor', 'coordinator',
    'employed', 'appointed', 'joined', 'present',
}

# Section headers that disqualify a school candidate
SECTION_HEADERS = {
    'education', 'experience', 'employment', 'publications', 'research',
    'teaching', 'awards', 'honors', 'service', 'references', 'grants',
    'activities', 'affiliations', 'memberships', 'certifications',
}

# Course/training tokens that disqualify a school candidate
COURSE_TOKENS = {
    'workshop', 'seminar', 'training', 'conference', 'course', 'module',
    'certificate', 'certification', 'program', 'class',
}


def is_valid_institution(text: str) -> bool:
    """
    STRICT: School must contain University/College/Institute/School OR be on allow-list.
    REJECT if contains employment/section header/course tokens.
    """
    if not text or len(text) < 2:
        return False

    text_lower = text.lower()
    words = set(text_lower.split())

    # HARD REJECT: employment tokens
    if any(token in text_lower for token in EMPLOYMENT_TOKENS):
        return False

    # HARD REJECT: section headers
    if any(header in text_lower for header in SECTION_HEADERS):
        return False

    # HARD REJECT: course tokens
    if any(token in text_lower for token in COURSE_TOKENS):
        return False

    # ACCEPT: contains institution keyword
    if any(kw in text_lower for kw in INSTITUTION_KEYWORDS):
        return True

    # ACCEPT: matches known institution
    if any(known in text for known in KNOWN_INSTITUTIONS):
        return True

    return False


def extract_institution_strict(text: str) -> str:
    """
    STRICT: Extract institution name from text.
    Returns clean school name or empty string.
    """
    if not text:
        return ""

    # Try known institutions first
    for known in KNOWN_INSTITUTIONS:
        if re.search(rf'\b{re.escape(known)}\b', text):
            return known

    # Pattern 1: "University of X" (most common)
    match = re.search(
        r'(University\s+of\s+[A-Z][a-z]+(?:[-\s]+[A-Z][a-z]+)?(?:,\s*[A-Z][a-z]+)?)',
        text
    )
    if match:
        inst = match.group(1).strip()
        inst = clean_institution(inst)
        if inst and is_valid_institution(inst):
            return inst

    # Pattern 2: "X University"
    match = re.search(
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}\s+University)',
        text
    )
    if match:
        inst = match.group(1).strip()
        inst = clean_institution(inst)
        if inst and is_valid_institution(inst):
            return inst

    # Pattern 3: "X State University"
    match = re.search(
        r'([A-Z][a-z]+\s+State\s+University)',
        text
    )
    if match:
        inst = match.group(1).strip()
        inst = clean_institution(inst)
        if inst and is_valid_institution(inst):
            return inst

    # Pattern 4: "X Institute of Technology"
    match = re.search(
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\s+Institute\s+of\s+Technology)',
        text
    )
    if match:
        inst = match.group(1).strip()
        inst = clean_institution(inst)
        if inst and is_valid_institution(inst):
            return inst

    # Pattern 5: "X College"
    match = re.search(
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}\s+College)',
        text
    )
    if match:
        inst = match.group(1).strip()
        inst = clean_institution(inst)
        if inst and is_valid_institution(inst):
            return inst

    # Pattern 6: "X School of Business/Law/etc."
    match = re.search(
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\s+School(?:\s+of\s+[A-Z][a-z]+)?)',
        text
    )
    if match:
        inst = match.group(1).strip()
        inst = clean_institution(inst)
        if inst and is_valid_institution(inst):
            return inst

    return ""


def clean_institution(inst: str) -> str:
    """Clean institution name."""
    if not inst:
        return ""

    # Remove leading/trailing whitespace and punctuation
    inst = inst.strip(' \t\n\r.,;:()[]{}"\'-')

    # Remove years at the end
    inst = re.sub(r'[\s,]+\d{4}\s*$', '', inst)
    inst = re.sub(r'[\s,]+\d{4}\s*[-–—]\s*\d{2,4}\s*$', '', inst)

    # Remove months at the end
    inst = re.sub(
        r'[\s,]+(?:January|February|March|April|May|June|July|August|'
        r'September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|'
        r'Jul|Aug|Sep|Sept|Oct|Nov|Dec)[\s,]*\d*\s*$',
        '', inst, flags=re.IGNORECASE
    )

    # Remove degree abbreviations at the end
    inst = re.sub(
        r'[\s,]+(?:Ph\.?D\.?|MBA|M\.?S\.?|M\.?A\.?|B\.?S\.?|B\.?A\.?|J\.?D\.?)\s*$',
        '', inst, flags=re.IGNORECASE
    )

    # Remove parenthetical content at the end
    inst = re.sub(r'\s*\([^)]*\)\s*$', '', inst)

    # Remove honors/distinctions
    inst = re.sub(
        r'[\s,]+(?:summa|magna|cum\s+laude|with\s+honors?|with\s+distinction)\s*$',
        '', inst, flags=re.IGNORECASE
    )

    # Clean up multiple spaces
    inst = re.sub(r'\s+', ' ', inst)
    inst = inst.strip(' \t\n\r.,;:()[]{}"\'-')

    return inst


# ============================================================================
# YEAR VALIDATION - STRICT 4 DIGITS ONLY
# ============================================================================

def extract_year_strict(text: str) -> str:
    """
    STRICT: Extract 4-digit year between 1950-2035 ONLY.
    If range found, take end year.
    NEVER extract months/dates.
    """
    # Year range: take end year
    range_match = re.search(
        r'(19[5-9]\d|20[0-3]\d)\s*[-–—]\s*(19[5-9]\d|20[0-3]\d)',
        text
    )
    if range_match:
        return range_match.group(2)

    # Standalone 4-digit years
    years = re.findall(r'\b(19[5-9]\d|20[0-3]\d)\b', text)

    # Filter out years that are part of longer numbers
    valid_years = []
    for year in years:
        idx = text.find(year)
        # Check not surrounded by digits
        if idx > 0 and text[idx-1].isdigit():
            continue
        if idx + 4 < len(text) and text[idx+4].isdigit():
            continue
        valid_years.append(year)

    if valid_years:
        # Return last year (usually graduation year)
        return valid_years[-1]

    return ""


# ============================================================================
# FIELD EXTRACTION - CONSERVATIVE
# ============================================================================

def extract_field_strict(text: str, degree_type: str) -> str:
    """
    STRICT: Extract field only if explicitly tied to degree.
    Patterns: "Degree in Field", "Degree, Concentration in Field", "Degree Field,"
    """
    # Make degree pattern flexible: MBA matches M.B.A. and vice versa
    # Replace each letter with letter + optional dot
    degree_flex = ''
    for char in degree_type:
        if char.isalpha():
            degree_flex += char + r'\.?\s*'
        elif char == '.':
            continue  # Skip dots in input
        else:
            degree_flex += re.escape(char)
    degree_flex = degree_flex.rstrip(r'\s*')  # Remove trailing \s*

    # Pattern 1: "Degree in Field"
    match = re.search(
        rf'{degree_flex}\s+(?:in|of)\s+([A-Za-z][A-Za-z\s&/\-]+?)(?:,|;|\s+\d{{4}}|\s+(?:University|College|Institute|School|from|at)|\s*$)',
        text, re.IGNORECASE
    )
    if match:
        field = match.group(1).strip()
        if is_valid_field(field):
            return clean_field(field)

    # Pattern 2: "Degree, Concentration in Field" (common MBA format)
    match = re.search(
        rf'{degree_flex}\s*,\s*Concentration\s+in\s+([A-Za-z][A-Za-z\s&/\-]+?)(?:,|\s+\d{{4}}|\s+(?:University|College|Institute|School)|\s*$)',
        text, re.IGNORECASE
    )
    if match:
        field = match.group(1).strip()
        if is_valid_field(field):
            return clean_field(field)

    # Pattern 3: "Degree Field,"
    match = re.search(
        rf'{degree_flex}\s+([A-Za-z][A-Za-z\s&/\-]+?)\s*,\s*[A-Z]',
        text, re.IGNORECASE
    )
    if match:
        field = match.group(1).strip()
        if is_valid_field(field):
            return clean_field(field)

    # Pattern 4: "Degree, Field"
    match = re.search(
        rf'{degree_flex}\s*,\s*([A-Za-z][A-Za-z\s&/\-]+?)(?:,|\s+\d{{4}}|\s+(?:University|College|Institute|School)|\s*$)',
        text, re.IGNORECASE
    )
    if match:
        field = match.group(1).strip()
        # Skip if it's "Concentration in X" - we handle that above
        if 'concentration' in field.lower():
            return ""
        if is_valid_field(field):
            return clean_field(field)

    return ""


def is_valid_field(field: str) -> bool:
    """Validate field is a real academic discipline."""
    if not field or len(field) < 3 or len(field) > 60:
        return False

    field_lower = field.lower()

    # REJECT: institution keywords
    if any(kw in field_lower for kw in INSTITUTION_KEYWORDS):
        return False

    # REJECT: employment/service terms
    reject_terms = {
        'professor', 'assistant', 'associate', 'director', 'chair', 'dean',
        'committee', 'board', 'faculty', 'department',
        'workshop', 'seminar', 'training', 'conference',
        'present', 'current', 'ongoing', 'employment', 'experience',
        'course', 'module', 'level', 'fellow', 'student',
        'advisor', 'adviser', 'mentor', 'supervisor',
        'core', 'modules',  # Reject "Core", "Course Modules" but NOT "concentration"
    }
    if any(term in field_lower for term in reject_terms):
        return False

    # REJECT: honors (not a field)
    if any(h in field_lower for h in ['summa', 'magna', 'cum laude', 'honors']):
        return False

    # REJECT: too many words (likely captured extra text)
    if len(field.split()) > 6:
        return False

    return True


def clean_field(field: str) -> str:
    """Clean extracted field."""
    field = re.sub(r'^(?:in|of|the)\s+', '', field, flags=re.IGNORECASE)
    field = re.sub(r'\s+(?:from|at|in)\s*$', '', field, flags=re.IGNORECASE)
    field = re.sub(r'\s+', ' ', field).strip()
    return field


# ============================================================================
# NAME EXTRACTION - CONSERVATIVE
# ============================================================================

def extract_name_strict(text: str) -> str:
    """
    CONSERVATIVE: Extract name from first 15 lines only.
    REJECT lines with: digits, @, http, addresses, university words, department.
    ACCEPT only: 2-5 words, mostly alphabetic.
    """
    lines = text.strip().split('\n')

    # Reject patterns
    reject_patterns = [
        r'curriculum\s+vita',
        r'\bcv\b',
        r'\bresume\b',
        r'\bprofessor\b',
        r'\bdirector\b',
        r'\bdepartment\b',
        r'\buniversity\b',
        r'\bcollege\b',
        r'\bschool\b',
        r'\beducation\b',
        r'\bexperience\b',
        r'@',
        r'\d{3}[-.\s]?\d{3}',  # phone
        r'\d{5}',  # zip code
        r'http',
        r'www\.',
        r'\bstreet\b',
        r'\bst\.\b',
        r'\bavenue\b',
        r'\bave\.\b',
        r'\broad\b',
        r'\brd\.\b',
        r'\bblvd\b',
        r'\bbuilding\b',
        r'\bsuite\b',
        r'\broom\b',
    ]

    for line in lines[:15]:
        line = line.strip()
        if not line or len(line) < 5:
            continue

        # Skip if matches reject pattern
        if any(re.search(p, line, re.IGNORECASE) for p in reject_patterns):
            continue

        # Remove date suffixes
        clean_line = re.sub(
            r'\s*(?:Revised|Updated)\s*:\s*\w+,?\s*\d{4}',
            '', line, flags=re.IGNORECASE
        )
        clean_line = re.sub(
            r'\s*(?:January|February|March|April|May|June|July|August|'
            r'September|October|November|December)\s*,?\s*\d{4}\s*$',
            '', clean_line, flags=re.IGNORECASE
        )
        clean_line = clean_line.strip()

        # Must be 2-5 words
        words = clean_line.split()
        if not (2 <= len(words) <= 5):
            continue

        # Must be mostly letters
        alpha_count = sum(1 for c in clean_line if c.isalpha() or c.isspace() or c in '.-,\'')
        if alpha_count / max(len(clean_line), 1) < 0.85:
            continue

        # Remove credentials
        name = re.sub(
            r',?\s*(?:Ph\.?D\.?|MBA|M\.?D\.?|J\.?D\.?|CPA|CFA|CFP).*$',
            '', clean_line, flags=re.IGNORECASE
        )
        name = name.strip(' ,.;:')

        if len(name.split()) >= 2:
            return name

    return ""


# ============================================================================
# CORE EXTRACTION - DEGREE-ANCHORED
# ============================================================================

def find_degrees_strict(text: str) -> List[Tuple[int, str, str, str]]:
    """
    STRICT: Find degree tokens line by line.
    SKIP lines matching exclusion patterns.
    Returns: [(line_index, degree_type, level, line_text), ...]
    """
    lines = text.split('\n')
    found = []

    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue

        # HARD FILTER: Skip exclusion patterns
        if any(p.search(line) for p in COMPILED_EXCLUSION_PATTERNS):
            continue

        # Check for degree patterns
        for pattern, display, level in COMPILED_DEGREE_PATTERNS:
            if pattern.search(line):
                found.append((i, display, level, line))
                break  # Only one degree per line

    return found


def extract_degree_with_context(
    lines: List[str],
    line_idx: int,
    degree_type: str,
    level: str
) -> Degree:
    """
    STRICT: Extract degree with tight context windows.

    School: Look up to 5 lines above (school often appears once before multiple degrees)
    Year/Field: Tight context (same line, ±1 line)
    """
    current_line = lines[line_idx]

    # Tight context for year/field (±1 line)
    tight_context_lines = []
    if line_idx > 0:
        tight_context_lines.append(lines[line_idx - 1])
    tight_context_lines.append(current_line)
    if line_idx < len(lines) - 1:
        tight_context_lines.append(lines[line_idx + 1])
    tight_context = ' '.join(tight_context_lines)

    # Extract institution (same line first, then look back)
    institution = extract_institution_strict(current_line)

    if not institution:
        # Look up to 5 lines above for school
        # Stop at section headers
        section_headers = {'employment', 'experience', 'publications', 'research',
                          'teaching', 'awards', 'service', 'references', 'grants'}
        for i in range(1, 6):
            if line_idx - i < 0:
                break
            prev_line = lines[line_idx - i].strip()
            prev_lower = prev_line.lower()

            # Stop at section headers
            if any(header in prev_lower for header in section_headers):
                break

            inst = extract_institution_strict(prev_line)
            if inst:
                institution = inst
                break

    # Extract year (STRICT - 4 digits only)
    year = extract_year_strict(current_line)
    if not year:
        year = extract_year_strict(tight_context)

    # Extract field (STRICT - explicit only)
    field = extract_field_strict(current_line, degree_type)
    if not field:
        field = extract_field_strict(tight_context, degree_type)

    return Degree(
        degree_type=degree_type,
        level=level,
        institution=institution,
        field=field,
        year=year,
        line_index=line_idx
    )


def deduplicate_degrees(degrees: List[Degree]) -> List[Degree]:
    """
    Remove duplicate degrees.
    Signature includes field to handle multiple BS/BA from same school in same year.
    """
    seen = set()
    unique = []

    for d in degrees:
        sig = f"{d.degree_type}|{d.level}|{d.field.lower() if d.field else ''}|{d.institution.lower() if d.institution else ''}|{d.year}"
        if sig not in seen:
            seen.add(sig)
            unique.append(d)

    return unique


def select_best_degrees(degrees: List[Degree]) -> List[Degree]:
    """
    Select best degrees per level.

    Rules:
    - Undergrad: up to 2, sorted by year
    - Masters: up to 2, sorted by year
    - PhD: 1 (most complete: school+year beats just degree)
    """
    undergrad = [d for d in degrees if d.level == 'undergrad']
    masters = [d for d in degrees if d.level == 'masters']
    phd = [d for d in degrees if d.level == 'phd']

    # Sort by year (ascending)
    undergrad.sort(key=lambda d: (d.year if d.year else '9999'))
    masters.sort(key=lambda d: (d.year if d.year else '9999'))

    # For PhD, select most complete
    if phd:
        # Score: school+year = 2, school or year = 1, neither = 0
        def phd_score(d):
            score = 0
            if d.institution:
                score += 1
            if d.year:
                score += 1
            return score

        phd.sort(key=lambda d: (-phd_score(d), d.year if d.year else '9999'))

    selected = []
    selected.extend(undergrad[:2])
    selected.extend(masters[:2])
    if phd:
        selected.append(phd[0])

    return selected


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def parse_education(text: str, filename: str = "") -> EducationRecord:
    """
    STRICT: Parse education from CV text.
    Only extracts explicit, validated information.
    """
    record = EducationRecord(cv_filename=filename)

    if not text:
        record.notes.append("No text provided")
        return record

    # Minimal preprocessing
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)  # Fix CamelCase
    text = re.sub(r'(\w)(19\d{2}|20\d{2})', r'\1 \2', text)  # Fix year stuck to word
    text = re.sub(r' {2,}', ' ', text)  # Fix multiple spaces

    # Extract name (CONSERVATIVE)
    record.name = extract_name_strict(text)

    # Find all degree mentions (DEGREE-ANCHORED)
    lines = text.split('\n')
    degree_matches = find_degrees_strict(text)

    # Extract details for each degree
    degrees = []
    for line_idx, degree_type, level, _ in degree_matches:
        degree = extract_degree_with_context(lines, line_idx, degree_type, level)

        # CRITICAL: Only keep if we have BOTH degree AND school
        # A degree without a school is useless per requirements
        if degree.degree_type and degree.institution:
            degrees.append(degree)

    # Deduplicate
    degrees = deduplicate_degrees(degrees)

    # Select best degrees per level
    degrees = select_best_degrees(degrees)

    # Sort by level and year
    level_order = {'phd': 0, 'masters': 1, 'undergrad': 2}
    degrees.sort(key=lambda d: (level_order.get(d.level, 3), d.year if d.year else '9999'))

    record.degrees = degrees

    # Add note if no education found
    if not degrees:
        record.notes.append("NO EDUCATION FOUND (unexpected)")

    return record
