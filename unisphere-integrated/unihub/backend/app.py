"""Backend for the Chanakya University Faculty & Research portal.

* Serves the unchanged frontend from ../frontend
* Serves /data.json (the file the frontend fetches) straight from the SQLite DB
* Exposes a REST API under /api for reading and (token-protected) editing data

Run:  python app.py        ->  http://localhost:5000
"""
import hashlib
import hmac
import html
import os
import re
import threading
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from flask import Flask, Response, abort, jsonify, request, send_from_directory

import db

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = Path(os.environ.get("FRONTEND_DIR", BASE_DIR.parent / "frontend")).resolve()
DB_PATH = Path(os.environ.get("DATABASE_PATH", BASE_DIR / "faculty.db"))
SEED_FILE = FRONTEND_DIR / "data.json"
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")

VERSION = "4"
ID_RE = re.compile(r"^[A-Za-z0-9_\-]{1,100}$")
NO_CACHE = "no-cache, no-store, must-revalidate, max-age=0"

SCHOOLS = {
    "School of Arts, Humanities and Social Sciences", "School of Management Sciences",
    "School of Mathematics and Natural Sciences", "School of Law, Governance and Public Policy",
    "School of Biosciences", "School of Engineering",
}
DOMAINS = {"General Research", "Law", "Public Health", "Sustainability", "Science Tech",
           "Humanities", "IKS", "Management"}
UPLOAD_LIMIT = (30, 3600)          # max 30 uploads per IP per hour


def create_app(db_path=DB_PATH, admin_token=None):
    app = Flask(__name__, static_folder=None)
    app.json.ensure_ascii = False
    app.json.sort_keys = False
    token = ADMIN_TOKEN if admin_token is None else admin_token

    conn = db.connect(db_path)
    db.init_db(conn)
    if db.is_empty(conn) and SEED_FILE.exists():
        n = db.seed_from_json(conn, SEED_FILE)
        print(f"[db] seeded {n} profiles from {SEED_FILE.name}")

    lock = threading.RLock()          # one shared sqlite connection -> serialise access
    cache = {"body": None, "etag": None}

    def invalidate():
        cache["body"] = cache["etag"] = None

    def profiles_json():
        with lock:
            if cache["body"] is None:
                body = app.json.dumps(db.build_profiles(conn))
                cache["body"] = body
                cache["etag"] = hashlib.md5(body.encode("utf-8")).hexdigest()
            return cache["body"], cache["etag"]

    def require_admin():
        if not token:
            abort(403, "Write API disabled: set the ADMIN_TOKEN environment variable.")
        supplied = request.headers.get("X-API-Key", "")
        if not hmac.compare_digest(supplied, token):
            abort(401, "Missing or invalid X-API-Key header.")

    @app.after_request
    def no_stale_pages(resp):
        if not request.path.startswith("/api/"):
            resp.headers["Cache-Control"] = NO_CACHE
        return resp

    @app.errorhandler(400)
    @app.errorhandler(401)
    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(409)
    def json_error(e):
        if request.path.startswith("/api/"):
            return jsonify(error=e.description), e.code
        return e

    # ---------------- data file used by the frontend ----------------
    @app.get("/data.json")
    @app.get("/faculty_data.json")
    def data_json():
        body, etag = profiles_json()
        resp = Response(body, mimetype="application/json")
        resp.headers["Cache-Control"] = NO_CACHE
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["ETag"] = etag
        return resp

    # ---------------- helpers ----------------
    def like(s):
        s = s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        return f"%{s}%"

    def page_args():
        try:
            limit = max(1, min(int(request.args.get("limit", 50)), 500))
            offset = max(0, int(request.args.get("offset", 0)))
        except ValueError:
            abort(400, "limit/offset must be integers")
        return limit, offset

    def get_json_body():
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            abort(400, "Request body must be a JSON object.")
        return body

    # ---------------- read API ----------------
    @app.get("/api/health")
    def health():
        with lock:
            n = conn.execute("SELECT COUNT(*) FROM faculty").fetchone()[0]
        return jsonify(status="ok", version=VERSION, faculty=n, frontend=str(FRONTEND_DIR), database=str(DB_PATH))

    @app.get("/api/stats")
    def stats():
        with lock:
            one = lambda q: conn.execute(q).fetchone()[0]
            by = lambda q: {r[0] or "Unknown": r[1] for r in conn.execute(q)}
            return jsonify(
                faculty_total=one("SELECT COUNT(*) FROM faculty"),
                publications_total=one("SELECT COUNT(*) FROM publications"),
                projects_total=one("SELECT COUNT(*) FROM projects"),
                international=one("SELECT COUNT(*) FROM faculty WHERE has_international_exp=1"),
                by_type=by("SELECT type, COUNT(*) FROM faculty GROUP BY type"),
                by_school=by("SELECT school, COUNT(*) FROM faculty GROUP BY school ORDER BY 2 DESC"),
                publications_by_category=by(
                    "SELECT category, COUNT(*) FROM publications GROUP BY category ORDER BY 2 DESC"),
            )

    @app.get("/api/faculty")
    def list_faculty():
        where, args = [], []
        for col in ("school", "type", "primary_category", "designation_group"):
            if request.args.get(col):
                where.append(f"{col}=?")
                args.append(request.args[col])
        if request.args.get("international") in ("1", "true"):
            where.append("has_international_exp=1")
        if request.args.get("q"):
            pat = like(request.args["q"])
            where.append("(name LIKE ? ESCAPE '\\' OR designation LIKE ? ESCAPE '\\' "
                         "OR areas_of_expertise LIKE ? ESCAPE '\\')")
            args += [pat] * 3
        limit, offset = page_args()
        sql = " WHERE " + " AND ".join(where) if where else ""
        with lock:
            total = conn.execute("SELECT COUNT(*) FROM faculty" + sql, args).fetchone()[0]
            ids = [r[0] for r in conn.execute(
                "SELECT id FROM faculty" + sql + " ORDER BY sort_order, id LIMIT ? OFFSET ?",
                args + [limit, offset])]
            items = db.build_profiles(conn, ids) if ids else []
        return jsonify(total=total, limit=limit, offset=offset, items=items)

    @app.get("/api/faculty/<fid>")
    def get_faculty(fid):
        with lock:
            items = db.build_profiles(conn, [fid])
        if not items:
            abort(404, "Faculty not found.")
        return jsonify(items[0])

    def child_list(table, fields):
        where, args = [], []
        for col in ("school", "category", "owner_id", "year" if table == "publications" else "status"):
            qname = "faculty_id" if col == "owner_id" else col
            if request.args.get(qname):
                where.append(f"t.{col}=?")
                args.append(request.args[qname])
        if request.args.get("q"):
            pat = like(request.args["q"])
            where.append("(t.title LIKE ? ESCAPE '\\' OR t.full_text LIKE ? ESCAPE '\\')")
            args += [pat, pat]
        limit, offset = page_args()
        sql = " WHERE " + " AND ".join(where) if where else ""
        with lock:
            total = conn.execute(f"SELECT COUNT(*) FROM {table} t" + sql, args).fetchone()[0]
            rows = conn.execute(
                f"SELECT t.pk, t.owner_id, f.name AS owner_name, t.faculty_name, "
                + ",".join("t." + f for f in fields if f != "faculty_name")
                + f" FROM {table} t LEFT JOIN faculty f ON f.id=t.owner_id" + sql
                + " ORDER BY t.owner_id, t.position LIMIT ? OFFSET ?", args + [limit, offset]).fetchall()
        items = [{"id": r["pk"], "faculty_id": r["owner_id"], "faculty_name": r["owner_name"] or r["faculty_name"],
                  **{f: r[f] for f in fields if f not in ("faculty_id", "faculty_name")}} for r in rows]
        return jsonify(total=total, limit=limit, offset=offset, items=items)

    @app.get("/api/publications")
    def list_publications():
        return child_list("publications", ["title", "full_text", "year", "category", "school",
                                           "link", "about", "submitted_at"])

    @app.get("/api/projects")
    def list_projects():
        return child_list("projects", ["title", "pi", "agency", "funding_agency", "status",
                                       "grant_amount", "description", "school", "category", "year", "link",
                                       "submitted_at"])

    # ---------------- write API (needs X-API-Key) ----------------
    WRITABLE = (set(db.FACULTY_TEXT) | set(db.FACULTY_JSON) | set(db.FACULTY_LABELS)
                | {"has_international_exp"})

    def validate_payload(body):
        for k in db.FACULTY_JSON:
            if k in body and body[k] is not None:
                want = dict if k == "social_links" else list
                if not isinstance(body[k], want):
                    abort(400, f"'{k}' must be a JSON {'object' if want is dict else 'array'}.")
        for k in ("publications_list", "projects_list"):
            if k in body and not (isinstance(body[k], list) and all(isinstance(x, dict) for x in body[k])):
                abort(400, f"'{k}' must be an array of objects.")

    @app.post("/api/faculty")
    def create_faculty():
        require_admin()
        body = get_json_body()
        fid = body.get("id", "")
        if not ID_RE.match(str(fid)):
            abort(400, "'id' is required (letters, digits, _ or -).")
        if not body.get("name"):
            abort(400, "'name' is required.")
        validate_payload(body)
        with lock, conn:
            if conn.execute("SELECT 1 FROM faculty WHERE id=?", (fid,)).fetchone():
                abort(409, "A profile with this id already exists.")
            nxt = conn.execute("SELECT COALESCE(MAX(sort_order),-1)+1 FROM faculty").fetchone()[0]
            db.insert_profile(conn, body, nxt)
        invalidate()
        return jsonify(db.build_profiles(conn, [fid])[0]), 201

    @app.route("/api/faculty/<fid>", methods=["PUT", "PATCH"])
    def update_faculty(fid):
        require_admin()
        body = get_json_body()
        validate_payload(body)
        with lock, conn:
            if not conn.execute("SELECT 1 FROM faculty WHERE id=?", (fid,)).fetchone():
                abort(404, "Faculty not found.")
            sets, args = [], []
            for k, v in body.items():
                if k not in WRITABLE:
                    continue
                if k in db.FACULTY_JSON:
                    sets.append(f"{k}=?"); args.append(db._jdump(v))
                elif k in db.FACULTY_LABELS:
                    sets.append(f"{k}_label=?"); args.append(db._jdump(v))
                elif k == "has_international_exp":
                    sets.append("has_international_exp=?"); args.append(1 if v else 0)
                else:
                    sets.append(f"{k}=?"); args.append(v)
            if sets:
                conn.execute(f"UPDATE faculty SET {','.join(sets)} WHERE id=?", args + [fid])
            if "publications_list" in body or "projects_list" in body:
                cur = db.build_profiles(conn, [fid])[0]
                db.replace_children(conn, fid,
                                    body.get("publications_list", cur["publications_list"]),
                                    body.get("projects_list", cur["projects_list"]))
        invalidate()
        return jsonify(db.build_profiles(conn, [fid])[0])

    @app.delete("/api/faculty/<fid>")
    def delete_faculty(fid):
        require_admin()
        with lock, conn:
            cur = conn.execute("DELETE FROM faculty WHERE id=?", (fid,))
        if not cur.rowcount:
            abort(404, "Faculty not found.")
        invalidate()
        return "", 204

    def add_child(table, fields):
        require_admin()
        body = get_json_body()
        fid = body.get("faculty_id")
        with lock, conn:
            if not fid or not conn.execute("SELECT 1 FROM faculty WHERE id=?", (fid,)).fetchone():
                abort(400, "'faculty_id' must reference an existing profile.")
            pos = conn.execute(f"SELECT COALESCE(MAX(position),-1)+1 FROM {table} WHERE owner_id=?",
                               (fid,)).fetchone()[0]
            cur = conn.execute(
                f"INSERT INTO {table} (owner_id, position, {','.join(fields)}) "
                f"VALUES (?,?,{','.join('?' * len(fields))})",
                [fid, pos] + [body.get(f) for f in fields])
        invalidate()
        return jsonify(id=cur.lastrowid), 201

    def edit_child(table, fields, pk):
        require_admin()
        body = get_json_body()
        cols = [f for f in fields if f in body]
        with lock, conn:
            if not conn.execute(f"SELECT 1 FROM {table} WHERE pk=?", (pk,)).fetchone():
                abort(404, "Record not found.")
            if cols:
                conn.execute(f"UPDATE {table} SET {','.join(c + '=?' for c in cols)} WHERE pk=?",
                             [body[c] for c in cols] + [pk])
        invalidate()
        return jsonify(id=pk, updated=cols)

    def del_child(table, pk):
        require_admin()
        with lock, conn:
            cur = conn.execute(f"DELETE FROM {table} WHERE pk=?", (pk,))
        if not cur.rowcount:
            abort(404, "Record not found.")
        invalidate()
        return "", 204

    for table, fields in (("publications", db.PUB_FIELDS), ("projects", db.PROJ_FIELDS)):
        app.add_url_rule(f"/api/{table}", f"add_{table}", lambda t=table, f=fields: add_child(t, f),
                         methods=["POST"])
        app.add_url_rule(f"/api/{table}/<int:pk>", f"edit_{table}",
                         lambda pk, t=table, f=fields: edit_child(t, f, pk), methods=["PUT", "PATCH"])
        app.add_url_rule(f"/api/{table}/<int:pk>", f"del_{table}",
                         lambda pk, t=table: del_child(t, pk), methods=["DELETE"])


    # ---------------- public uploads: Upload -> Research Paper / Repository ----------------
    hits = {}

    def rate_limited():
        ip = request.headers.get("X-Forwarded-For", request.remote_addr or "?").split(",")[0].strip()
        n, window = UPLOAD_LIMIT
        now = time.time()
        q = [t for t in hits.get(ip, []) if now - t < window]
        q.append(now)
        hits[ip] = q
        return len(q) > n

    def clean_text(body, key, label, required=True, maxlen=300):
        v = body.get(key)
        v = "" if v is None else str(v)
        v = re.sub(r"\s+", " ", v).strip() if maxlen <= 300 else v.strip()
        if required and not v:
            return None, f"{label} is required."
        if len(v) > maxlen:
            return None, f"{label} must be at most {maxlen} characters."
        # stored HTML-escaped: the frontend renders these values with innerHTML
        return html.escape(v, quote=True), None

    def clean_url(body, key, label, github=False):
        v = str(body.get(key) or "").strip()
        if not v:
            return None, f"{label} is required."
        if not github and re.match(r"^10\.\d{4,9}/\S+$", v):
            v = "https://doi.org/" + v
        if len(v) > 500:
            return None, f"{label} is too long."
        u = urlparse(v)
        if u.scheme not in ("http", "https") or not u.netloc or " " in v:
            return None, f"{label} must be a valid http(s) URL" + (" or DOI." if not github else ".")
        if github and (u.hostname or "").lower() not in ("github.com", "www.github.com"):
            return None, "GitHub link must point to github.com."
        return html.escape(v, quote=True), None

    def validate_upload(body, kind):
        errors, out = {}, {}
        def put(key, res):
            val, err = res
            if err:
                errors[key] = err
            else:
                out[key] = val
        paper = kind == "publication"
        put("title", clean_text(body, "title", "Paper title" if paper else "Project title", maxlen=300))
        put("author", clean_text(body, "author", "Author / faculty name" if paper else "Principal investigator", maxlen=150))
        put("about", clean_text(body, "about", "About", maxlen=3000))
        put("link", clean_url(body, "link", "Paper link" if paper else "GitHub link", github=not paper))
        if paper:
            put("citation", clean_text(body, "citation", "Journal / publisher / citation", required=False, maxlen=500))
        school = str(body.get("school") or "").strip()
        if school and not school.startswith("School of "):
            school = "School of " + school
        if school not in SCHOOLS:
            errors["school"] = "Please choose a school."
        out["school"] = school
        domain = str(body.get("category") or "").strip()
        if domain not in DOMAINS:
            errors["category"] = "Please choose a domain."
        out["category"] = domain
        year = str(body.get("year") or "").strip()
        if not (year.isdigit() and len(year) == 4 and 1900 <= int(year) <= datetime.now().year + 1):
            errors["year"] = "Enter a valid 4-digit year."
        out["year"] = year
        return out, errors

    def handle_upload(kind):
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            abort(400, "Request body must be a JSON object.")
        if body.get("website"):                       # honeypot field, real users leave it empty
            return jsonify(ok=True, id=0), 201
        if rate_limited():
            return jsonify(error="Too many uploads from this address. Please try again later."), 429
        data, errors = validate_upload(body, kind)
        if errors:
            return jsonify(error="Please fix the highlighted fields.", fields=errors), 400
        with lock, conn:
            try:
                pk, fac = db.add_upload(conn, kind, data)
            except ValueError:
                return jsonify(error="This has already been added.", fields={"title": "Already added by this author."}), 409
        invalidate()
        return jsonify(ok=True, id=pk, linked_to=({"id": fac["id"], "name": fac["name"]} if fac else None)), 201

    app.add_url_rule("/api/submit/paper", "submit_paper", lambda: handle_upload("publication"), methods=["POST"])
    app.add_url_rule("/api/submit/project", "submit_project", lambda: handle_upload("project"), methods=["POST"])

    @app.get("/api/unlinked")
    def unlinked():
        """Uploads whose author/PI is not a directory profile. Pages merge these with data.json."""
        with lock:
            r = jsonify(db.list_unlinked(conn))
        r.headers["Cache-Control"] = NO_CACHE
        return r

    # ---------------- frontend ----------------
    @app.get("/")
    def index():
        return send_from_directory(FRONTEND_DIR, "index.html")

    @app.get("/<path:filename>")
    def frontend(filename):
        if filename.startswith("api/"):
            abort(404)
        return send_from_directory(FRONTEND_DIR, filename)

    app.config["DB"] = conn
    return app


def _port_free(port, host="127.0.0.1"):
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sk:
        return sk.connect_ex((host, port)) != 0


def _who_is_on(port):
    """Return the /api/health JSON of whatever portal copy already listens on `port`, else None."""
    import json
    import urllib.request
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1.5) as r:
            return json.load(r)
    except Exception:
        return {}


if __name__ == "__main__":
    want = int(os.environ.get("PORT", 5000))
    port = want
    if not _port_free(port):
        if os.environ.get("UNIHUB_STRICT_PORT") == "1":
            raise SystemExit(f"UniHub backend port {port} became unavailable before startup.")
        old = _who_is_on(port)
        bar = "!" * 70
        print(bar)
        if old and "status" in old:
            print(f" An OLDER COPY of this portal is still running on port {port}")
            print(f" (version {old.get('version', '1 or 2')}, serving: {old.get('frontend', 'unknown folder')}).")
            print(" That is why the browser still shows the old page.")
            print(" Close its window (or press Ctrl+C in it), then start this again.")
        else:
            print(f" Port {port} is used by another program.")
        while not _port_free(port):
            port += 1
        print(f" Starting THIS copy on port {port} instead -> open http://localhost:{port}")
        print(bar)
    if not ADMIN_TOKEN:
        print("[info] ADMIN_TOKEN not set -> admin write API is disabled; reads and Upload still work.")
    print(f"[portal v{VERSION}] frontend: {FRONTEND_DIR}")
    print(f"[portal v{VERSION}] database: {DB_PATH}")
    print(f"[UniHub] API backend listening at http://127.0.0.1:{port}.")
    print("[UniHub] For the integrated portal, open the UniSphere Local URL printed by Vite.")
    create_app().run(host=os.environ.get("HOST", "127.0.0.1"), port=port, debug=False)
