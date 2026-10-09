import os

from dotenv import load_dotenv

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BACKEND_DIR, ".env"))


class Config:
    ELECTRICITY_RATE = float(os.getenv("ELECTRICITY_RATE", 12.0))
    BASELINE_BILL = float(os.getenv("BASELINE_BILL", 1500))
    MONTHLY_BUDGET = float(os.getenv("MONTHLY_BUDGET", 2000))
    BILLING_CYCLE_START_DAY = int(os.getenv("BILLING_CYCLE_START_DAY", 1))
    # Where readings are stored: a mysql:// URL, or a SQLite file path (the default)
    DATABASE = os.getenv("DATABASE_URL") or os.getenv("DB_PATH") or os.path.join(BACKEND_DIR, "data", "wattage.db")
    # Bill actually received this month, and the rate that applied before AI use
    CURRENT_BILL = float(os.getenv("CURRENT_BILL", 2500))
    BASELINE_RATE = float(os.getenv("BASELINE_RATE", os.getenv("ELECTRICITY_RATE", 12.0)))
    # For "≈ X kg CO₂" and "= Y hours of aircon". Defaults: Philippine DOE 2015-2017 National Grid
    # Emission Factor (Luzon-Visayas operating margin), and a 1 HP non-inverter aircon (~180 kWh a
    # month at 8 hours a day, Midea Philippines).
    GRID_CO2_KG_PER_KWH = float(os.getenv("GRID_CO2_KG_PER_KWH", 0.7122))
    GRID_CO2_SOURCE = os.getenv("GRID_CO2_SOURCE", "DOE Philippines 2015-2017 grid emission factor, Luzon-Visayas")
    AIRCON_WATTS = float(os.getenv("AIRCON_WATTS", 750))
