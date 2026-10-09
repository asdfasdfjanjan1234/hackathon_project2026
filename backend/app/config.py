import os


class Config:
    ELECTRICITY_RATE = float(os.getenv("ELECTRICITY_RATE", 12.0))
    BASELINE_BILL = float(os.getenv("BASELINE_BILL", 1500))
    MONTHLY_BUDGET = float(os.getenv("MONTHLY_BUDGET", 2000))
    BILLING_CYCLE_START_DAY = int(os.getenv("BILLING_CYCLE_START_DAY", 1))
    USE_SAMPLE_DATA = os.getenv("USE_SAMPLE_DATA", "true").lower() == "true"
