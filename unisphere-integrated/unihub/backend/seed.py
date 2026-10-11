"""Rebuild the database from a JSON file.   python seed.py [path/to/data.json]"""
import os, sys
from pathlib import Path
import db

base = Path(__file__).resolve().parent
src = Path(sys.argv[1]) if len(sys.argv) > 1 else base.parent / "frontend" / "data.json"
dbp = Path(os.environ.get("DATABASE_PATH", base / "faculty.db"))
if dbp.exists():
    dbp.unlink()
conn = db.connect(dbp)
db.init_db(conn)
print(f"Imported {db.seed_from_json(conn, src)} profiles into {dbp}")
