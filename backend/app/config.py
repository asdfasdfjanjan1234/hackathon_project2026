import os

from dotenv import load_dotenv

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BACKEND_DIR, ".env"))


class Config:
    ELECTRICITY_RATE = float(os.getenv("ELECTRICITY_RATE", 12.0))
    BASELINE_BILL = float(os.getenv("BASELINE_BILL", 1500))
    MONTHLY_BUDGET = float(os.getenv("MONTHLY_BUDGET", 2000))
    BILLING_CYCLE_START_DAY = int(os.getenv("BILLING_CYCLE_START_DAY", 1))
    USE_SAMPLE_DATA = os.getenv("USE_SAMPLE_DATA", "true").lower() == "true"
    DB_PATH = os.getenv("DB_PATH", os.path.join(BACKEND_DIR, "data", "wattage.db"))
    # Bill actually received this month, and the rate that applied before AI use
    CURRENT_BILL = float(os.getenv("CURRENT_BILL", 2500))
    BASELINE_RATE = float(os.getenv("BASELINE_RATE", os.getenv("ELECTRICITY_RATE", 12.0)))
