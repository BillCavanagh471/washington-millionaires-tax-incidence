from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd


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

CROSSWALK = (
    ROOT
    / "data"
    / "processed"
    / "validation"
    / "irs_ld_ty2022"
    / "wa_zcta_ld_population_weights.csv"
)

OUT_DIR = (
    ROOT
    / "data"
    / "processed"
    / "validation"
    / "irs_ld_ty2022"
)

OUT_ALLOCATION = (
    OUT_DIR
    / "irs_ty2022_zip_to_ld_allocated_detail.csv"
)

OUT_UNRESOLVED = (
    OUT_DIR
    / "irs_ty2022_zip_unresolved_geography.csv"
)

OUT_LD = (
    OUT_DIR
    / "irs_ty2022_ld_upper_tail_predictors.csv"
)


# =============================================================================
# FROZEN SOURCE CONTROLS
# =============================================================================

EXPECTED_ZIP_SHA256 = (
    "cadcf9dd5b197a084dccb62268c1fc18"
    "be039a17722b15eb05e674fdc855dfa5"
)

EXPECTED_CROSSWALK_SHA256 = (
    "7c01ec9b23c535194895e4c94e41a8b0"
    "fe140c88bb4f79a698ad8fbc3c69e007"
)

EXPECTED_ZIP_STATE_N1 = 423_160
EXPECTED_ZIP_STATE_A00100 = 197_286_593

EXPECTED_ZIP_DETAIL_N1 = 423_440
EXPECTED_ZIP_DETAIL_A00100 = 197_286_593

EXPECTED_RESOLVED_ZIP_COUNT = 498
EXPECTED_UNRESOLVED_ZIP = "99999"

EXPECTED_ZERO_POP_ZCTAS = {
    "98154",
    "98158",
    "98174",
    "98430",
}

EXPECTED_LDS = {
    f"{i:03d}" for i in range(1, 50)
}

EXPECTED_RESOLVED_TOTALS = {
    "N1": 419_030,
    "A00100": 194_171_010,
    "A00300": 1_773_853,
    "A00600": 7_385_367,
    "A00900": 4_175_683,
    "A01000": 24_464_750,
    "A01700": 4_430_480,
    "A26270": 21_287_874,
}


# =============================================================================
# IRS ZIP WORKBOOK COLUMN POSITIONS
#
# Frozen from Stage 5C schema audit.
# Zero-based pandas positions.
# IRS A-fields are thousands of dollars.
# =============================================================================

COL_ZIP = 0
COL_AGI_LABEL = 1

COL_N1 = 2
COL_A00100 = 18

COL_A00300 = 24
COL_A00600 = 28
COL_A00900 = 34
COL_A01000 = 36
COL_A01700 = 40
COL_A26270 = 47


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


# =============================================================================
# READ IRS ZIP DATA
# =============================================================================

def read_zip_data() -> tuple[pd.DataFrame, pd.Series]:
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

    state = rows.loc[
        rows["zip"].eq("00000")
        & rows["agi_label"].eq(
            "$200,000 or more"
        )
    ].copy()

    if len(state) != 1:
        raise RuntimeError(
            "Could not uniquely identify statewide "
            "$200K+ ZIP-product control."
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

    high = rows.loc[
        rows["agi_label"].eq(
            "$200,000 or more"
        )
        & ~rows["zip"].eq("00000")
    ].copy()

    if high["zip"].duplicated().any():
        raise RuntimeError(
            "Duplicate ZIPs in IRS $200K+ detail universe."
        )

    detail_n1 = int(high["N1"].sum())
    detail_agi = int(high["A00100"].sum())

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
        f"{detail_n1:,}"
    )

    print(
        f"ZIP-detail A00100                : "
        f"{detail_agi:,}"
    )

    if detail_n1 != EXPECTED_ZIP_DETAIL_N1:
        raise RuntimeError(
            "Unexpected ZIP-detail N1 total."
        )

    if detail_agi != EXPECTED_ZIP_DETAIL_A00100:
        raise RuntimeError(
            "Unexpected ZIP-detail A00100 total."
        )

    print()
    print("IRS ZIP source controls          : PASS")

    return high, state_row


# =============================================================================
# READ STAGE 6A ZCTA x LD CROSSWALK
# =============================================================================

def read_crosswalk() -> pd.DataFrame:
    print()
    print("=" * 100)
    print("READ FROZEN ZCTA x LEGISLATIVE DISTRICT CROSSWALK")
    print("=" * 100)

    crosswalk = pd.read_csv(
        CROSSWALK,
        dtype={
            "zcta5ce20": str,
            "sldl": str,
        },
    )

    required = {
        "zcta5ce20",
        "sldl",
        "population_weight",
    }

    missing = required - set(crosswalk.columns)

    if missing:
        raise RuntimeError(
            "Required crosswalk columns missing: "
            f"{sorted(missing)}"
        )

    crosswalk = crosswalk[
        [
            "zcta5ce20",
            "sldl",
            "population_weight",
        ]
    ].copy()

    crosswalk.columns = [
        "zcta",
        "ld",
        "weight",
    ]

    crosswalk["zcta"] = (
        crosswalk["zcta"]
        .astype(str)
        .str.strip()
        .str.zfill(5)
    )

    crosswalk["ld"] = (
        crosswalk["ld"]
        .astype(str)
        .str.strip()
        .str.zfill(3)
    )

    crosswalk["weight"] = pd.to_numeric(
        crosswalk["weight"],
        errors="coerce",
    )

    unresolved_zero_pop = crosswalk.loc[
        crosswalk["weight"].isna()
    ].copy()

    observed_zero_pop = set(
        unresolved_zero_pop["zcta"].unique()
    )

    print(
        f"Crosswalk rows                   : "
        f"{len(crosswalk):,}"
    )

    print(
        f"Undefined-weight rows            : "
        f"{len(unresolved_zero_pop):,}"
    )

    print(
        f"Undefined-weight ZCTAs           : "
        f"{len(observed_zero_pop):,}"
    )

    if observed_zero_pop != EXPECTED_ZERO_POP_ZCTAS:
        raise RuntimeError(
            "Unexpected zero-population ZCTA universe: "
            f"{sorted(observed_zero_pop)}"
        )

    # Stage 6A preserves zero-population ZCTAs explicitly.
    # Their population-based allocation weights are undefined.
    # They receive no invented geographic weights.
    crosswalk = crosswalk.loc[
        crosswalk["weight"].notna()
    ].copy()

    observed_lds = set(
        crosswalk["ld"].unique()
    )

    if observed_lds != EXPECTED_LDS:
        raise RuntimeError(
            "Unexpected legislative-district universe."
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
        f"Allocatable crosswalk rows       : "
        f"{len(crosswalk):,}"
    )

    print(
        f"Positive-population ZCTAs        : "
        f"{crosswalk['zcta'].nunique():,}"
    )

    print(
        f"Legislative districts            : "
        f"{len(observed_lds):,}"
    )

    print(
        f"Maximum ZCTA weight-sum error    : "
        f"{max_error:.15f}"
    )

    if crosswalk["zcta"].nunique() != 602:
        raise RuntimeError(
            "Unexpected positive-population ZCTA count."
        )

    if max_error > 1e-12:
        raise RuntimeError(
            "Crosswalk ZCTA weights do not sum to 1."
        )

    print()
    print("Stage 6A crosswalk validation    : PASS")

    return crosswalk


# =============================================================================
# CLASSIFY IRS ZIP GEOGRAPHY
# =============================================================================

def classify_zip_geography(
    high: pd.DataFrame,
    crosswalk: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
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
            "Unexpected resolved ZIP count."
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

    print(
        unresolved[
            ["zip", *VARIABLES]
        ].to_string(index=False)
    )

    print()
    print(
        "Rule: IRS ZIP 99999 remains geographically "
        "unresolved and receives NO invented LD allocation."
    )

    return resolved, unresolved


# =============================================================================
# ALLOCATE IRS ZIP DATA TO LEGISLATIVE DISTRICTS
# =============================================================================

def allocate_zip_to_ld(
    resolved: pd.DataFrame,
    crosswalk: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    print()
    print("=" * 100)
    print("ALLOCATE RESOLVED IRS ZIP DATA TO 49 LEGISLATIVE DISTRICTS")
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

    if merged["_merge"].ne("both").any():
        raise RuntimeError(
            "Resolved ZIP failed LD crosswalk join."
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

    ld = (
        merged.groupby(
            "ld",
            as_index=False,
        )[allocated_cols]
        .sum()
    )

    ld = ld.rename(
        columns={
            f"allocated_{v}": v
            for v in VARIABLES
        }
    )

    observed_lds = set(
        ld["ld"].unique()
    )

    if observed_lds != EXPECTED_LDS:
        raise RuntimeError(
            "Allocated LD universe is incomplete."
        )

    if len(ld) != 49:
        raise RuntimeError(
            "Expected exactly 49 LD rows."
        )

    print()
    print("RESOLVED MASS CONSERVATION")
    print("-" * 100)

    for variable in VARIABLES:
        source_total = float(
            resolved[variable].sum()
        )

        allocated_total = float(
            ld[variable].sum()
        )

        difference = (
            allocated_total
            - source_total
        )

        expected = float(
            EXPECTED_RESOLVED_TOTALS[variable]
        )

        print(
            f"{variable:<10} "
            f"source={source_total:>16,.3f} "
            f"allocated={allocated_total:>16,.3f} "
            f"expected={expected:>16,.3f} "
            f"diff={difference:>12,.6f}"
        )

        if abs(source_total - expected) > 1e-6:
            raise RuntimeError(
                f"Resolved source control failed for "
                f"{variable}."
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
    print("Resolved mass conservation       : PASS")

    return merged, ld


# =============================================================================
# ADD ANALYTICAL SHARES
# =============================================================================

def add_ld_shares(
    ld: pd.DataFrame,
) -> pd.DataFrame:
    print()
    print("=" * 100)
    print("BUILD 49-LD UPPER-TAIL PREDICTOR DATASET")
    print("=" * 100)

    result = ld.copy()

    for variable in VARIABLES:
        total = float(
            result[variable].sum()
        )

        result[
            f"share_{variable}"
        ] = (
            result[variable]
            / total
        )

    result = result.sort_values(
        "ld"
    ).reset_index(drop=True)

    n1_share_sum = float(
        result["share_N1"].sum()
    )

    agi_share_sum = float(
        result["share_A00100"].sum()
    )

    print(
        f"LD rows                          : "
        f"{len(result):,}"
    )

    print(
        f"N1 share sum                     : "
        f"{n1_share_sum:.15f}"
    )

    print(
        f"A00100 share sum                 : "
        f"{agi_share_sum:.15f}"
    )

    if abs(n1_share_sum - 1.0) > 1e-12:
        raise RuntimeError(
            "LD N1 shares do not sum to 1."
        )

    if abs(agi_share_sum - 1.0) > 1e-12:
        raise RuntimeError(
            "LD A00100 shares do not sum to 1."
        )

    print()
    print("49-LD predictor construction     : PASS")

    return result


# =============================================================================
# DIAGNOSTIC DISPLAY
# =============================================================================

def print_ld_diagnostics(
    ld: pd.DataFrame,
) -> None:
    print()
    print("=" * 100)
    print("49-LD IRS UPPER-TAIL GEOGRAPHY")
    print("=" * 100)

    display = ld[
        [
            "ld",
            "N1",
            "share_N1",
            "A00100",
            "share_A00100",
            "A00600",
            "A01000",
            "A26270",
        ]
    ].copy()

    print(
        display.to_string(
            index=False,
            formatters={
                "N1":
                    lambda x: f"{x:,.3f}",
                "share_N1":
                    lambda x: f"{x:.6%}",
                "A00100":
                    lambda x: f"{x:,.3f}",
                "share_A00100":
                    lambda x: f"{x:.6%}",
                "A00600":
                    lambda x: f"{x:,.3f}",
                "A01000":
                    lambda x: f"{x:,.3f}",
                "A26270":
                    lambda x: f"{x:,.3f}",
            },
        )
    )

    print()
    print("TOP 10 LDs BY $200K+ RETURN SHARE")
    print("-" * 100)

    top_n1 = (
        ld.sort_values(
            "share_N1",
            ascending=False,
        )
        .head(10)
        [
            [
                "ld",
                "N1",
                "share_N1",
            ]
        ]
    )

    print(
        top_n1.to_string(
            index=False,
            formatters={
                "N1":
                    lambda x: f"{x:,.3f}",
                "share_N1":
                    lambda x: f"{x:.6%}",
            },
        )
    )


# =============================================================================
# WRITE OUTPUTS
# =============================================================================

def write_outputs(
    merged: pd.DataFrame,
    unresolved: pd.DataFrame,
    ld: pd.DataFrame,
) -> None:
    print()
    print("=" * 100)
    print("WRITE STAGE 6B ARTIFACTS")
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

    ld.to_csv(
        OUT_LD,
        index=False,
    )

    for path in (
        OUT_ALLOCATION,
        OUT_UNRESOLVED,
        OUT_LD,
    ):
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
        "IRS TY2022 ZIP TO LEGISLATIVE DISTRICT ALLOCATION"
    )
    print("=" * 100)

    print()
    print("STAGE 6B - UPPER-TAIL LD PREDICTOR CONSTRUCTION")
    print()
    print("READ ONLY")
    print("NO DATABASE WRITES")
    print("NO MODEL FITTING")
    print("NO MILLIONAIRE ESTIMATION")
    print("NO HISTORICAL LD MILLIONAIRE INPUTS")
    print()

    print(
        "PURPOSE: Allocate audited IRS TY2022 ZIP "
        "$200K+ upper-tail variables to Washington's "
        "49 legislative districts using the independently "
        "constructed Stage 6A population crosswalk."
    )

    print()
    print("=" * 100)
    print("SOURCE PROVENANCE")
    print("=" * 100)

    for path in (
        IRS_ZIP_XLSX,
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

    if sha256(IRS_ZIP_XLSX) != EXPECTED_ZIP_SHA256:
        raise RuntimeError(
            "IRS ZIP workbook hash differs from "
            "frozen audited source."
        )

    if sha256(CROSSWALK) != EXPECTED_CROSSWALK_SHA256:
        raise RuntimeError(
            "Stage 6A LD crosswalk hash differs "
            "from frozen source."
        )

    print()
    print("Frozen source hash validation    : PASS")

    high, _ = read_zip_data()

    crosswalk = read_crosswalk()

    resolved, unresolved = (
        classify_zip_geography(
            high,
            crosswalk,
        )
    )

    merged, ld = (
        allocate_zip_to_ld(
            resolved,
            crosswalk,
        )
    )

    ld = add_ld_shares(ld)

    print_ld_diagnostics(ld)

    write_outputs(
        merged,
        unresolved,
        ld,
    )

    print()
    print("=" * 100)
    print("STAGE 6B COMPLETE")
    print("=" * 100)

    print()
    print("INTERPRETATION RULES")
    print("-" * 100)

    print(
        "1. These are IRS $200K+ upper-tail predictors, "
        "NOT estimated millionaire counts."
    )

    print(
        "2. IRS ZIP 99999 remains geographically "
        "unresolved and receives no invented LD allocation."
    )

    print(
        "3. All resolved IRS mass is conserved exactly "
        "through the ZCTA-to-LD allocation."
    )

    print(
        "4. Historical LD millionaire estimates are "
        "not inputs to this dataset."
    )

    print(
        "5. This dataset is an input to subsequent "
        "de novo millionaire-count modeling only."
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())