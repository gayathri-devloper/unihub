"""Run:  python test_backend.py"""
import json, tempfile, unittest
from pathlib import Path
import app as appmod

SRC = Path(appmod.FRONTEND_DIR) / "data.json"


def norm(o):
    """Treat missing keys and null alike for comparison."""
    if isinstance(o, dict):
        return {k: norm(v) for k, v in o.items() if v is not None}
    if isinstance(o, list):
        return [norm(x) for x in o]
    return o


class T(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.app = appmod.create_app(Path(cls.tmp.name) / "t.db", admin_token="secret")
        cls.c = cls.app.test_client()
        cls.H = {"X-API-Key": "secret"}

    # NOTE: 2 source profiles omit `intl_track_category`; we emit null (frontend only does === 'string' checks).
    def test_01_data_json_roundtrip_exact(self):
        orig = json.loads(SRC.read_text(encoding="utf-8-sig"))
        got = self.c.get("/data.json").get_json()
        self.assertEqual(len(got), len(orig))
        self.assertEqual(norm(got), norm(orig))

    def test_02_frontend_served_unchanged(self):
        for name in ("index.html", "app.js", "styles.css", "profile.html", "projects.html",
                     "publications.html", "international.html", "logo.svg", "upload.js"):
            r = self.c.get("/" + name if name != "index.html" else "/")
            self.assertEqual(r.status_code, 200, name)
            self.assertEqual(r.data, (Path(appmod.FRONTEND_DIR) / name).read_bytes(), name)

    def test_03_reads(self):
        self.assertEqual(self.c.get("/api/health").get_json()["faculty"], 174)
        s = self.c.get("/api/stats").get_json()
        self.assertEqual((s["publications_total"], s["projects_total"]), (885, 111))
        r = self.c.get("/api/faculty?school=School of Biosciences&limit=5").get_json()
        self.assertTrue(r["total"] > 0 and len(r["items"]) <= 5)
        self.assertEqual(self.c.get("/api/faculty/h_s_subramanya").get_json()["name"], "Prof. H. S. Subramanya")
        self.assertEqual(self.c.get("/api/faculty/nope").status_code, 404)
        self.assertTrue(self.c.get("/api/publications?q=crop&limit=3").get_json()["total"] >= 0)
        self.assertEqual(self.c.get("/api/projects?limit=1").get_json()["total"], 111)
        self.assertEqual(self.c.get("/api/faculty?q=%25").get_json()["total"], 0)  # % is escaped

    def test_04_write_auth(self):
        self.assertEqual(self.c.post("/api/faculty", json={"id": "x", "name": "X"}).status_code, 401)
        a = appmod.create_app(Path(self.tmp.name) / "n.db", admin_token="")
        self.assertEqual(a.test_client().post("/api/faculty", json={"id": "x", "name": "X"}).status_code, 403)

    def test_05_crud_reflected_in_data_json(self):
        c, H = self.c, self.H
        r = c.post("/api/faculty", headers=H, json={
            "id": "test_person", "name": "Dr. Test", "type": "Faculty", "school": "School of Engineering",
            "categories": ["Engineering"], "publications_list": [{"title": "T1", "full_text": "T1 full", "year": "2024", "category": "Engineering"}]})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(c.post("/api/faculty", headers=H, json={"id": "test_person", "name": "dup"}).status_code, 409)
        self.assertEqual(c.post("/api/faculty", headers=H, json={"id": "bad id!", "name": "x"}).status_code, 400)
        data = c.get("/data.json").get_json()
        self.assertEqual(len(data), 175)
        self.assertEqual(data[-1]["id"], "test_person")          # cache invalidated
        r = c.put("/api/faculty/test_person", headers=H, json={"designation": "Professor", "has_international_exp": True})
        self.assertEqual(r.get_json()["designation"], "Professor")
        pid = c.post("/api/projects", headers=H, json={"faculty_id": "test_person", "title": "P1", "status": "Ongoing"}).get_json()["id"]
        self.assertEqual(len(c.get("/api/faculty/test_person").get_json()["projects_list"]), 1)
        c.put(f"/api/projects/{pid}", headers=H, json={"status": "Completed"})
        self.assertEqual(c.get("/api/faculty/test_person").get_json()["projects_list"][0]["status"], "Completed")
        self.assertEqual(c.delete(f"/api/projects/{pid}", headers=H).status_code, 204)
        self.assertEqual(c.delete("/api/faculty/test_person", headers=H).status_code, 204)
        self.assertEqual(len(c.get("/data.json").get_json()), 174)
        self.assertEqual(c.get("/api/publications?faculty_id=test_person").get_json()["total"], 0)  # cascade

    # ------------------------------------------------------------------ uploads
    PAPER = {"title": "Crop Yield Study", "author": "Dr. H. S. Subramanya", "school": "Biosciences",
             "category": "General Research", "year": "2026", "citation": "J. Agri 12(3)",
             "link": "https://doi.org/10.1000/xyz", "about": "About the study."}
    PROJ = {"title": "Open Crop Repo", "author": "Someone Outside", "school": "Engineering",
            "category": "Law", "year": 2026, "link": "https://github.com/user/repo", "about": "Repo about."}

    def test_06_upload_paper_linked_and_persistent(self):
        c = self.c
        before = len(c.get("/api/faculty/h_s_subramanya").get_json()["publications_list"])
        r = c.post("/api/submit/paper", json=self.PAPER)
        self.assertEqual(r.status_code, 201, r.get_json())
        self.assertEqual(r.get_json()["linked_to"]["id"], "h_s_subramanya")
        pubs = c.get("/data.json").get_json()
        prof = next(p for p in pubs if p["id"] == "h_s_subramanya")
        self.assertEqual(len(prof["publications_list"]), before + 1)
        new = prof["publications_list"][-1]
        self.assertEqual((new["title"], new["school"], new["year"], new["link"]),
                         ("Crop Yield Study", "School of Biosciences", "2026", "https://doi.org/10.1000/xyz"))
        self.assertTrue(new["submitted_at"])
        # survives a restart (new app instance on the same database file)
        again = appmod.create_app(Path(self.tmp.name) / "t.db", admin_token="secret").test_client()
        titles = [x["title"] for x in again.get("/api/faculty/h_s_subramanya").get_json()["publications_list"]]
        self.assertIn("Crop Yield Study", titles)
        # duplicate rejected
        self.assertEqual(c.post("/api/submit/paper", json=self.PAPER).status_code, 409)

    def test_07_upload_project_unlinked(self):
        c = self.c
        r = c.post("/api/submit/project", json=self.PROJ)
        self.assertEqual(r.status_code, 201, r.get_json())
        self.assertIsNone(r.get_json()["linked_to"])
        un = c.get("/api/unlinked").get_json()
        self.assertEqual([p["title"] for p in un["projects"]], ["Open Crop Repo"])
        self.assertEqual(un["projects"][0]["faculty_name"], "Someone Outside")
        self.assertEqual(un["projects"][0]["link"], "https://github.com/user/repo")
        self.assertEqual(len(c.get("/data.json").get_json()), 174)   # directory untouched
        # unlinked uploads also show in the list API and stats
        self.assertEqual(c.get("/api/projects?q=Open Crop").get_json()["total"], 1)

    def test_08_upload_validation_and_safety(self):
        c = self.c
        bad = dict(self.PAPER, title="", link="javascript:alert(1)", year="abcd", school="Nope", category="Nope")
        r = c.post("/api/submit/paper", json=bad)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(set(r.get_json()["fields"]), {"title", "link", "year", "school", "category"})
        self.assertEqual(c.post("/api/submit/project", json=dict(self.PROJ, title="t2", link="https://evil.com/x")).status_code, 400)
        self.assertEqual(c.post("/api/submit/paper", data="notjson", content_type="text/plain").status_code, 400)
        # HTML is escaped before storage (pages render with innerHTML)
        r = c.post("/api/submit/paper", json=dict(self.PAPER, title='<img src=x onerror=alert(1)>', author="Nobody Known",
                                                  link='https://a.com/"onmouseover="x'))
        self.assertEqual(r.status_code, 201)
        row = c.get("/api/unlinked").get_json()["publications"][0]
        self.assertNotIn("<", row["title"]); self.assertNotIn('"', row["link"])
        # honeypot: silently accepted, nothing stored
        n = c.get("/api/unlinked").get_json()
        c.post("/api/submit/paper", json=dict(self.PAPER, title="bot", website="spam"))
        self.assertEqual(c.get("/api/unlinked").get_json(), n)

    def test_09_old_database_is_migrated(self):
        import sqlite3
        p = Path(self.tmp.name) / "old.db"
        con = sqlite3.connect(p)
        con.executescript("""
        CREATE TABLE faculty (id TEXT PRIMARY KEY, sort_order INTEGER NOT NULL DEFAULT 0, name TEXT NOT NULL, type TEXT,
          designation TEXT, school TEXT, primary_category TEXT, categories TEXT, clusters TEXT, qualifications TEXT, email TEXT,
          profile_url TEXT, image_url TEXT, areas_of_expertise TEXT, bio TEXT, research_quest TEXT, publications_label TEXT,
          projects_label TEXT, achievements TEXT, additional_info TEXT, social_links TEXT, has_international_exp INTEGER NOT NULL DEFAULT 0,
          international_evidence TEXT, qual_level TEXT, designation_group TEXT, category TEXT, intl_track_category TEXT,
          research TEXT, department TEXT, international_exp TEXT);
        CREATE TABLE publications (pk INTEGER PRIMARY KEY AUTOINCREMENT, owner_id TEXT NOT NULL REFERENCES faculty(id) ON DELETE CASCADE ON UPDATE CASCADE,
          position INTEGER NOT NULL DEFAULT 0, title TEXT, full_text TEXT, year TEXT, category TEXT, faculty_id TEXT, faculty_name TEXT, school TEXT);
        CREATE TABLE projects (pk INTEGER PRIMARY KEY AUTOINCREMENT, owner_id TEXT NOT NULL REFERENCES faculty(id) ON DELETE CASCADE ON UPDATE CASCADE,
          position INTEGER NOT NULL DEFAULT 0, title TEXT, pi TEXT, agency TEXT, funding_agency TEXT, status TEXT, grant_amount TEXT,
          description TEXT, full_text TEXT, faculty_id TEXT, faculty_name TEXT, school TEXT, category TEXT);
        CREATE INDEX idx_pub_owner ON publications(owner_id, position);
        INSERT INTO faculty (id,name,school) VALUES ('a','Dr. Old Timer','School of Engineering');
        INSERT INTO publications (owner_id,position,title,year) VALUES ('a',0,'Old paper','2020');
        """); con.commit(); con.close()
        cl = appmod.create_app(p, admin_token="x").test_client()
        d = cl.get("/data.json").get_json()
        self.assertEqual([x["title"] for x in d[0]["publications_list"]], ["Old paper"])
        self.assertEqual(cl.post("/api/submit/paper", json=dict(self.PAPER, author="Old Timer")).get_json()["linked_to"]["id"], "a")


if __name__ == "__main__":
    unittest.main(verbosity=2)
