"""Dump the database back to a data.json-style file.   python export_json.py out.json"""
import json, os, sys
from pathlib import Path
import db

base = Path(__file__).resolve().parent
conn = db.connect(Path(os.environ.get("DATABASE_PATH", base / "faculty.db")))
out = Path(sys.argv[1] if len(sys.argv) > 1 else "data_export.json")
out.write_text(json.dumps(db.build_profiles(conn), ensure_ascii=False, indent=2), encoding="utf-8")
print("wrote", out)
