from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
DATA_POWERBI = ROOT / "data" / "powerbi"
SQL_DIR = ROOT / "sql"
PYTHON_DIR = ROOT / "python"
REPORT_DIR = ROOT / "report"
FIGURES_DIR = REPORT_DIR / "figures"

DB_CONFIG = dict(
    host="localhost",
    port=5432,
    dbname="opspulse",
    user="postgres",
    password="",
)

SEED = 42