"""
heuristics.py  ─  Constraint maps and fuzzy-matching helpers for the IMS scraper.

Responsibilities
────────────────
1. Static knowledge: DEGREE_TO_DEPARTMENTS, DEPARTMENT_TO_SPECIALIZATIONS,
   DEGREE_TO_SPECIALIZATIONS
2. String normalisation / fuzzy matching
3. A HeuristicsCache that learns from successful scrapes and persists to disk.
4. A Blacklist that prunes department×degree pairs that consistently return nothing.
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from pathlib import Path
from typing import Optional

# ─────────────────────────────────────────────────────────────────────────────
# 1.  Static constraint maps
# ─────────────────────────────────────────────────────────────────────────────

# Which departments are plausible for each degree?
# Keys are normalised forms (upper-case, no punctuation, collapsed).
# Multiple keys may point to the same department list (abbreviation + expanded form).
_BACHELOR_DEPTS = [
    "COMPUTER SCIENCE AND ENGINEERING",
    "INFORMATION TECHNOLOGY",
    "MECHANICAL ENGINEERING",
    "ELECTRICAL ENGINEERING",
    "CIVIL ENGINEERING",
    "ELECTRONICS AND COMMUNICATION ENGINEERING",
]
_MASTER_TECH_DEPTS = [
    "COMPUTER SCIENCE AND ENGINEERING",
    "ELECTRONICS AND COMMUNICATION ENGINEERING",
    "MECHANICAL ENGINEERING",
    "INFORMATION TECHNOLOGY",
]
# B.F.Tech = Bachelor of Fine Technology → Faculty of Architecture, Planning & Design
_BFTECH_DEPTS = [
    "ARCHITECTURE",
    "ARCHITECTURE AND SUSTAINABLE DESIGN",
    "APPLIED ARTS",
    "DESIGN",
    "INDUSTRIAL DESIGN",
    "FACULTY OF ARCHITECTURE",
    "FACULTY OF ARCHITECTURE AND SUSTAINABLE DESIGN",
]

DEGREE_TO_DEPARTMENTS: dict[str, list[str]] = {
    # ── Bachelor of Engineering / Technology ───────────────────────────────
    "BE":                               _BACHELOR_DEPTS,
    "BTECH":                            _BACHELOR_DEPTS,
    "BACHELOR OF ENGINEERING":          _BACHELOR_DEPTS,
    "BACHELOR OF TECHNOLOGY":           _BACHELOR_DEPTS,
    "BACHELOR OF ENGINEERING FULLTIME": _BACHELOR_DEPTS,
    "BACHELOR OF TECHNOLOGY FULLTIME":  _BACHELOR_DEPTS,
    # ── B.F.Tech = Bachelor of Fine Technology  (Architecture / Design faculty)
    # NOT the same as B.Tech — completely different faculty at NSIT
    "BFTECH":                           _BFTECH_DEPTS,
    "BACHELOR OF FINE TECHNOLOGY":      _BFTECH_DEPTS,
    # ── Master of Technology ───────────────────────────────────────────────
    "MTECH":                        _MASTER_TECH_DEPTS,
    "MASTER OF TECHNOLOGY":         _MASTER_TECH_DEPTS,
    # ── MBA ────────────────────────────────────────────────────────────────
    "MBA": [
        "MANAGEMENT STUDIES",
        "BUSINESS ADMINISTRATION",
    ],
    "MASTER OF BUSINESS ADMINISTRATION": [
        "MANAGEMENT STUDIES",
        "BUSINESS ADMINISTRATION",
    ],
    # ── MCA ────────────────────────────────────────────────────────────────
    "MCA": [
        "COMPUTER SCIENCE AND ENGINEERING",
        "INFORMATION TECHNOLOGY",
        "COMPUTER APPLICATIONS",
    ],
    "MASTER OF COMPUTER APPLICATIONS": [
        "COMPUTER SCIENCE AND ENGINEERING",
        "INFORMATION TECHNOLOGY",
        "COMPUTER APPLICATIONS",
    ],
}

DEPARTMENT_TO_SPECIALIZATIONS: dict[str, list[str]] = {
    "COMPUTER SCIENCE AND ENGINEERING": [
        "COMPUTER SCIENCE AND ENGINEERING",
        "ARTIFICIAL INTELLIGENCE",
        "DATA SCIENCE",
        "BIG DATA ANALYTICS",
        "INTERNET OF THINGS",
        "CLOUD COMPUTING",
        "CYBER SECURITY",
    ],
    "INFORMATION TECHNOLOGY": [
        "INFORMATION TECHNOLOGY",
        "INFORMATION TECHNOLOGY INTERNET OF THINGS",
        "INFORMATION TECHNOLOGY NETWORK AND INFORMATION SECURITY",
        "INFORMATION TECHNOLOGY IOT",
    ],
    "MECHANICAL ENGINEERING": [
        "MECHANICAL ENGINEERING",
        "MANUFACTURING ENGINEERING",
        "THERMAL ENGINEERING",
        "INDUSTRIAL ENGINEERING",
    ],
    "ELECTRICAL ENGINEERING": [
        "ELECTRICAL ENGINEERING",
        "POWER SYSTEMS",
        "CONTROL SYSTEMS",
    ],
    "ELECTRONICS AND COMMUNICATION ENGINEERING": [
        "ELECTRONICS AND COMMUNICATION ENGINEERING",
        "VLSI DESIGN",
        "EMBEDDED SYSTEMS",
        "SIGNAL PROCESSING",
    ],
    "CIVIL ENGINEERING": [
        "CIVIL ENGINEERING",
        "STRUCTURAL ENGINEERING",
        "ENVIRONMENTAL ENGINEERING",
    ],
    "MANAGEMENT STUDIES": [
        "MANAGEMENT STUDIES",
        "FINANCE",
        "MARKETING",
        "HUMAN RESOURCE MANAGEMENT",
        "OPERATIONS MANAGEMENT",
    ],
    "BUSINESS ADMINISTRATION": [
        "BUSINESS ADMINISTRATION",
    ],
    "COMPUTER APPLICATIONS": [
        "COMPUTER APPLICATIONS",
    ],
    # ── Architecture / Design faculty  (B.F.Tech) ──────────────────────────
    "ARCHITECTURE": [
        "ARCHITECTURE",
        "ARCHITECTURE AND SUSTAINABLE DESIGN",
    ],
    "ARCHITECTURE AND SUSTAINABLE DESIGN": [
        "ARCHITECTURE AND SUSTAINABLE DESIGN",
        "ARCHITECTURE",
        "SUSTAINABLE DESIGN",
        "URBAN DESIGN",
        "LANDSCAPE ARCHITECTURE",
    ],
    "APPLIED ARTS": [
        "APPLIED ARTS",
        "VISUAL COMMUNICATION",
        "GRAPHIC DESIGN",
        "PRODUCT DESIGN",
    ],
    "DESIGN": [
        "DESIGN",
        "INDUSTRIAL DESIGN",
        "PRODUCT DESIGN",
        "COMMUNICATION DESIGN",
    ],
    "INDUSTRIAL DESIGN": [
        "INDUSTRIAL DESIGN",
        "PRODUCT DESIGN",
    ],
    "FACULTY OF ARCHITECTURE": [
        "ARCHITECTURE",
        "ARCHITECTURE AND SUSTAINABLE DESIGN",
        "URBAN PLANNING",
    ],
    "FACULTY OF ARCHITECTURE AND SUSTAINABLE DESIGN": [
        "ARCHITECTURE AND SUSTAINABLE DESIGN",
        "SUSTAINABLE DESIGN",
        "URBAN PLANNING",
        "LANDSCAPE ARCHITECTURE",
    ],
}

# Quick reverse index: degree → flattened set of specs
DEGREE_TO_SPECIALIZATIONS: dict[str, list[str]] = {}
for _deg, _depts in DEGREE_TO_DEPARTMENTS.items():
    _specs: list[str] = []
    for _dept in _depts:
        _specs.extend(DEPARTMENT_TO_SPECIALIZATIONS.get(_dept, []))
    DEGREE_TO_SPECIALIZATIONS[_deg] = list(dict.fromkeys(_specs))   # dedup, stable order


# ─────────────────────────────────────────────────────────────────────────────
# 2.  String normalisation & fuzzy matching
# ─────────────────────────────────────────────────────────────────────────────

# Tokens to strip that never add discriminating information
_NOISE_TOKENS = frozenset({
    "AND", "OF", "THE", "IN", "FOR", "A", "AN",
    # Campus / intake / mode suffixes common in NSIT dropdowns
    "EAST", "WEST", "NORTH", "SOUTH", "EVENING", "MORNING",
    "SHIFT", "I", "II", "III",
    # Full-time / part-time qualifiers  (e.g. "B.F.Tech (Full Time)")
    "FULL", "PART", "TIME", "FT", "PT",
})

# Dots between/after word-characters (abbreviations like B.E., M.Tech) → strip only the dot
_ABBREV_DOT_RE = re.compile(r'(?<=\w)\.(?=\w)|(?<=\w)\.(?=\s|$)')
# Any remaining non-word, non-space characters → single space
_PUNCT_RE = re.compile(r"[^\w\s]")
_SPACE_RE = re.compile(r"\s+")


def normalize(text: str, *, strip_noise: bool = False) -> str:
    """
    Normalise a dropdown label for comparison.

    Steps:
        1. Unicode → ASCII (strip accents)
        2. Upper-case
        3. Remove dots that are part of abbreviations (B.E. → BE, M.Tech → MTECH)
        4. Replace remaining punctuation with spaces
        5. Collapse whitespace
        6. Optionally remove noise tokens (useful for looser matching)

    Examples
    ────────
    "COMPUTER SCIENCE AND ENGINEERING (EAST)"  → "COMPUTER SCIENCE AND ENGINEERING EAST"
    "B.E."                                      → "BE"
    "M.Tech"                                    → "MTECH"
    "Computer Science & Engg. (East)"          → "COMPUTER SCIENCE ENGG EAST"
    """
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.upper()
    # Strip dots in abbreviations without introducing spaces (B.E. → BE)
    text = _ABBREV_DOT_RE.sub("", text)
    # Replace remaining punctuation (parens, &, commas, etc.) with a space
    text = _PUNCT_RE.sub(" ", text)
    text = _SPACE_RE.sub(" ", text).strip()
    if strip_noise:
        text = " ".join(w for w in text.split() if w not in _NOISE_TOKENS)
    return text


def _token_set(text: str) -> set[str]:
    return set(normalize(text, strip_noise=True).split())


def fuzzy_match(candidate: str, reference_list: list[str], threshold: float = 0.60) -> Optional[str]:
    """
    Return the best match from *reference_list* for *candidate*, or None.

    Scoring = Jaccard similarity on normalised token sets, ignoring noise.
    A match is accepted only when score ≥ threshold.
    """
    c_tokens = _token_set(candidate)
    if not c_tokens:
        return None

    best_score = 0.0
    best_ref   = None

    for ref in reference_list:
        r_tokens = _token_set(ref)
        if not r_tokens:
            continue
        intersection = len(c_tokens & r_tokens)
        union        = len(c_tokens | r_tokens)
        score        = intersection / union if union else 0.0
        if score > best_score:
            best_score = score
            best_ref   = ref

    return best_ref if best_score >= threshold else None


def match_degree(raw_degree: str) -> Optional[str]:
    """Return the best key from DEGREE_TO_DEPARTMENTS that matches raw_degree."""
    return fuzzy_match(raw_degree, list(DEGREE_TO_DEPARTMENTS.keys()), threshold=0.50)


def allowed_departments_for_degree(raw_degree: str) -> list[str]:
    """
    Return the list of normalised department names that are allowed for a degree.
    Uses fuzzy key lookup; falls back to empty list when degree is unknown.
    """
    key = match_degree(raw_degree)
    return DEGREE_TO_DEPARTMENTS.get(key, []) if key else []


def is_department_allowed(raw_dept: str, raw_degree: str) -> bool:
    """True when raw_dept fuzzy-matches one of the allowed departments for raw_degree."""
    allowed = allowed_departments_for_degree(raw_degree)
    if not allowed:
        # Unknown degree → permit everything (safe fallback)
        return True
    return fuzzy_match(raw_dept, allowed, threshold=0.55) is not None


def allowed_specs_for_department(raw_dept: str) -> list[str]:
    """Return specialisation list for a department, or [] when unknown."""
    known = list(DEPARTMENT_TO_SPECIALIZATIONS.keys())
    key = fuzzy_match(raw_dept, known, threshold=0.55)
    return DEPARTMENT_TO_SPECIALIZATIONS.get(key, []) if key else []


def is_spec_allowed(raw_spec: str, raw_dept: str) -> bool:
    """True when raw_spec fuzzy-matches an allowed specialisation for raw_dept."""
    allowed = allowed_specs_for_department(raw_dept)
    if not allowed:
        return True   # unknown dept → permit everything
    return fuzzy_match(raw_spec, allowed, threshold=0.50) is not None


# ─────────────────────────────────────────────────────────────────────────────
# 3.  Learned-heuristics cache  (auto-learning from successful scrapes)
# ─────────────────────────────────────────────────────────────────────────────

_DEFAULT_CACHE_PATH = os.path.expanduser("~/ims_scraper_outputs/heuristics_cache.json")


class HeuristicsCache:
    """
    Persists learned (dept → degree) and (dept → spec) associations so that
    future runs can skip impossible combinations from the very first request.

    Schema
    ──────
    {
      "dept_to_degrees":  { "<NORM_DEPT>": ["<NORM_DEG>", ...] },
      "dept_to_specs":    { "<NORM_DEPT>": ["<NORM_SPEC>", ...] },
      "degree_to_depts":  { "<NORM_DEG>":  ["<NORM_DEPT>", ...] }
    }
    """

    def __init__(self, path: str = _DEFAULT_CACHE_PATH):
        self.path = path
        self._data: dict = {
            "dept_to_degrees":  {},
            "dept_to_specs":    {},
            "degree_to_depts":  {},
        }
        self._dirty = False
        self._load()

    # ── Persistence ──────────────────────────────────────────────────────────

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, encoding="utf-8") as f:
                    loaded = json.load(f)
                for key in self._data:
                    if key in loaded:
                        self._data[key] = loaded[key]
                print(f"📖  Heuristics cache loaded from {self.path}")
            except Exception as e:
                print(f"⚠️   Could not read heuristics cache: {e}")

    def save(self, force: bool = False):
        if not (self._dirty or force):
            return
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
            self._dirty = False
        except Exception as e:
            print(f"⚠️   Could not save heuristics cache: {e}")

    # ── Learning ─────────────────────────────────────────────────────────────

    def record_success(self, raw_dept: str, raw_degree: str, raw_spec: str):
        """Call this whenever a combination produces a valid timetable."""
        dept   = normalize(raw_dept)
        degree = normalize(raw_degree)
        spec   = normalize(raw_spec) if raw_spec else None

        def _add(mapping: dict, key: str, val: str):
            if val not in mapping.setdefault(key, []):
                mapping[key].append(val)
                self._dirty = True

        _add(self._data["dept_to_degrees"],  dept,   degree)
        _add(self._data["degree_to_depts"],  degree, dept)
        if spec:
            _add(self._data["dept_to_specs"], dept, spec)

    # ── Querying ─────────────────────────────────────────────────────────────

    def known_degrees_for_dept(self, raw_dept: str) -> list[str]:
        return self._data["dept_to_degrees"].get(normalize(raw_dept), [])

    def known_specs_for_dept(self, raw_dept: str) -> list[str]:
        return self._data["dept_to_specs"].get(normalize(raw_dept), [])

    def known_depts_for_degree(self, raw_degree: str) -> list[str]:
        return self._data["degree_to_depts"].get(normalize(raw_degree), [])

    def has_any_success_for_dept(self, raw_dept: str) -> bool:
        return normalize(raw_dept) in self._data["dept_to_degrees"]


# ─────────────────────────────────────────────────────────────────────────────
# 4.  Blacklist  (prune dept×degree pairs with repeated failures)
# ─────────────────────────────────────────────────────────────────────────────

_DEFAULT_BLACKLIST_PATH = os.path.expanduser("~/ims_scraper_outputs/blacklist.json")

class Blacklist:
    """
    Tracks consecutive spec-level failures per (dept_norm, degree_norm) pair.
    After persist_threshold (3) failures, the pair is persistently blacklisted.
    After skip_threshold (6) failures, returns True to break the inner loop (skip).
    """

    def __init__(self, persist_threshold: int = 3, skip_threshold: int = 6, path: str = _DEFAULT_BLACKLIST_PATH):
        self._persist_threshold = persist_threshold
        self._skip_threshold = skip_threshold
        self._path = path
        self._failures: dict[tuple[str, str], int] = {}
        self._session_skipped: set[tuple[str, str]] = set()
        self._persisted_blacklisted: set[tuple[str, str]] = set()
        self._load()

    def _load(self):
        if os.path.exists(self._path):
            try:
                with open(self._path, encoding="utf-8") as f:
                    data = json.load(f)
                    self._persisted_blacklisted = {tuple(k) for k in data if len(k) == 2}
            except Exception:
                pass

    def _save(self):
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump([list(k) for k in self._persisted_blacklisted], f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _key(self, raw_dept: str, raw_degree: str) -> tuple[str, str]:
        return (normalize(raw_dept), normalize(raw_degree))

    def record_failure(self, raw_dept: str, raw_degree: str) -> bool:
        """
        Record one consecutive failure for this dept×degree pair.
        Returns True the moment failures reach skip_threshold so the caller
        can break out of inner loops.
        """
        key = self._key(raw_dept, raw_degree)
        self._failures[key] = self._failures.get(key, 0) + 1
        
        # 1) Persist blacklist
        if self._failures[key] == self._persist_threshold:
            if key not in self._persisted_blacklisted:
                self._persisted_blacklisted.add(key)
                self._save()
                print(f"         🚫  Persistently Blacklisted: {raw_dept} × {raw_degree} "
                      f"(≥{self._persist_threshold} empty ops)")

        # 2) Session Skip
        if self._failures[key] >= self._skip_threshold:
            newly_skipped = key not in self._session_skipped
            self._session_skipped.add(key)
            if newly_skipped:
                print(f"         ⏭️   Skipping remaining specs: {raw_dept} × {raw_degree} "
                      f"(≥{self._skip_threshold} consecutive empty results)")
            return True

        return False

    def record_success(self, raw_dept: str, raw_degree: str):
        key = self._key(raw_dept, raw_degree)
        self._failures.pop(key, None)
        self._session_skipped.discard(key)
        
        # If successfully scraped, ensure it's removed from persistent blacklist
        if key in self._persisted_blacklisted:
            self._persisted_blacklisted.discard(key)
            self._save()

    def is_blacklisted(self, raw_dept: str, raw_degree: str) -> bool:
        key = self._key(raw_dept, raw_degree)
        return key in self._persisted_blacklisted or key in self._session_skipped


# ─────────────────────────────────────────────────────────────────────────────
# 5.  Filtering helpers  (used directly by the scraper loop)
# ─────────────────────────────────────────────────────────────────────────────

def filter_depts_for_degree(
    dept_opts: list[dict],
    raw_degree: str,
    cache: HeuristicsCache,
) -> list[dict]:
    """
    Given the live dropdown options and a degree string, return only those
    departments that pass the heuristic gate.

    Priority:
      1. If the cache has learned associations for this degree, use those.
      2. Otherwise fall back to static DEGREE_TO_DEPARTMENTS fuzzy match.
      3. If nothing is known (novel degree), pass everything through.
    """
    cached = cache.known_depts_for_degree(raw_degree)
    if cached:
        allowed_set = set(cached)
        result = [
            d for d in dept_opts
            if normalize(d["text"]) in allowed_set
               or fuzzy_match(d["text"], list(allowed_set), threshold=0.60) is not None
        ]
        if result:
            return result

    # Static fallback
    result = [d for d in dept_opts if is_department_allowed(d["text"], raw_degree)]
    if result:
        return result

    # Unknown degree → pass everything (safe; avoids silent data loss)
    return dept_opts


def filter_specs_for_dept(
    spec_opts: list[dict],
    raw_dept: str,
    cache: HeuristicsCache,
) -> list[dict]:
    """
    Given the live spec options and a department string, return only those
    specs that pass the heuristic gate.

    Same priority logic as filter_depts_for_degree.
    """
    cached = cache.known_specs_for_dept(raw_dept)
    if cached:
        allowed_set = set(cached)
        result = [
            s for s in spec_opts
            if normalize(s["text"]) in allowed_set
               or fuzzy_match(s["text"], list(allowed_set), threshold=0.55) is not None
        ]
        if result:
            return result

    result = [s for s in spec_opts if is_spec_allowed(s["text"], raw_dept)]
    if result:
        return result

    return spec_opts