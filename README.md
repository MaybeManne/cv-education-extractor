## CV Education Extractor ✅ 

This repo takes a folder of **academic CV PDFs** and outputs a single CSV with each person’s **education**:
- **Undergrad / Master’s / PhD**
- **Where they studied** (institution, and when available: school/college)
- **Extra context (optional but helpful):** degree type, field, year, PhD dissertation (only if explicitly stated)

It runs **100% locally** (no APIs, no ML calls), so it’s deterministic and easy to audit.

**Input:** `data/raw_cvs/`  
**Run:** `python3 src/run_pipeline.py`  
**Output:** `data/output/education.csv`

---

## Repo structure (what each file is doing)

- `src/run_pipeline.py` — orchestrates the whole run: load PDFs → extract text → parse education → write CSV
- `src/extract_text.py` — PDF → text extraction + cleanup
- `src/parse_education.py` — the parsing logic (find education block, detect degrees, attach details)
- `src/utils.py` — file discovery, CSV writing, formatting, lightweight validation + summary printing
- `requirements.txt` — dependencies (main one is `pdfplumber`)

---

## How it works 

### 1) PDF → clean text (`extract_text.py`)
- Uses `pdfplumber` to read each PDF page and call `page.extract_text()`.
- Then `_clean_page_text()` normalizes the raw output:
  - collapses multi-spaces into single spaces
  - replaces weird PDF dash characters with standard `-`
  - strips control characters that can break regex parsing
  - normalizes newlines and removes excessive blank lines
- Pages are joined with `\n\n` so we preserve boundaries without losing readability.

Why this matters: PDF text extraction often produces “almost text” (random spacing and characters). Cleaning makes the parser consistent across different CV layouts.

---

### 2) Locate the Education section first (`parse_education.py`)
Instead of scanning the entire CV (which is noisy), `find_education_section()`:
- searches for headers like `EDUCATION`, `EARNED DEGREES`, `ACADEMIC BACKGROUND`, etc.
- stops when it hits the next major header like `EXPERIENCE`, `POSITIONS`, `PUBLICATIONS`, etc.
- returns just that “education block” text

Why: universities show up in employment (e.g., “Professor at University of X”). Section isolation is the main thing preventing false positives.

---

### 3) Degree-first parsing 
Inside the education block, the parser loops line-by-line and looks for explicit degree tokens using `DEGREE_PATTERNS`:
- PhD/DBA → `phd`
- MBA/MS/MA/MPhil/Licentiaat → `masters`
- BA/BS/BSc/BEng/BTech/AB/Kandidaat → `undergrad`

Each hit creates a `Degree` object (dataclass) with fields:
`degree_type, level, institution, school, field, year, dissertation, raw_text`

Why: institution names can be ambiguous (“Booth”, “Graduate School”), but degree markers are a reliable anchor. Also: patterns are written to avoid common false matches (ex: don’t match `BA` inside `MBA`).

---

### 4) Attach details with “nearby context” rules
CV formatting is inconsistent, so after detecting a degree line, the parser tries to attach metadata from:
- the same line
- the previous line (common when the institution is on its own line)
- a few following lines (common when field is written as “Concentration:” etc.)

Specifically:
- `extract_institution()` grabs institution names with patterns like:
  - “University of X”
  - “X University”
  - “X College”
  - plus a few special-case patterns (MIT, Texas A&M, etc.)
  - supports *compound* institutions like “X University – Y University” → stored as `X / Y`
- `extract_school()` looks for business school names (Wharton, Booth, Kellogg, etc.)
- `extract_field()` handles common degree formats:
  - `Ph.D. in Marketing`
  - `MBA, Strategy and Marketing`
  - `BA, Political Science`
  - plus foreign phrasing like `Licentiaat in de Psychologie`
- `extract_field_from_context()` catches cases where field is on a separate line:
  - `Concentration: Experimental Psychology`
  - `Academic Area: ...`
- `extract_year()` handles single years and ranges:
  - If it’s a range like `2008–2012`, it uses the **end year** as completion year.

There’s also a “pending context” mechanism:
- if a line has an institution/year but no degree, it stores it as pending
- the next degree line can inherit those values (fixes many multi-line CV formats)

---

### 5) Employment filtering (important for mixed timelines)
Some CVs mix employment and education in one timeline section. `is_employment_line()` flags likely job lines (Professor titles, “Present”, date ranges) and skips them unless they also contain a degree token.

Why: prevents accidentally reading employers as schools.

---

### 6) Dissertation extraction (explicit only)
For PhD entries, `extract_dissertation()` only captures a dissertation when it’s clearly labeled:
- `Dissertation: ...`
- `Thesis: ...`
- `Topic: ...`
- or a quoted title immediately near the PhD line

If it’s not explicit, it stays blank (no guessing).

---

### 7) Output + sanity checks (`utils.py`)
`write_csv()` writes:
- `name`
- `cv_filename`
- `phd`, `masters`, `undergrad` (multiple degrees separated by ` | `)
- `notes` (missing degree levels, parsing issues, validation warnings)

`validate_record()` adds a light warning if the same institution appears across multiple degree levels (sometimes legit, sometimes worth re-checking).

---

## Oddities / red flags in this specific set ⚠️

- **Omar Rodriguez-Vila**  
  Degrees were listed with **start–end ranges** (not single years). The parser uses the **end year** as completion year to keep output consistent.

- **Donald D. Eisenstein**  
  Education is embedded inside an “Employment and Education” timeline, with job entries interleaved and not strictly in chronological order. This is exactly why the pipeline:
  - isolates the education block
  - filters employment-like lines
  - anchors on explicit degree patterns

- **Meyvis**  
  Non-US degree titles (`Licentiaat`, `Kandidaat`) and key details split across lines (e.g., `Concentration:` line after the degree). The parser handles this using:
  - foreign-degree patterns
  - context lookup across nearby lines

Overall, the main “gotcha” across the 10 CVs wasn’t missing education—it was **format variance** (timelines, multi-line entries, foreign degree naming). The code is built around those failure modes so it generalizes beyond this batch.
