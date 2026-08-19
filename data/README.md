# Data

`spain_raw_data.xlsx` contains the raw level series used by the project. `spain_data.xlsx` is the transformed panel read by MATLAB.

The exact source selected for each variable is recorded in `source_manifest.csv`. The download script uses those same selections.

The model input columns are:

- `gdp_qoq`
- `ipi`
- `affiliation`
- `retail_sales`
- `imports`
- `tourism_overnights`
- `esi`

ESI remains in levels. Its 12-month soft-indicator treatment is implemented in `matlab/state_space_matrices.m`, not in the Python preprocessing.

## Data attribution

The project uses public macroeconomic series from the original providers listed in `source_manifest.csv`:

- Eurostat / European Commission for GDP, industrial production, retail sales, tourism overnight stays and ESI;
- Spanish Social Security for monthly average total-system affiliation;
- OECD data distributed through FRED for Spanish monthly imports (`XTIMVA01ESM667S`).

The exact dataset identifiers, selections and source URLs are recorded in `source_manifest.csv`. Users reusing or redistributing the underlying data should follow the terms of the original providers.

