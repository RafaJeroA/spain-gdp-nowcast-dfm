from pathlib import Path

import numpy as np
import pandas as pd

MISSING = 99999.0
ROOT = Path(__file__).resolve().parents[1]
RAW_FILE = ROOT / "data" / "spain_raw_data.xlsx"
OUTPUT_FILE = ROOT / "data" / "spain_data.xlsx"

MODEL_COLUMNS = [
    "gdp_qoq",
    "ipi",
    "affiliation",
    "retail_sales",
    "imports",
    "tourism_overnights",
    "esi",
]


def log_growth(series: pd.Series, periods: int = 1) -> pd.Series:
    values = series.astype(float).where(series.astype(float) > 0)
    return 100.0 * (np.log(values) - np.log(values.shift(periods)))


def main() -> None:
    raw = pd.read_excel(RAW_FILE, sheet_name="raw_data")
    raw["date"] = pd.to_datetime(raw["date"])
    raw = raw.sort_values("date").set_index("date")

    panel = pd.DataFrame(index=raw.index)
    quarterly_gdp = raw["gdp_level"].dropna()

    panel["gdp_qoq"] = log_growth(quarterly_gdp, 1).reindex(raw.index)
    panel["ipi"] = log_growth(raw["ipi_level"], 1)
    panel["affiliation"] = log_growth(raw["affiliation_level"], 12)
    panel["retail_sales"] = log_growth(raw["retail_sales_level"], 1)
    panel["imports"] = log_growth(raw["imports_level"], 12)
    panel["tourism_overnights"] = log_growth(raw["tourism_overnights_level"], 12)

    # ESI stays in levels. In the MATLAB measurement equation it is treated
    # as a soft indicator and loads on the current factor plus 11 monthly lags.
    panel["esi"] = raw["esi"].astype(float)

    # Keep the treatment used in the final course specification.
    panel.loc[panel.index.year == 2020, MODEL_COLUMNS] = np.nan
    yoy_columns = ["affiliation", "imports", "tourism_overnights"]
    panel.loc[panel.index.year == 2021, yoy_columns] = np.nan

    panel = panel.reset_index(names="date")
    panel[MODEL_COLUMNS] = panel[MODEL_COLUMNS].fillna(MISSING)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    panel.to_excel(OUTPUT_FILE, sheet_name="data", index=False)
    print(f"Wrote {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
