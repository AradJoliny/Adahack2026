"""Abstract CSV -> canonical project records.

The incoming CSV may have different header names and column ordering, so the
rest of the app never touches raw headers. Everything goes through
``parse_csv_text`` which maps headers onto a fixed canonical schema using
(1) an optional explicit ``column_map`` supplied by the caller, then
(2) a table of aliases, then (3) a fuzzy match as a last resort.

To support a new CSV layout, add aliases to ``FIELDS`` - nothing else changes.
"""
from __future__ import annotations

import csv
import difflib
import io
import re
from dataclasses import dataclass, field

# canonical field -> (kind, aliases). Aliases are compared after normalise().
FIELDS: dict[str, tuple[str, list[str]]] = {
    "project_name": ("text", ["project name", "project", "name", "project title", "title"]),
    "status": ("text", ["status", "project status", "stage"]),
    "project_type": ("text", ["project type", "type", "category", "methodology", "project category"]),
    "region": ("text", ["region", "continent", "area"]),
    "country": ("text", ["country", "nation", "location", "host country"]),
    "developer": ("text", ["developer", "project developer", "proponent", "owner", "company"]),
    "vintage_year": ("int", ["vintage year", "vintage", "year", "credit vintage"]),
    "price_per_tonne": ("number", ["price per tonne", "price per ton", "price", "price tco2", "unit price",
                                   "price per tco2e", "cost per tonne"]),
    "risk": ("text", ["risk", "risk rating", "risk level", "risk score"]),
    "tonnes_chosen": ("number", ["tonnes chosen", "tonnes selected", "tonnes", "quantity", "volume",
                                 "tonnes purchased", "tco2e chosen", "amount chosen", "tonnes allocated",
                                 "qty", "quantity chosen"]),
}

REQUIRED = ["project_name", "tonnes_chosen"]
FUZZY_CUTOFF = 0.82


def normalise(header: str) -> str:
    """'  Price_Per-Tonne (£) ' -> 'price per tonne'"""
    h = re.sub(r"\(.*?\)|\[.*?\]", " ", str(header).lower())
    h = re.sub(r"[^a-z0-9]+", " ", h)
    return h.strip()


def parse_number(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s or s.lower() in {"n/a", "na", "nan", "null", "none", "-"}:
        return None
    neg = s.startswith("(") and s.endswith(")")
    s = re.sub(r"[^\d.,\-eE]", "", s)
    if "," in s and "." not in s and re.fullmatch(r"-?\d+,\d{1,2}", s):
        s = s.replace(",", ".")  # European decimal comma
    else:
        s = s.replace(",", "")
    try:
        n = float(s)
    except ValueError:
        return None
    return -n if neg else n


@dataclass
class ParseResult:
    records: list[dict]
    mapping: dict[str, str | None]  # canonical field -> source header (or None)
    unmapped_headers: list[str]
    warnings: list[str] = field(default_factory=list)


def build_mapping(headers: list[str], column_map: dict[str, str] | None = None):
    """Return (canonical -> source header, leftover headers)."""
    mapping: dict[str, str | None] = {k: None for k in FIELDS}
    used: set[str] = set()
    by_norm = {normalise(h): h for h in headers}

    # 1. explicit overrides: {"region": "Geo Region"}
    for canon, src in (column_map or {}).items():
        if canon in FIELDS and src in headers:
            mapping[canon] = src
            used.add(src)

    # 2. exact alias match (alias order = priority)
    for canon, (_, aliases) in FIELDS.items():
        if mapping[canon]:
            continue
        for alias in [canon.replace("_", " "), *aliases]:
            src = by_norm.get(alias)
            if src and src not in used:
                mapping[canon] = src
                used.add(src)
                break

    # 3. fuzzy match for whatever is left
    for canon, (_, aliases) in FIELDS.items():
        if mapping[canon]:
            continue
        candidates = [n for n, h in by_norm.items() if h not in used]
        best, best_score = None, 0.0
        for alias in aliases:
            m = difflib.get_close_matches(alias, candidates, n=1, cutoff=FUZZY_CUTOFF)
            if m:
                score = difflib.SequenceMatcher(None, alias, m[0]).ratio()
                if score > best_score:
                    best, best_score = m[0], score
        if best:
            mapping[canon] = by_norm[best]
            used.add(by_norm[best])

    return mapping, [h for h in headers if h not in used]


def _coerce(kind: str, raw):
    if kind == "text":
        s = "" if raw is None else str(raw).strip()
        return s or None
    n = parse_number(raw)
    if n is None:
        return None
    return int(round(n)) if kind == "int" else n


def parse_csv_text(text: str, column_map: dict[str, str] | None = None) -> ParseResult:
    text = text.lstrip("\ufeff")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    rows = list(reader)
    headers = [h for h in (reader.fieldnames or []) if h is not None]
    return parse_rows(rows, headers, column_map)


def parse_rows(rows: list[dict], headers: list[str] | None = None,
               column_map: dict[str, str] | None = None) -> ParseResult:
    """Shared by CSV text and by already-parsed JSON row arrays."""
    if headers is None:
        headers = list(rows[0].keys()) if rows else []
    mapping, leftover = build_mapping(headers, column_map)
    warnings = [f"Could not find a column for '{k}'" for k, v in mapping.items() if v is None]
    missing_required = [k for k in REQUIRED if mapping[k] is None]
    if missing_required:
        raise ValueError("Missing required column(s): " + ", ".join(missing_required)
                         + f". Headers received: {headers}")

    records = []
    for i, row in enumerate(rows):
        rec = {c: _coerce(FIELDS[c][0], row.get(src) if src else None) for c, src in mapping.items()}
        rec["tonnes_chosen"] = rec["tonnes_chosen"] or 0.0
        price = rec["price_per_tonne"] or 0.0
        rec["total_spend"] = round(rec["tonnes_chosen"] * price, 2)
        rec["region"] = rec["region"] or "Unknown"
        rec["project_name"] = rec["project_name"] or f"Project {i + 1}"
        records.append(rec)

    return ParseResult(records, mapping, leftover, warnings)
