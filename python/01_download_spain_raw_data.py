#!/usr/bin/env python3
"""Download the seven raw series used by the Spain GDP nowcasting project.

The selected source for each variable is also written to data/source_manifest.csv.

Outputs:
    data/spain_raw_data.xlsx
    data/spain_raw_data.csv
    data/source_manifest.csv
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from dataclasses import asdict, dataclass
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DEFAULT_OUTPUT = DATA_DIR / "spain_raw_data.xlsx"
DEFAULT_MANIFEST = DATA_DIR / "source_manifest.csv"
VERIFIED_ON = "2026-08-19"

HEADERS = {
    "User-Agent": "SpainGDPNowcast/0.1 (academic research; contact via repository)",
    "Accept": "application/json,text/csv,application/vnd.openxmlformats-officedocument."
    "spreadsheetml.sheet,*/*",
}


@dataclass(frozen=True)
class SourceSpec:
    field: str
    frequency: str
    provider: str
    dataset_or_series: str
    selection: str
    download_url: str
    landing_page: str
    raw_measure: str
    model_transformation: str
    verified_on: str = VERIFIED_ON
    notes: str = ""


AFFILIATION_DOWNLOAD_URL = (
    "https://www.seg-social.es/wps/wcm/connect/wss/"
    "5ccf558a-868f-48b3-b832-04fe9f524960/"
    "19_Serie%2Bafiliaci%C3%B3n%2Bmedia%2Bpor%2Breg%C3%ADmenes%2B"
    "%28Total%2BSistema%29.xlsx?"
    "CACHEID=ROOTWORKSPACE.Z18_81D21J401P5L40QTIT61G41000-"
    "5ccf558a-868f-48b3-b832-04fe9f524960-p.bxcg2&"
    "CONVERT_TO=linktext&MOD=AJPERES"
)
AFFILIATION_LANDING_PAGE = (
    "https://www.seg-social.es/wps/portal/wss/internet/"
    "EstadisticasPresupuestosEstudios/Estadisticas/EST8/EST10/EST290/EST291"
)

SOURCE_SPECS: tuple[SourceSpec, ...] = (
    SourceSpec(
        field="gdp_level",
        frequency="quarterly",
        provider="Eurostat",
        dataset_or_series="namq_10_gdp",
        selection="freq=Q; unit=CLV10_MEUR; s_adj=SCA; na_item=B1GQ; geo=ES",
        download_url=(
            "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
            "namq_10_gdp?freq=Q&unit=CLV10_MEUR&s_adj=SCA&na_item=B1GQ&geo=ES&lang=en"
        ),
        landing_page=(
            "https://ec.europa.eu/eurostat/databrowser/view/namq_10_gdp/default/table?lang=en"
        ),
        raw_measure="Chain-linked volumes (2010), million euro; seasonally/calendar adjusted",
        model_transformation="100 × quarter-on-quarter log growth",
        notes="Quarterly observations are placed in the quarter-end month.",
    ),
    SourceSpec(
        field="ipi_level",
        frequency="monthly",
        provider="Eurostat",
        dataset_or_series="sts_inpr_m",
        selection="freq=M; unit=I21; s_adj=SCA; indic_bt=PRD; nace_r2=B-D; geo=ES",
        download_url=(
            "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
            "sts_inpr_m?freq=M&unit=I21&s_adj=SCA&indic_bt=PRD&nace_r2=B-D&geo=ES&lang=en"
        ),
        landing_page=(
            "https://ec.europa.eu/eurostat/databrowser/view/sts_inpr_m/default/table?lang=en"
        ),
        raw_measure="Industrial production index, 2021=100; seasonally/calendar adjusted",
        model_transformation="100 × one-month log growth",
    ),
    SourceSpec(
        field="affiliation_level",
        frequency="monthly",
        provider="Spanish Social Security",
        dataset_or_series="Serie de afiliación media por regímenes 2001–2026",
        selection="Total Sistema; monthly average; all regimes",
        download_url=AFFILIATION_DOWNLOAD_URL,
        landing_page=AFFILIATION_LANDING_PAGE,
        raw_measure="Average number of Social Security affiliates, Total System",
        model_transformation="100 × twelve-month log growth",
    ),
    SourceSpec(
        field="retail_sales_level",
        frequency="monthly",
        provider="Eurostat",
        dataset_or_series="sts_trtu_m",
        selection=(
            "freq=M; unit=I21; s_adj=SCA; indic_bt=VOL_SLS; "
            "nace_r2=G47_X_G473; geo=ES"
        ),
        download_url=(
            "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
            "sts_trtu_m?freq=M&unit=I21&s_adj=SCA&indic_bt=VOL_SLS&"
            "nace_r2=G47_X_G473&geo=ES&lang=en"
        ),
        landing_page=(
            "https://ec.europa.eu/eurostat/databrowser/view/sts_trtu_m/default/table?lang=en"
        ),
        raw_measure="Retail trade volume index excluding motor fuel, 2021=100; adjusted",
        model_transformation="100 × one-month log growth",
    ),
    SourceSpec(
        field="imports_level",
        frequency="monthly",
        provider="OECD via FRED",
        dataset_or_series="XTIMVA01ESM667S",
        selection=(
            "REF_AREA=ESP; COUNTERPART_AREA=W; UNIT_MEASURE=USD_EXC; TRADE_FLOW=M; "
            "PRODUCT_TYPE=C; ADJUSTMENT=Y; TRANSFORMATION=N; FREQ=M"
        ),
        download_url=(
            "https://fred.stlouisfed.org/graph/fredgraph.csv?id=XTIMVA01ESM667S"
        ),
        landing_page="https://fred.stlouisfed.org/series/XTIMVA01ESM667S",
        raw_measure="Commodity imports, US dollars (exchange-rate converted), seasonally adjusted",
        model_transformation="100 × twelve-month log growth",
        notes="Monthly imports series used in the final model.",
    ),
    SourceSpec(
        field="tourism_overnights_level",
        frequency="monthly",
        provider="Eurostat",
        dataset_or_series="tour_occ_nim",
        selection="freq=M; unit=NR; nace_r2=I551-I553; c_resid=TOTAL; geo=ES",
        download_url=(
            "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
            "tour_occ_nim?freq=M&unit=NR&nace_r2=I551-I553&c_resid=TOTAL&geo=ES&lang=en"
        ),
        landing_page=(
            "https://ec.europa.eu/eurostat/databrowser/view/tour_occ_nim/default/table?lang=en"
        ),
        raw_measure="Nights spent at tourist accommodation establishments, all residents",
        model_transformation="100 × twelve-month log growth",
    ),
    SourceSpec(
        field="esi",
        frequency="monthly",
        provider="European Commission / Eurostat",
        dataset_or_series="ei_bssi_m_r2",
        selection="freq=M; indic=BS-ESI-I; s_adj=SA; geo=ES",
        download_url=(
            "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
            "ei_bssi_m_r2?freq=M&indic=BS-ESI-I&s_adj=SA&geo=ES&lang=en"
        ),
        landing_page=(
            "https://ec.europa.eu/eurostat/databrowser/view/ei_bssi_m_r2/default/table?lang=en"
        ),
        raw_measure="Seasonally adjusted Economic Sentiment Indicator, level",
        model_transformation=(
            "Level; MATLAB measurement equation loads ESI on the current factor "
            "and 11 monthly lags"
        ),
    ),
)

SPEC_BY_FIELD = {spec.field: spec for spec in SOURCE_SPECS}


def source_manifest_frame() -> pd.DataFrame:
    """Return the single-source registry in a stable column order."""

    columns = [field.name for field in SourceSpec.__dataclass_fields__.values()]
    return pd.DataFrame([asdict(spec) for spec in SOURCE_SPECS], columns=columns)


def parse_period_to_month(period: object) -> pd.Timestamp:
    """Map monthly and quarterly source labels to a monthly timestamp."""

    text = str(period).strip()
    if re.fullmatch(r"\d{6}", text):
        return pd.Timestamp(int(text[:4]), int(text[4:6]), 1)
    monthly = re.fullmatch(r"(\d{4})[-M](\d{2})", text)
    if monthly:
        return pd.Timestamp(int(monthly.group(1)), int(monthly.group(2)), 1)
    quarterly = re.fullmatch(r"(\d{4})-?Q([1-4])", text)
    if quarterly:
        return pd.Timestamp(int(quarterly.group(1)), 3 * int(quarterly.group(2)), 1)
    timestamp = pd.to_datetime(text)
    return pd.Timestamp(timestamp.year, timestamp.month, 1)


def _category_index(payload: dict[str, Any], dimension_id: str) -> dict[str, int]:
    raw = payload["dimension"][dimension_id].get("category", {}).get("index", {})
    if isinstance(raw, dict):
        return {str(key): int(value) for key, value in raw.items()}
    if isinstance(raw, list):
        return {str(key): value for value, key in enumerate(raw)}
    raise ValueError(f"Unsupported category index for {dimension_id!r}")


def jsonstat_to_series(payload: dict[str, Any]) -> pd.Series:
    """Extract a one-series Eurostat JSON-stat response."""

    dimension_ids = payload.get("id") or []
    sizes = payload.get("size") or []
    dimensions = payload.get("dimension") or {}
    if not dimension_ids or not sizes or not dimensions:
        raise ValueError("Eurostat response is not a populated JSON-stat dataset")

    time_id = next(
        (candidate for candidate in ("time", "TIME") if candidate in dimension_ids),
        None,
    )
    if time_id is None:
        raise ValueError(f"Eurostat response has no time dimension: {dimension_ids}")

    indices = {
        dimension_id: _category_index(payload, dimension_id)
        for dimension_id in dimension_ids
    }
    fixed_positions: dict[str, int] = {}
    for dimension_id in dimension_ids:
        if dimension_id == time_id:
            continue
        categories = indices[dimension_id]
        if len(categories) != 1:
            raise ValueError(
                f"Endpoint did not select exactly one {dimension_id!r} value: {list(categories)}"
            )
        fixed_positions[dimension_id] = next(iter(categories.values()))

    strides: dict[str, int] = {}
    stride = 1
    for dimension_id, size in reversed(list(zip(dimension_ids, sizes, strict=True))):
        strides[dimension_id] = stride
        stride *= int(size)

    raw_values = payload.get("value", {}) or {}
    dates: list[pd.Timestamp] = []
    values: list[float] = []
    for time_label, time_position in sorted(indices[time_id].items(), key=lambda item: item[1]):
        offset = sum(
            (time_position if dimension_id == time_id else fixed_positions[dimension_id])
            * strides[dimension_id]
            for dimension_id in dimension_ids
        )
        if isinstance(raw_values, list):
            raw_value = raw_values[offset] if offset < len(raw_values) else None
        else:
            raw_value = raw_values.get(str(offset))
        dates.append(parse_period_to_month(time_label))
        values.append(np.nan if raw_value is None else float(raw_value))

    return pd.Series(values, index=pd.DatetimeIndex(dates), dtype=float).sort_index()


def _get(session: requests.Session, url: str) -> requests.Response:
    response = session.get(url, headers=HEADERS, timeout=90)
    response.raise_for_status()
    return response


def fetch_eurostat(
    session: requests.Session,
    spec: SourceSpec,
    start_period: str,
) -> pd.Series:
    response = _get(session, spec.download_url)
    series = jsonstat_to_series(response.json())
    series = series.loc[series.index >= parse_period_to_month(start_period)]
    if series.dropna().empty:
        raise ValueError(f"Eurostat returned no observations for {spec.field}")
    series.name = spec.field
    return series


def fetch_fred_imports(
    session: requests.Session,
    spec: SourceSpec,
    start_period: str,
) -> pd.Series:
    response = _get(session, spec.download_url)
    frame = pd.read_csv(StringIO(response.text))
    date_column = "observation_date" if "observation_date" in frame.columns else frame.columns[0]
    if spec.dataset_or_series not in frame.columns:
        raise ValueError(
            f"FRED response does not contain expected series {spec.dataset_or_series!r}"
        )
    dates = pd.to_datetime(frame[date_column], errors="raise")
    values = pd.to_numeric(frame[spec.dataset_or_series].replace(".", np.nan), errors="coerce")
    index = pd.DatetimeIndex(pd.Timestamp(date.year, date.month, 1) for date in dates)
    series = pd.Series(values.to_numpy(), index=index, name=spec.field, dtype=float).sort_index()
    series = series.loc[~series.index.duplicated(keep="last")]
    series = series.loc[series.index >= parse_period_to_month(start_period)]
    if series.dropna().empty:
        raise ValueError("FRED returned no observations for imports")
    return series


def normalise_label(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value).strip().lower())
    text = "".join(character for character in text if not unicodedata.combining(character))
    return re.sub(r"\s+", " ", text)


def parse_numeric_value(value: object) -> float:
    if pd.isna(value):
        return np.nan
    if isinstance(value, (int, float, np.integer, np.floating)):
        return float(value)
    text = re.sub(r"[^0-9,.\-]", "", str(value).strip().replace("\u00a0", " "))
    if not text:
        return np.nan
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(".", "").replace(",", ".")
    elif text.count(".") > 1:
        text = text.replace(".", "")
    return float(text)


def parse_affiliation_period(value: object) -> pd.Timestamp:
    if isinstance(value, pd.Timestamp):
        return pd.Timestamp(value.year, value.month, 1)
    if hasattr(value, "year") and hasattr(value, "month") and not isinstance(value, str):
        return pd.Timestamp(int(value.year), int(value.month), 1)
    if pd.isna(value):
        raise ValueError("Empty affiliation period")
    if isinstance(value, (int, float, np.integer, np.floating)):
        number = int(round(float(value)))
        if 100000 <= number <= 999999:
            return pd.Timestamp(number // 100, number % 100, 1)

    text = str(value).strip()
    if re.fullmatch(r"\d{6}\.0", text):
        text = text[:-2]
    try:
        return parse_period_to_month(text)
    except (ValueError, TypeError):
        pass

    months = {
        "enero": 1,
        "febrero": 2,
        "marzo": 3,
        "abril": 4,
        "mayo": 5,
        "junio": 6,
        "julio": 7,
        "agosto": 8,
        "septiembre": 9,
        "setiembre": 9,
        "octubre": 10,
        "noviembre": 11,
        "diciembre": 12,
    }
    normalised = normalise_label(text)
    year_match = re.search(r"(20\d{2}|19\d{2})", normalised)
    month = next((number for name, number in months.items() if name in normalised), None)
    if year_match and month:
        return pd.Timestamp(int(year_match.group(1)), month, 1)
    raise ValueError(f"Could not parse affiliation period: {value!r}")


def workbook_to_affiliation_series(content: bytes, start_year: int) -> pd.Series:
    """Extract the Periodo / Total Sistema columns from the official workbook."""

    if not content.startswith(b"PK"):
        raise ValueError("Affiliation endpoint did not return an XLSX workbook")
    sheets = pd.read_excel(BytesIO(content), sheet_name=None, header=None)
    errors: list[str] = []
    for sheet_name, raw in sheets.items():
        try:
            period_position: tuple[int, int] | None = None
            total_position: tuple[int, int] | None = None
            for row_index in range(min(len(raw), 30)):
                labels = [normalise_label(value) for value in raw.iloc[row_index].tolist()]
                for column_index, label in enumerate(labels):
                    if period_position is None and label.startswith("periodo"):
                        period_position = (row_index, column_index)
                    if total_position is None and "total sistema" in label:
                        total_position = (row_index, column_index)
                if period_position and total_position:
                    break
            if period_position is None or total_position is None:
                continue

            first_data_row = max(period_position[0], total_position[0]) + 1
            period_column = period_position[1]
            total_column = total_position[1]
            rows: list[tuple[pd.Timestamp, float]] = []
            for _, row in raw.iloc[first_data_row:, [period_column, total_column]].iterrows():
                try:
                    date = parse_affiliation_period(row.iloc[0])
                    value = parse_numeric_value(row.iloc[1])
                except (ValueError, TypeError):
                    continue
                if np.isfinite(value):
                    rows.append((date, value))
            if not rows:
                continue

            series = pd.Series(
                [value for _, value in rows],
                index=pd.DatetimeIndex(date for date, _ in rows),
                name="affiliation_level",
                dtype=float,
            ).sort_index()
            series = series.loc[~series.index.duplicated(keep="last")]
            series = series.loc[series.index.year >= start_year]
            if series.dropna().empty or float(series.dropna().median()) < 10_000:
                raise ValueError("Parsed values do not look like Total System affiliation")
            return series
        except Exception as exc:  # noqa: BLE001 - retain sheet-level diagnostics
            errors.append(f"{sheet_name}: {exc}")
    raise ValueError("Could not parse the official affiliation workbook: " + "; ".join(errors))


def fetch_affiliation(
    session: requests.Session,
    spec: SourceSpec,
    start_year: int,
) -> pd.Series:
    response = _get(session, spec.download_url)
    return workbook_to_affiliation_series(response.content, start_year)


def month_range(start: pd.Timestamp, end: pd.Timestamp) -> pd.DatetimeIndex:
    return pd.date_range(
        pd.Timestamp(start.year, start.month, 1),
        pd.Timestamp(end.year, end.month, 1),
        freq="MS",
    )


def build_raw_dataset(
    start: str,
    end: str | None,
    output: Path,
    source_manifest: Path,
) -> None:
    start_timestamp = pd.Timestamp(start)
    end_timestamp = pd.Timestamp(end) if end else pd.Timestamp.today().normalize()
    start_quarter = f"{start_timestamp.year}-Q{((start_timestamp.month - 1) // 3) + 1}"
    start_month = f"{start_timestamp.year}-{start_timestamp.month:02d}"

    with requests.Session() as session:
        print("Downloading GDP from Eurostat namq_10_gdp...")
        gdp_level = fetch_eurostat(session, SPEC_BY_FIELD["gdp_level"], start_quarter)

        print("Downloading industrial production from Eurostat sts_inpr_m...")
        ipi_level = fetch_eurostat(session, SPEC_BY_FIELD["ipi_level"], start_month)

        print("Downloading Social Security affiliation from the official workbook...")
        affiliation_level = fetch_affiliation(
            session,
            SPEC_BY_FIELD["affiliation_level"],
            start_timestamp.year,
        )

        print("Downloading retail sales from Eurostat sts_trtu_m...")
        retail_sales_level = fetch_eurostat(
            session,
            SPEC_BY_FIELD["retail_sales_level"],
            start_month,
        )

        print("Downloading imports from OECD/FRED XTIMVA01ESM667S...")
        imports_level = fetch_fred_imports(
            session,
            SPEC_BY_FIELD["imports_level"],
            start_month,
        )

        print("Downloading tourism overnights from Eurostat tour_occ_nim...")
        tourism_overnights_level = fetch_eurostat(
            session,
            SPEC_BY_FIELD["tourism_overnights_level"],
            start_month,
        )

        print("Downloading ESI from Eurostat ei_bssi_m_r2...")
        esi = fetch_eurostat(session, SPEC_BY_FIELD["esi"], start_month)

    series = [
        gdp_level,
        ipi_level,
        affiliation_level,
        retail_sales_level,
        imports_level,
        tourism_overnights_level,
        esi,
    ]
    first_month = pd.Timestamp(start_timestamp.year, start_timestamp.month, 1)
    last_available = min(
        end_timestamp,
        max(item.dropna().index.max() for item in series if not item.dropna().empty),
    )
    full_index = month_range(first_month, last_available)

    raw = pd.DataFrame(
        {
            "date": full_index,
            "gdp_level": gdp_level.reindex(full_index).to_numpy(),
            "ipi_level": ipi_level.reindex(full_index).to_numpy(),
            "affiliation_level": affiliation_level.reindex(full_index).to_numpy(),
            "retail_sales_level": retail_sales_level.reindex(full_index).to_numpy(),
            "imports_level": imports_level.reindex(full_index).to_numpy(),
            "tourism_overnights_level": tourism_overnights_level.reindex(full_index).to_numpy(),
            "esi": esi.reindex(full_index).to_numpy(),
        }
    )

    availability_rows: list[dict[str, object]] = []
    for column in raw.columns.drop("date"):
        valid = raw[column].notna()
        availability_rows.append(
            {
                "variable": column,
                "first_valid": raw.loc[valid, "date"].min() if valid.any() else pd.NaT,
                "last_valid": raw.loc[valid, "date"].max() if valid.any() else pd.NaT,
                "n_valid": int(valid.sum()),
                "n_missing": int((~valid).sum()),
            }
        )
    availability = pd.DataFrame(availability_rows)
    manifest = source_manifest_frame()

    output.parent.mkdir(parents=True, exist_ok=True)
    source_manifest.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        raw.to_excel(writer, sheet_name="raw_data", index=False)
        availability.to_excel(writer, sheet_name="availability", index=False)
        manifest.to_excel(writer, sheet_name="sources", index=False)
    raw.to_csv(output.with_suffix(".csv"), index=False)
    manifest.to_csv(source_manifest, index=False)

    print(f"Wrote {output}")
    print(f"Wrote {output.with_suffix('.csv')}")
    print(f"Wrote {source_manifest}")
    print(availability.to_string(index=False))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Download the single documented source for every raw variable in the Spain GDP DFM."
        )
    )
    parser.add_argument("--start", default="2005-01-01", help="Sample start, YYYY-MM-DD")
    parser.add_argument("--end", default=None, help="Optional sample end, YYYY-MM-DD")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Raw Excel output path")
    parser.add_argument(
        "--source-manifest",
        default=str(DEFAULT_MANIFEST),
        help="CSV path for the exact source registry",
    )
    parser.add_argument(
        "--list-sources",
        action="store_true",
        help="Print the seven exact source specifications and exit without downloading",
    )
    args = parser.parse_args(argv)

    if args.list_sources:
        print(source_manifest_frame().to_string(index=False))
        return 0

    try:
        build_raw_dataset(
            start=args.start,
            end=args.end,
            output=Path(args.output),
            source_manifest=Path(args.source_manifest),
        )
        return 0
    except Exception as exc:  # noqa: BLE001 - CLI should report upstream failures cleanly
        print(f"ERROR while downloading raw data: {exc}", file=sys.stderr)
        print(
            "Check the selected endpoint in data/source_manifest.csv if a provider has changed it.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
