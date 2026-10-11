"""SQLite storage layer for the Faculty & Research portal.

The database is normalised into three tables (faculty, publications, projects).
`build_profiles()` re-assembles rows into exactly the JSON structure the
frontend already expects, so the frontend needs no changes.
"""
import json
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS faculty (
    id                      TEXT PRIMARY KEY,
    sort_order              INTEGER NOT NULL DEFAULT 0,
    name                    TEXT NOT NULL,
    type                    TEXT,
    designation             TEXT,
    school                  TEXT,
    primary_category        TEXT,
    categories              TEXT,   -- JSON array
    clusters                TEXT,   -- JSON array
    qualifications          TEXT,
    email                   TEXT,
    profile_url             TEXT,
    image_url               TEXT,
    areas_of_expertise      TEXT,
    bio                     TEXT,
    research_quest          TEXT,
    publications_label      TEXT,   -- JSON scalar (e.g. "49 Publications" or 12)
    projects_label          TEXT,   -- JSON scalar
    achievements            TEXT,
    additional_info         TEXT,
    social_links            TEXT,   -- JSON object
    has_international_exp   INTEGER NOT NULL DEFAULT 0,
    international_evidence  TEXT,
    qual_level              TEXT,
    designation_group       TEXT,
    category                TEXT,
    intl_track_category     TEXT,
    research                TEXT,
    department              TEXT,
    international_exp       TEXT    -- JSON array
);

CREATE TABLE IF NOT EXISTS publications (
    pk            INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id      TEXT REFERENCES faculty(id) ON DELETE CASCADE ON UPDATE CASCADE,  -- NULL = author not in directory
    position      INTEGER NOT NULL DEFAULT 0,
    title         TEXT,
    full_text     TEXT,
    year          TEXT,
    category      TEXT,
    faculty_id    TEXT,
    faculty_name  TEXT,
    school        TEXT,
    link          TEXT,   -- DOI / paper URL (user uploads)
    about         TEXT,   -- short description (user uploads)
    submitted_at  TEXT    -- ISO timestamp, set only for user uploads
);

CREATE TABLE IF NOT EXISTS projects (
    pk              INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id        TEXT REFERENCES faculty(id) ON DELETE CASCADE ON UPDATE CASCADE,  -- NULL = PI not in directory
    position        INTEGER NOT NULL DEFAULT 0,
    title           TEXT,
    pi              TEXT,
    agency          TEXT,
    funding_agency  TEXT,
    status          TEXT,
    grant_amount    TEXT,
    description     TEXT,
    full_text       TEXT,
    faculty_id      TEXT,
    faculty_name    TEXT,
    school          TEXT,
    category        TEXT,
    year            TEXT,   -- user uploads
    link            TEXT,   -- GitHub URL (user uploads)
    submitted_at    TEXT    -- ISO timestamp, set only for user uploads
);

CREATE INDEX IF NOT EXISTS idx_faculty_school ON faculty(school);
CREATE INDEX IF NOT EXISTS idx_faculty_type   ON faculty(type);
CREATE INDEX IF NOT EXISTS idx_pub_owner      ON publications(owner_id, position);
CREATE INDEX IF NOT EXISTS idx_pub_category   ON publications(category);
CREATE INDEX IF NOT EXISTS idx_proj_owner     ON projects(owner_id, position);
"""

# column definitions -----------------------------------------------------
FACULTY_TEXT = [
    "name", "type", "designation", "school", "primary_category", "qualifications",
    "email", "profile_url", "image_url", "areas_of_expertise", "bio", "research_quest",
    "achievements", "additional_info", "international_evidence", "qual_level",
    "designation_group", "category", "intl_track_category", "research", "department",
]
FACULTY_JSON = ["categories", "clusters", "social_links", "international_exp"]
# stored in "<name>_label" columns, value can be string or number
FACULTY_LABELS = ["publications", "projects"]
PUB_FIELDS = ["title", "full_text", "year", "category", "faculty_id", "faculty_name", "school",
              "link", "about", "submitted_at"]
PROJ_FIELDS = ["title", "pi", "agency", "funding_agency", "status", "grant_amount",
               "description", "full_text", "faculty_id", "faculty_name", "school", "category",
               "year", "link", "submitted_at"]

# keys that the original dataset keeps as explicit `null` when empty
EXPLICIT_NULL_KEYS = {"intl_track_category"}


def connect(path):
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _columns(conn, table):
    return [r["name"] for r in conn.execute(f"PRAGMA table_info({table})")]


def _migrate(conn):
    """Upgrade databases created by the first release (owner_id NOT NULL, no upload columns)."""
    for table in ("publications", "projects"):
        cols = _columns(conn, table)
        if cols and "link" not in cols:
            conn.execute("DROP INDEX IF EXISTS idx_pub_owner")
            conn.execute("DROP INDEX IF EXISTS idx_pub_category")
            conn.execute("DROP INDEX IF EXISTS idx_proj_owner")
            conn.execute(f"ALTER TABLE {table} RENAME TO {table}_old")
            conn.executescript(SCHEMA)
            keep = ",".join(c for c in cols if c != "pk")
            conn.execute(f"INSERT INTO {table} ({keep}) SELECT {keep} FROM {table}_old ORDER BY pk")
            conn.execute(f"DROP TABLE {table}_old")
            conn.commit()


def init_db(conn):
    _migrate(conn)               # only acts on old-format databases
    conn.executescript(SCHEMA)   # creates tables/indexes that are missing
    conn.commit()


def is_empty(conn):
    return conn.execute("SELECT COUNT(*) FROM faculty").fetchone()[0] == 0


# ---- python dict -> row ------------------------------------------------
def _jdump(v):
    return None if v is None else json.dumps(v, ensure_ascii=False)


def insert_profile(conn, p, sort_order):
    cols = {"id": p["id"], "sort_order": sort_order}
    for k in FACULTY_TEXT:
        cols[k] = p.get(k)
    for k in FACULTY_JSON:
        cols[k] = _jdump(p[k]) if k in p else None
    for k in FACULTY_LABELS:
        cols[k + "_label"] = _jdump(p[k]) if k in p else None
    cols["has_international_exp"] = 1 if p.get("has_international_exp") else 0
    names = ",".join(cols)
    marks = ",".join("?" * len(cols))
    conn.execute(f"INSERT INTO faculty ({names}) VALUES ({marks})", list(cols.values()))
    replace_children(conn, p["id"], p.get("publications_list", []), p.get("projects_list", []))


def replace_children(conn, owner_id, pubs, projs):
    conn.execute("DELETE FROM publications WHERE owner_id=?", (owner_id,))
    conn.execute("DELETE FROM projects WHERE owner_id=?", (owner_id,))
    for i, x in enumerate(pubs or []):
        conn.execute(
            f"INSERT INTO publications (owner_id, position, {','.join(PUB_FIELDS)}) "
            f"VALUES (?,?,{','.join('?' * len(PUB_FIELDS))})",
            [owner_id, i] + [x.get(f) for f in PUB_FIELDS])
    for i, x in enumerate(projs or []):
        conn.execute(
            f"INSERT INTO projects (owner_id, position, {','.join(PROJ_FIELDS)}) "
            f"VALUES (?,?,{','.join('?' * len(PROJ_FIELDS))})",
            [owner_id, i] + [x.get(f) for f in PROJ_FIELDS])


# ---- row -> python dict (frontend shape) --------------------------------
def _clean(row, fields):
    return {f: row[f] for f in fields if row[f] is not None}


def faculty_row_to_dict(r):
    d = {"id": r["id"]}
    for k in FACULTY_TEXT:
        if r[k] is not None or k in EXPLICIT_NULL_KEYS:
            d[k] = r[k]
    for k in FACULTY_JSON:
        if r[k] is not None:
            d[k] = json.loads(r[k])
    for k in FACULTY_LABELS:
        if r[k + "_label"] is not None:
            d[k] = json.loads(r[k + "_label"])
    d["has_international_exp"] = bool(r["has_international_exp"])
    return d


def build_profiles(conn, ids=None):
    """Return list of profile dicts, identical in shape to the original data.json."""
    q = "SELECT * FROM faculty"
    args = []
    if ids is not None:
        q += " WHERE id IN (%s)" % ",".join("?" * len(ids))
        args = list(ids)
    q += " ORDER BY sort_order, id"
    profiles = [faculty_row_to_dict(r) for r in conn.execute(q, args)]
    by_id = {p["id"]: p for p in profiles}
    for p in profiles:
        p["publications_list"] = []
        p["projects_list"] = []
    for r in conn.execute("SELECT * FROM publications ORDER BY owner_id, position"):
        if r["owner_id"] in by_id:
            by_id[r["owner_id"]]["publications_list"].append(_clean(r, PUB_FIELDS))
    for r in conn.execute("SELECT * FROM projects ORDER BY owner_id, position"):
        if r["owner_id"] in by_id:
            by_id[r["owner_id"]]["projects_list"].append(_clean(r, PROJ_FIELDS))
    return profiles


def seed_from_json(conn, json_path):
    data = json.loads(Path(json_path).read_text(encoding="utf-8-sig"))
    with conn:
        for i, p in enumerate(data):
            insert_profile(conn, p, i)
    return len(data)


# ---------------------------------------------------------------------------
# User uploads (Upload -> Research Paper / Repository)
# ---------------------------------------------------------------------------
import re
from datetime import datetime, timezone

_TITLES = {"dr", "prof", "professor", "mr", "mrs", "ms", "miss", "shri", "smt", "sri", "er"}


def _name_tokens(name):
    t = re.sub(r"[^a-z0-9 ]", " ", (name or "").lower().replace(".", " "))
    return [w for w in t.split() if w not in _TITLES]


def find_faculty(conn, name):
    """Match a typed author name to a directory profile. Returns row or None.

    1. exact match after stripping titles/punctuation/case
    2. otherwise a *unique* profile whose name contains all typed words (needs >= 2 words)
    """
    want = _name_tokens(name)
    if not want:
        return None
    rows = conn.execute("SELECT id, name, school FROM faculty").fetchall()
    toks = [(r, _name_tokens(r["name"])) for r in rows]
    exact = [r for r, t in toks if t == want]
    if len(exact) == 1:
        return exact[0]
    if len(want) >= 2:
        sub = [r for r, t in toks if set(want) <= set(t)]
        if len(sub) == 1:
            return sub[0]
    return None


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _dup(conn, table, title, author):
    t = re.sub(r"\W+", "", (title or "").lower())
    a = " ".join(_name_tokens(author))
    for r in conn.execute(f"SELECT title, faculty_name FROM {table} WHERE submitted_at IS NOT NULL"):
        if re.sub(r"\W+", "", (r["title"] or "").lower()) == t and " ".join(_name_tokens(r["faculty_name"])) == a:
            return True
    return False


def add_upload(conn, kind, d):
    """Store a validated upload. kind = 'publication' | 'project'. Returns (pk, matched_faculty_row|None).

    Raises ValueError('duplicate') if the same title+author was already uploaded.
    """
    table = "publications" if kind == "publication" else "projects"
    fac = find_faculty(conn, d["author"])
    if _dup(conn, table, d["title"], d["author"]):
        raise ValueError("duplicate")
    owner = fac["id"] if fac else None
    pos = conn.execute(f"SELECT COALESCE(MAX(position),-1)+1 FROM {table} WHERE owner_id IS ?", (owner,)).fetchone()[0]
    common = {
        "owner_id": owner, "position": pos, "title": d["title"],
        "faculty_id": owner, "faculty_name": fac["name"] if fac else d["author"],
        "school": d["school"], "category": d["category"], "year": d["year"],
        "link": d["link"], "submitted_at": _now(),
    }
    if kind == "publication":
        common.update(full_text=d.get("citation") or d["title"], about=d["about"])
    else:
        common.update(pi=d["author"], agency="GitHub Repository", funding_agency="GitHub Repository",
                      status="Open Source", grant_amount="N/A", description=d["about"], full_text=d["about"])
    cols = list(common)
    cur = conn.execute(f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                       [common[c] for c in cols])
    return cur.lastrowid, fac


def list_unlinked(conn):
    """Uploads whose author is not in the faculty directory (data.json cannot carry them)."""
    out = {}
    for table, fields in (("publications", PUB_FIELDS), ("projects", PROJ_FIELDS)):
        rows = conn.execute(f"SELECT * FROM {table} WHERE owner_id IS NULL ORDER BY submitted_at DESC, pk DESC")
        out[table] = [{"id": r["pk"], **_clean(r, fields)} for r in rows]
    return out
