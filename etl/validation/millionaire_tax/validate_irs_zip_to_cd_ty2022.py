from __future__ import annotations

import hashlib
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd


# =============================================================================
# PATHS
# =============================================================================

ROOT = Path(__file__).resolve().parents[3]

IRS_ZIP_XLSX = (
    ROOT
    / "data"
    / "raw"
    / "irs"
    / "zip"
    / "ty2022"
    / "22zp48wa.xlsx"
)

IRS_CD_CSV = (
    ROOT
    / "data"
    / "raw"
    / "irs"
    / "congressional_district"
    / "ty2022"
    / "22incd.csv"
)

CROSSWALK = (
    ROOT
    / "data"
    / "processed"
    / "validation"
    / "irs_cd_ty2022"
    / "wa_zcta_cd116_population_weights.csv"
)

OUT_DIR = (
    ROOT
    / "data"
    / "processed"
    / "validation"
    / "irs_cd_ty2022"
)

OUT_CD_COMPARISON = (
    OUT_DIR
    / "irs_ty2022_zip_to_cd_comparison.csv"
)

OUT_METRICS = (
    OUT_DIR
    / "irs_ty2022_zip_to_cd_validation_metrics.csv"
)

OUT_ALLOCATION = (
    OUT_DIR
    / "irs_ty2022_zip_to_cd_allocated_detail.csv"
)

OUT_UNRESOLVED = (
    OUT_DIR
    / "irs_ty2022_zip_unresolved_geography.csv"
)


# =============================================================================
# FROZEN SOURCE CONTROLS
# =============================================================================

EXPECTED_ZIP_SHA256 = (
    "cadcf9dd5b197a084dccb62268c1fc18"
    "be039a17722b15eb05e674fdc855dfa5"
)

EXPECTED_CROSSWALK_SHA256 = (
    "d93a662e824e7c9bb3e55cdbb351808"
    "af30b0952961a95fca51f378756f2c10d"
)

EXPECTED_ZIP_STATE_N1 = 423_160
EXPECTED_ZIP_STATE_A00100 = 197_286_593

EXPECTED_CD_STATE_STUB8_N1 = 339_460
EXPECTED_CD_STATE_STUB8_A00100 = 99_295_231

EXPECTED_CD_STATE_STUB9_N1 = 78_770
EXPECTED_CD_STATE_STUB9_A00100 = 102_610_653

EXPECTED_RESOLVED_ZIP_COUNT = 498
EXPECTED_UNRESOLVED_ZIP = "99999"

EXPECTED_CDS = {
    "01",
    "02",
    "03",
    "04",
    "05",
    "06",
    "07",
    "08",
    "09",
    "10",
}


# =============================================================================
# IRS ZIP WORKBOOK COLUMN POSITIONS
#
# These are zero-based pandas column positions.
#
# Important:
# A00100 is column 18. It is an amount-only field at this position.
# =============================================================================

COL_ZIP = 0
COL_AGI_LABEL = 1

COL_N1 = 2
COL_A00100 = 18

COL_N00300 = 23
COL_A00300 = 24

COL_N00600 = 27
COL_A00600 = 28

# Business or profession net income (less loss)
COL_N00900 = 33
COL_A00900 = 34

# Net capital gain (less loss) in AGI
COL_N01000 = 35
COL_A01000 = 36

# Taxable pensions and annuities
COL_N01700 = 39
COL_A01700 = 40

# Partnership/S-corp net income (less loss)
COL_N26270 = 46
COL_A26270 = 47


# =============================================================================
# VALIDATION VARIABLES
#
# Counts and dollar amounts are kept distinct.
# IRS A-fields are in thousands of dollars.
# =============================================================================

VARIABLES = [
    "N1",
    "A00100",
    "A00300",
    "A00600",
    "A00900",
    "A01000",
    "A01700",
    "A26270",
]

ZIP_COLUMN_MAP = {
    "N1": COL_N1,
    "A00100": COL_A00100,
    "A00300": COL_A00300,
    "A00600": COL_A00600,
    "A00900": COL_A00900,
    "A01000": COL_A01000,
    "A01700": COL_A01700,
    "A26270": COL_A26270,
}


# =============================================================================
# HELPERS
# =============================================================================

def sha256(path: Path) -> str:
    h = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(
            lambda: f.read(1024 * 1024),
            b"",
        ):
            h.update(chunk)

    return h.hexdigest()


def require_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(
            f"Required file not found: {path}"
        )


def clean_zip(value) -> str | None:
    if pd.isna(value):
        return None

    text = str(value).strip()

    if text.endswith(".0"):
        text = text[:-2]

    if not text.isdigit():
        return None

    return text.zfill(5)


def clean_cd(value) -> str | None:
    if pd.isna(value):
        return None

    text = str(value).strip()

    if text.endswith(".0"):
        text = text[:-2]

    if not text.isdigit():
        return None

    return text.zfill(2)


def safe_float(value) -> float:
    if pd.isna(value):
        return 0.0

    return float(value)


def pct(value: float) -> str:
    return f"{value:.6%}"


def fmt_number(value: float) -> str:
    if pd.isna(value):
        return "NA"

    return f"{value:,.3f}"


# =============================================================================
# CROSSWALK SCHEMA DETECTION
# =============================================================================

def detect_column(
    columns: list[str],
    candidates: list[str],
    purpose: str,
) -> str:
    lookup = {
        str(col).strip().lower(): col
        for col in columns
    }

    for candidate in candidates:
        key = candidate.lower()

        if key in lookup:
            return lookup[key]

    raise RuntimeError(
        f"Could not identify {purpose} column. "
        f"Available columns: {columns}"
    )


# =============================================================================
# READ IRS ZIP DATA
# =============================================================================

def read_zip_data() -> tuple[
    pd.DataFrame,
    pd.Series,
]:
    print()
    print("=" * 100)
    print("READ IRS TY2022 WASHINGTON ZIP SOI")
    print("=" * 100)

    raw = pd.read_excel(
        IRS_ZIP_XLSX,
        sheet_name="Sheet1",
        header=None,
    )

    print(
        f"Workbook rows                    : "
        f"{len(raw):,}"
    )
    print(
        f"Workbook columns                 : "
        f"{raw.shape[1]:,}"
    )

    rows = pd.DataFrame()

    rows["zip"] = (
        raw.iloc[:, COL_ZIP]
        .map(clean_zip)
    )

    rows["agi_label"] = (
        raw.iloc[:, COL_AGI_LABEL]
        .astype("string")
        .str.strip()
    )

    for variable, col in ZIP_COLUMN_MAP.items():
        rows[variable] = pd.to_numeric(
            raw.iloc[:, col],
            errors="coerce",
        )

    rows = rows.loc[
        rows["zip"].notna()
        & rows["agi_label"].notna()
    ].copy()

    print(
        f"Parsed IRS rows                  : "
        f"{len(rows):,}"
    )

    state = rows.loc[
        rows["zip"].eq("00000")
        & rows["agi_label"].eq(
            "$200,000 or more"
        )
    ].copy()

    if len(state) != 1:
        raise RuntimeError(
            "Could not uniquely identify ZIP-product "
            "statewide $200K+ control."
        )

    state_row = state.iloc[0]

    print()
    print("ZIP PRODUCT STATEWIDE $200K+ CONTROL")
    print("-" * 100)

    print(
        f"N1                               : "
        f"{int(state_row['N1']):,}"
    )

    print(
        f"A00100 (thousands)               : "
        f"{int(state_row['A00100']):,}"
    )

    if int(state_row["N1"]) != EXPECTED_ZIP_STATE_N1:
        raise RuntimeError(
            "Unexpected ZIP-product statewide N1."
        )

    if (
        int(state_row["A00100"])
        != EXPECTED_ZIP_STATE_A00100
    ):
        raise RuntimeError(
            "Unexpected ZIP-product statewide A00100."
        )

    print(
        "ZIP statewide control            : PASS"
    )

    high = rows.loc[
        rows["agi_label"].eq(
            "$200,000 or more"
        )
        & ~rows["zip"].eq("00000")
    ].copy()

    if high["zip"].duplicated().any():
        duplicates = high.loc[
            high["zip"].duplicated(
                keep=False
            ),
            ["zip", "agi_label"],
        ]

        print(duplicates.to_string(index=False))

        raise RuntimeError(
            "Duplicate ZIPs in IRS $200K+ universe."
        )

    print()
    print("ZIP PRODUCT DETAIL UNIVERSE")
    print("-" * 100)

    print(
        f"ZIP observations                 : "
        f"{len(high):,}"
    )

    print(
        f"Distinct ZIPs                    : "
        f"{high['zip'].nunique():,}"
    )

    print(
        f"ZIP-detail N1                    : "
        f"{int(high['N1'].sum()):,}"
    )

    print(
        f"ZIP-detail A00100                : "
        f"{int(high['A00100'].sum()):,}"
    )

    return high, state_row


# =============================================================================
# READ ZCTA x CD CROSSWALK
# =============================================================================

def read_crosswalk() -> pd.DataFrame:
    print()
    print("=" * 100)
    print("READ FROZEN ZCTA x CD116 POPULATION CROSSWALK")
    print("=" * 100)

    crosswalk = pd.read_csv(
        CROSSWALK,
        dtype=str,
    )

    columns = list(crosswalk.columns)

    zcta_col = detect_column(
        columns,
        [
            "zcta5ce20",
            "zcta",
            "zcta5",
            "zip",
        ],
        "ZCTA",
    )

    cd_col = detect_column(
        columns,
        [
            "cd116",
            "district",
            "congressional_district",
            "cd",
        ],
        "Congressional District",
    )

    weight_col = detect_column(
        columns,
        [
            "zcta_cd_population_weight",
            "population_weight",
            "pop_weight",
            "weight",
        ],
        "population weight",
    )

    print(
        f"Detected ZCTA column             : "
        f"{zcta_col}"
    )
    print(
        f"Detected CD column               : "
        f"{cd_col}"
    )
    print(
        f"Detected weight column           : "
        f"{weight_col}"
    )

    crosswalk = crosswalk[
        [
            zcta_col,
            cd_col,
            weight_col,
        ]
    ].copy()

    crosswalk.columns = [
        "zcta",
        "cd",
        "weight",
    ]

    crosswalk["zcta"] = (
        crosswalk["zcta"]
        .astype(str)
        .str.strip()
        .str.zfill(5)
    )

    crosswalk["cd"] = (
        crosswalk["cd"]
        .map(clean_cd)
    )

    crosswalk["weight"] = pd.to_numeric(
        crosswalk["weight"],
        errors="coerce",
    )

    if crosswalk["cd"].isna().any():
        raise RuntimeError(
            "Crosswalk contains invalid CD values."
        )

    # -------------------------------------------------------------------------
    # Zero-population ZCTA treatment
    #
    # Stage 3 deliberately retained legitimate Census ZCTAs having zero
    # population. Their population-based CD allocation weight is undefined
    # (0 / 0), so population_weight is NaN by design.
    #
    # They must NOT be assigned an invented weight.
    # -------------------------------------------------------------------------

    unresolved_zero_pop = crosswalk.loc[
        crosswalk["weight"].isna()
    ].copy()

    expected_zero_pop_zctas = {
        "98154",
        "98158",
        "98174",
        "98430",
    }

    observed_zero_pop_zctas = set(
        unresolved_zero_pop["zcta"].unique()
    )

    print(
        f"Undefined-weight rows            : "
        f"{len(unresolved_zero_pop):,}"
    )

    print(
        f"Undefined-weight ZCTAs           : "
        f"{len(observed_zero_pop_zctas):,}"
    )

    if observed_zero_pop_zctas != expected_zero_pop_zctas:
        raise RuntimeError(
            "Unexpected undefined-weight ZCTA universe. "
            f"Expected {sorted(expected_zero_pop_zctas)}, "
            f"observed {sorted(observed_zero_pop_zctas)}."
        )

    if len(unresolved_zero_pop) != 4:
        raise RuntimeError(
            "Expected exactly four zero-population "
            "ZCTA crosswalk rows."
        )

    print(
        "Zero-population ZCTAs            : "
        + ", ".join(
            sorted(observed_zero_pop_zctas)
        )
    )

    print(
        "Zero-population treatment        : PASS"
    )

    # Only positive-population ZCTAs are eligible for population-weighted
    # allocation. Zero-population ZCTAs remain preserved in the frozen
    # source crosswalk but are excluded from the allocatable universe.
    crosswalk = crosswalk.loc[
        crosswalk["weight"].notna()
    ].copy()

    actual_cds = set(
        crosswalk["cd"].dropna().unique()
    )

    if actual_cds != EXPECTED_CDS:
        raise RuntimeError(
            "Unexpected Congressional District universe "
            f"in crosswalk: {sorted(actual_cds)}"
        )

    print(
        f"Allocatable crosswalk rows       : "
        f"{len(crosswalk):,}"
    )

    print(
        f"Positive-population ZCTAs        : "
        f"{crosswalk['zcta'].nunique():,}"
    )

    print(
        f"Districts                        : "
        f"{', '.join(sorted(actual_cds))}"
    )

    weight_sums = (
        crosswalk.groupby(
            "zcta",
            as_index=False,
        )["weight"]
        .sum()
    )

    max_error = float(
        (
            weight_sums["weight"] - 1.0
        )
        .abs()
        .max()
    )

    print(
        f"Maximum ZCTA weight-sum error    : "
        f"{max_error:.15f}"
    )

    if max_error > 1e-10:
        raise RuntimeError(
            "Crosswalk ZCTA weights do not sum to 1."
        )

    print(
        "Crosswalk weight validation      : PASS"
    )

    return crosswalk


# =============================================================================
# CLASSIFY IRS ZIP GEOGRAPHY
# =============================================================================

def classify_zip_geography(
    high: pd.DataFrame,
    crosswalk: pd.DataFrame,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
]:
    print()
    print("=" * 100)
    print("CLASSIFY IRS ZIP GEOGRAPHY")
    print("=" * 100)

    valid_zctas = set(
        crosswalk["zcta"].unique()
    )

    high = high.copy()

    high["geography_status"] = np.where(
        high["zip"].isin(valid_zctas),
        "RESOLVED_ZCTA",
        "UNRESOLVED",
    )

    resolved = high.loc[
        high["geography_status"].eq(
            "RESOLVED_ZCTA"
        )
    ].copy()

    unresolved = high.loc[
        high["geography_status"].eq(
            "UNRESOLVED"
        )
    ].copy()

    print(
        f"Resolved ZIPs                    : "
        f"{len(resolved):,}"
    )

    print(
        f"Unresolved ZIPs                  : "
        f"{len(unresolved):,}"
    )

    if len(resolved) != EXPECTED_RESOLVED_ZIP_COUNT:
        raise RuntimeError(
            "Unexpected resolved ZIP count. "
            f"Expected {EXPECTED_RESOLVED_ZIP_COUNT:,}, "
            f"observed {len(resolved):,}."
        )

    unresolved_codes = set(
        unresolved["zip"].unique()
    )

    if unresolved_codes != {
        EXPECTED_UNRESOLVED_ZIP
    }:
        raise RuntimeError(
            "Unexpected unresolved ZIP universe: "
            f"{sorted(unresolved_codes)}"
        )

    print()
    print("UNRESOLVED IRS GEOGRAPHY")
    print("-" * 100)

    display_cols = [
        "zip",
        "N1",
        "A00100",
        "A00300",
        "A00600",
        "A00900",
        "A01000",
        "A01700",
        "A26270",
    ]

    print(
        unresolved[
            display_cols
        ].to_string(index=False)
    )

    print()
    print(
        "Rule: unresolved ZIP geography is retained "
        "but receives NO invented CD allocation."
    )

    return resolved, unresolved


# =============================================================================
# ALLOCATE RESOLVED ZIP DATA TO CD
# =============================================================================

def allocate_zip_to_cd(
    resolved: pd.DataFrame,
    crosswalk: pd.DataFrame,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
]:
    print()
    print("=" * 100)
    print("ALLOCATE RESOLVED IRS ZIP DATA TO CD116")
    print("=" * 100)

    merged = resolved.merge(
        crosswalk,
        left_on="zip",
        right_on="zcta",
        how="left",
        validate="one_to_many",
        indicator=True,
    )

    join_counts = (
        merged["_merge"]
        .value_counts()
        .to_dict()
    )

    print(
        f"Allocation rows                  : "
        f"{len(merged):,}"
    )

    print(
        f"Join both                        : "
        f"{join_counts.get('both', 0):,}"
    )

    print(
        f"Join left_only                   : "
        f"{join_counts.get('left_only', 0):,}"
    )

    if (
        merged["_merge"]
        .ne("both")
        .any()
    ):
        raise RuntimeError(
            "Resolved ZIP failed crosswalk join."
        )

    for variable in VARIABLES:
        merged[
            f"allocated_{variable}"
        ] = (
            merged[variable]
            * merged["weight"]
        )

    allocated_cols = [
        f"allocated_{v}"
        for v in VARIABLES
    ]

    predicted = (
        merged.groupby(
            "cd",
            as_index=False,
        )[allocated_cols]
        .sum()
    )

    predicted = predicted.rename(
        columns={
            f"allocated_{v}":
                f"predicted_{v}"
            for v in VARIABLES
        }
    )

    predicted_cds = set(
        predicted["cd"].unique()
    )

    if predicted_cds != EXPECTED_CDS:
        raise RuntimeError(
            "Predicted CD universe is incomplete."
        )

    print()
    print("RESOLVED MASS CONSERVATION")
    print("-" * 100)

    for variable in VARIABLES:
        source_total = float(
            resolved[variable].sum()
        )

        allocated_total = float(
            predicted[
                f"predicted_{variable}"
            ].sum()
        )

        difference = (
            allocated_total
            - source_total
        )

        print(
            f"{variable:<10} "
            f"source={source_total:>16,.3f} "
            f"allocated={allocated_total:>16,.3f} "
            f"diff={difference:>12,.6f}"
        )

        tolerance = max(
            1e-6,
            abs(source_total) * 1e-12,
        )

        if abs(difference) > tolerance:
            raise RuntimeError(
                f"Mass conservation failed for "
                f"{variable}."
            )

    print()
    print(
        "Resolved mass conservation       : PASS"
    )

    return merged, predicted


# =============================================================================
# READ OFFICIAL IRS CONGRESSIONAL DISTRICT ANSWER KEY
# =============================================================================

def read_cd_answer_key() -> tuple[
    pd.DataFrame,
    pd.DataFrame,
]:
    print()
    print("=" * 100)
    print("READ OFFICIAL IRS TY2022 CONGRESSIONAL DISTRICT DATA")
    print("=" * 100)

    dtype_map = {
        "STATEFIPS": str,
        "STATE": str,
        "CONG_DISTRICT": str,
    }

    data = pd.read_csv(
        IRS_CD_CSV,
        dtype=dtype_map,
        low_memory=False,
    )

    required = {
        "STATE",
        "CONG_DISTRICT",
        "agi_stub",
        *VARIABLES,
    }

    missing = (
        required
        - set(data.columns)
    )

    if missing:
        raise RuntimeError(
            "Required IRS CD columns missing: "
            f"{sorted(missing)}"
        )

    wa = data.loc[
        data["STATE"].eq("WA")
    ].copy()

    wa["cd"] = (
        wa["CONG_DISTRICT"]
        .map(clean_cd)
    )

    wa["agi_stub"] = pd.to_numeric(
        wa["agi_stub"],
        errors="raise",
    ).astype(int)

    print(
        f"Washington rows                  : "
        f"{len(wa):,}"
    )

    print(
        f"District values                  : "
        f"{', '.join(sorted(wa['cd'].unique()))}"
    )

    print(
        f"AGI stubs                        : "
        f"{sorted(wa['agi_stub'].unique())}"
    )

    if len(wa) != 110:
        raise RuntimeError(
            "Expected 110 Washington CD rows."
        )

    expected_cd_universe = (
        {"00"} | EXPECTED_CDS
    )

    if set(wa["cd"].unique()) != expected_cd_universe:
        raise RuntimeError(
            "Unexpected IRS CD district universe."
        )

    if set(
        wa["agi_stub"].unique()
    ) != set(range(10)):
        raise RuntimeError(
            "Unexpected IRS CD AGI stub universe."
        )

    print()
    print("VERIFY OFFICIAL CD STATEWIDE UPPER-TAIL STUBS")
    print("-" * 100)

    state8 = wa.loc[
        wa["cd"].eq("00")
        & wa["agi_stub"].eq(8)
    ]

    state9 = wa.loc[
        wa["cd"].eq("00")
        & wa["agi_stub"].eq(9)
    ]

    if len(state8) != 1 or len(state9) != 1:
        raise RuntimeError(
            "Could not uniquely identify statewide "
            "CD stubs 8 and 9."
        )

    state8 = state8.iloc[0]
    state9 = state9.iloc[0]

    print(
        f"Stub 8 N1                       : "
        f"{int(state8['N1']):,}"
    )
    print(
        f"Stub 8 A00100                   : "
        f"{int(state8['A00100']):,}"
    )
    print(
        f"Stub 9 N1                       : "
        f"{int(state9['N1']):,}"
    )
    print(
        f"Stub 9 A00100                   : "
        f"{int(state9['A00100']):,}"
    )

    if int(state8["N1"]) != EXPECTED_CD_STATE_STUB8_N1:
        raise RuntimeError(
            "Unexpected statewide CD stub 8 N1."
        )

    if (
        int(state8["A00100"])
        != EXPECTED_CD_STATE_STUB8_A00100
    ):
        raise RuntimeError(
            "Unexpected statewide CD stub 8 A00100."
        )

    if int(state9["N1"]) != EXPECTED_CD_STATE_STUB9_N1:
        raise RuntimeError(
            "Unexpected statewide CD stub 9 N1."
        )

    if (
        int(state9["A00100"])
        != EXPECTED_CD_STATE_STUB9_A00100
    ):
        raise RuntimeError(
            "Unexpected statewide CD stub 9 A00100."
        )

    print(
        "CD upper-tail stub controls      : PASS"
    )

    detail = wa.loc[
        wa["cd"].isin(EXPECTED_CDS)
        & wa["agi_stub"].isin([8, 9])
    ].copy()

    if len(detail) != 20:
        raise RuntimeError(
            "Expected exactly 20 district/stub rows "
            "for stubs 8 and 9."
        )

    official = (
        detail.groupby(
            "cd",
            as_index=False,
        )[VARIABLES]
        .sum()
    )

    official = official.rename(
        columns={
            variable:
                f"official_{variable}"
            for variable in VARIABLES
        }
    )

    print()
    print("OFFICIAL CD $200K+ ANSWER KEY")
    print("-" * 100)

    print(
        f"District rows                    : "
        f"{len(official):,}"
    )

    print(
        f"Official N1 total                : "
        f"{official['official_N1'].sum():,.0f}"
    )

    print(
        f"Official A00100 total            : "
        f"{official['official_A00100'].sum():,.0f}"
    )

    return official, wa


# =============================================================================
# BUILD COMPARISON
# =============================================================================

def build_comparison(
    predicted: pd.DataFrame,
    official: pd.DataFrame,
) -> pd.DataFrame:
    print()
    print("=" * 100)
    print("BUILD PREDICTED VS OFFICIAL CD COMPARISON")
    print("=" * 100)

    comparison = predicted.merge(
        official,
        on="cd",
        how="inner",
        validate="one_to_one",
    )

    if len(comparison) != 10:
        raise RuntimeError(
            "Expected exactly 10 CD comparison rows."
        )

    comparison = comparison.sort_values(
        "cd"
    ).reset_index(drop=True)

    for variable in VARIABLES:
        predicted_col = (
            f"predicted_{variable}"
        )

        official_col = (
            f"official_{variable}"
        )

        error_col = (
            f"error_{variable}"
        )

        abs_error_col = (
            f"abs_error_{variable}"
        )

        comparison[error_col] = (
            comparison[predicted_col]
            - comparison[official_col]
        )

        comparison[abs_error_col] = (
            comparison[error_col].abs()
        )

        predicted_total = float(
            comparison[predicted_col].sum()
        )

        official_total = float(
            comparison[official_col].sum()
        )

        predicted_share_col = (
            f"predicted_share_{variable}"
        )

        official_share_col = (
            f"official_share_{variable}"
        )

        share_error_col = (
            f"share_error_{variable}"
        )

        comparison[
            predicted_share_col
        ] = (
            comparison[predicted_col]
            / predicted_total
        )

        comparison[
            official_share_col
        ] = (
            comparison[official_col]
            / official_total
        )

        comparison[
            share_error_col
        ] = (
            comparison[predicted_share_col]
            - comparison[official_share_col]
        )

    print(
        f"Comparison rows                  : "
        f"{len(comparison):,}"
    )

    print(
        "Comparison construction          : PASS"
    )

    return comparison


# =============================================================================
# METRICS
# =============================================================================

def pearson_corr(
    x: pd.Series,
    y: pd.Series,
) -> float:
    if x.nunique() <= 1 or y.nunique() <= 1:
        return float("nan")

    return float(
        x.corr(
            y,
            method="pearson",
        )
    )


def spearman_corr(
    x: pd.Series,
    y: pd.Series,
) -> float:
    """
    Calculate Spearman rank correlation without requiring SciPy.

    Spearman correlation is the Pearson correlation of the ranked
    observations. pandas Series.rank() uses average ranks for ties,
    which is the standard treatment for Spearman correlation.
    """

    if x.nunique() <= 1 or y.nunique() <= 1:
        return float("nan")

    x_rank = x.rank(
        method="average"
    )

    y_rank = y.rank(
        method="average"
    )

    return float(
        x_rank.corr(
            y_rank,
            method="pearson",
        )
    )

def calculate_metrics(
    comparison: pd.DataFrame,
) -> pd.DataFrame:
    print()
    print("=" * 100)
    print("VARIABLE-BY-VARIABLE VALIDATION METRICS")
    print("=" * 100)

    records: list[dict] = []

    for variable in VARIABLES:
        p = comparison[
            f"predicted_{variable}"
        ].astype(float)

        o = comparison[
            f"official_{variable}"
        ].astype(float)

        ps = comparison[
            f"predicted_share_{variable}"
        ].astype(float)

        os = comparison[
            f"official_share_{variable}"
        ].astype(float)

        error = p - o
        share_error = ps - os

        mae = float(
            np.mean(
                np.abs(error)
            )
        )

        rmse = float(
            np.sqrt(
                np.mean(
                    np.square(error)
                )
            )
        )

        share_mae = float(
            np.mean(
                np.abs(share_error)
            )
        )

        share_rmse = float(
            np.sqrt(
                np.mean(
                    np.square(share_error)
                )
            )
        )

        max_share_idx = (
            share_error.abs().idxmax()
        )

        max_level_idx = (
            error.abs().idxmax()
        )

        record = {
            "variable": variable,
            "predicted_total":
                float(p.sum()),
            "official_total":
                float(o.sum()),
            "total_difference":
                float(p.sum() - o.sum()),
            "total_ratio":
                (
                    float(p.sum() / o.sum())
                    if o.sum() != 0
                    else float("nan")
                ),
            "level_mae": mae,
            "level_rmse": rmse,
            "pearson_correlation":
                pearson_corr(p, o),
            "spearman_rank_correlation":
                spearman_corr(p, o),
            "share_mae": share_mae,
            "share_rmse": share_rmse,
            "max_abs_share_error":
                float(
                    share_error.abs().max()
                ),
            "max_share_error_cd":
                comparison.loc[
                    max_share_idx,
                    "cd",
                ],
            "max_abs_level_error":
                float(
                    error.abs().max()
                ),
            "max_level_error_cd":
                comparison.loc[
                    max_level_idx,
                    "cd",
                ],
        }

        records.append(record)

    metrics = pd.DataFrame(
        records
    )

    print(
        metrics[
            [
                "variable",
                "predicted_total",
                "official_total",
                "total_ratio",
                "pearson_correlation",
                "spearman_rank_correlation",
                "share_mae",
                "max_abs_share_error",
                "max_share_error_cd",
            ]
        ].to_string(
            index=False,
            formatters={
                "predicted_total":
                    lambda x: f"{x:,.3f}",
                "official_total":
                    lambda x: f"{x:,.3f}",
                "total_ratio":
                    lambda x: f"{x:.6f}",
                "pearson_correlation":
                    lambda x: f"{x:.6f}",
                "spearman_rank_correlation":
                    lambda x: f"{x:.6f}",
                "share_mae":
                    lambda x: f"{x:.6%}",
                "max_abs_share_error":
                    lambda x: f"{x:.6%}",
            },
        )
    )

    return metrics


# =============================================================================
# DISTRICT DIAGNOSTICS
# =============================================================================

def print_district_diagnostics(
    comparison: pd.DataFrame,
) -> None:
    print()
    print("=" * 100)
    print("DISTRICT SHARE DIAGNOSTICS")
    print("=" * 100)

    for variable in VARIABLES:
        print()
        print(variable)
        print("-" * 100)

        display = comparison[
            [
                "cd",
                f"predicted_{variable}",
                f"official_{variable}",
                f"predicted_share_{variable}",
                f"official_share_{variable}",
                f"share_error_{variable}",
            ]
        ].copy()

        display.columns = [
            "CD",
            "predicted",
            "official",
            "predicted_share",
            "official_share",
            "share_error",
        ]

        print(
            display.to_string(
                index=False,
                formatters={
                    "predicted":
                        lambda x: f"{x:,.3f}",
                    "official":
                        lambda x: f"{x:,.3f}",
                    "predicted_share":
                        lambda x: f"{x:.6%}",
                    "official_share":
                        lambda x: f"{x:.6%}",
                    "share_error":
                        lambda x: f"{x:+.6%}",
                },
            )
        )


# =============================================================================
# SEATTLE / EASTSIDE FOCUS
# =============================================================================

def print_focus_districts(
    comparison: pd.DataFrame,
) -> None:
    print()
    print("=" * 100)
    print("FOCUS DISTRICTS: CD07, CD08, CD09")
    print("=" * 100)

    focus = comparison.loc[
        comparison["cd"].isin(
            {"07", "08", "09"}
        )
    ].copy()

    for variable in VARIABLES:
        print()
        print(variable)
        print("-" * 100)

        display = focus[
            [
                "cd",
                f"predicted_share_{variable}",
                f"official_share_{variable}",
                f"share_error_{variable}",
            ]
        ].copy()

        display.columns = [
            "CD",
            "predicted_share",
            "official_share",
            "share_error",
        ]

        print(
            display.to_string(
                index=False,
                formatters={
                    "predicted_share":
                        lambda x: f"{x:.6%}",
                    "official_share":
                        lambda x: f"{x:.6%}",
                    "share_error":
                        lambda x: f"{x:+.6%}",
                },
            )
        )


# =============================================================================
# WRITE OUTPUTS
# =============================================================================

def write_outputs(
    merged: pd.DataFrame,
    unresolved: pd.DataFrame,
    comparison: pd.DataFrame,
    metrics: pd.DataFrame,
) -> None:
    print()
    print("=" * 100)
    print("WRITE VALIDATION ARTIFACTS")
    print("=" * 100)

    OUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    merged.to_csv(
        OUT_ALLOCATION,
        index=False,
    )

    unresolved.to_csv(
        OUT_UNRESOLVED,
        index=False,
    )

    comparison.to_csv(
        OUT_CD_COMPARISON,
        index=False,
    )

    metrics.to_csv(
        OUT_METRICS,
        index=False,
    )

    outputs = [
        OUT_ALLOCATION,
        OUT_UNRESOLVED,
        OUT_CD_COMPARISON,
        OUT_METRICS,
    ]

    for path in outputs:
        print()
        print(
            f"Wrote                            : "
            f"{path.relative_to(ROOT)}"
        )

        print(
            f"SHA-256                          : "
            f"{sha256(path)}"
        )


# =============================================================================
# MAIN
# =============================================================================

def main() -> int:
    print("=" * 100)
    print(
        "MILLIONAIRE TAX LD MODEL - "
        "IRS TY2022 ZIP TO CONGRESSIONAL DISTRICT VALIDATION"
    )
    print("=" * 100)

    print()
    print("STAGE 5B - INDEPENDENT GEOGRAPHIC VALIDATION")
    print()
    print("READ ONLY")
    print("NO DATABASE WRITES")
    print("NO MODEL FITTING")
    print("NO LD MILLIONAIRE ESTIMATES")
    print("NO USE OF HISTORICAL LD MILLIONAIRE DATA")
    print()
    print(
        "PURPOSE: Test whether population-weighted "
        "ZIP/ZCTA geography reproduces independently "
        "published IRS Congressional District geography."
    )

    print()
    print("=" * 100)
    print("SOURCE PROVENANCE")
    print("=" * 100)

    for path in (
        IRS_ZIP_XLSX,
        IRS_CD_CSV,
        CROSSWALK,
    ):
        require_file(path)

        print()
        print(
            f"Source                           : "
            f"{path.relative_to(ROOT)}"
        )

        print(
            f"Bytes                            : "
            f"{path.stat().st_size:,}"
        )

        print(
            f"SHA-256                          : "
            f"{sha256(path)}"
        )

    zip_hash = sha256(
        IRS_ZIP_XLSX
    )

    if zip_hash != EXPECTED_ZIP_SHA256:
        raise RuntimeError(
            "IRS ZIP workbook hash differs from "
            "frozen Stage 4 source."
        )

    crosswalk_hash = sha256(
        CROSSWALK
    )

    if (
        crosswalk_hash
        != EXPECTED_CROSSWALK_SHA256
    ):
        raise RuntimeError(
            "ZCTA/CD crosswalk hash differs from "
            "frozen Stage 3 source."
        )

    print()
    print(
        "Frozen source hash validation    : PASS"
    )

    high, _ = read_zip_data()

    crosswalk = read_crosswalk()

    resolved, unresolved = (
        classify_zip_geography(
            high,
            crosswalk,
        )
    )

    merged, predicted = (
        allocate_zip_to_cd(
            resolved,
            crosswalk,
        )
    )

    official, _ = (
        read_cd_answer_key()
    )

    comparison = build_comparison(
        predicted,
        official,
    )

    metrics = calculate_metrics(
        comparison
    )

    print_district_diagnostics(
        comparison
    )

    print_focus_districts(
        comparison
    )

    write_outputs(
        merged,
        unresolved,
        comparison,
        metrics,
    )

    print()
    print("=" * 100)
    print("STAGE 5B COMPLETE")
    print("=" * 100)

    print()
    print(
        "Interpretation rule:"
    )

    print(
        "1. Level differences are reported but are "
        "not treated as pure geographic error because "
        "the IRS ZIP and CD products have different "
        "published statewide upper-tail totals."
    )

    print(
        "2. District-share agreement is the principal "
        "test of the ZIP/ZCTA population-weighted "
        "geographic allocation."
    )

    print(
        "3. IRS ZIP 99999 remains geographically "
        "unresolved and receives no invented "
        "Congressional District allocation."
    )

    print(
        "4. This validation does not use or evaluate "
        "any historical LD-level millionaire estimates."
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())