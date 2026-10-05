from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]

IRS_XLSX = (
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

OUT_COVERAGE = (
    OUT_DIR
    / "irs_ty2022_zip_zcta_coverage.csv"
)

OUT_UNMATCHED = (
    OUT_DIR
    / "irs_ty2022_zip_unmatched_profile.csv"
)


# Column positions in the IRS workbook.
#
# Confirmed from the workbook's IRS column-number row:
#
#  0  ZIP code
#  1  AGI class
#  2  N1       Number of returns
# 19  A00100   Adjusted gross income
# 27  N00600   Ordinary dividends - returns
# 28  A00600   Ordinary dividends - amount
# 35  N01000   Net capital gain - returns
# 36  A01000   Net capital gain - amount
# 45  N26270   Partnership/S-corp - returns
# 46  A26270   Partnership/S-corp - amount
#
# Additional candidate predictors:
#
# 23/24 taxable interest
# 39/40 business/profession net income
# 47/48 rental/royalty net income
#
COL_ZIP = 0
COL_AGI_LABEL = 1
COL_N1 = 2
COL_A00100 = 18

COL_N00600 = 27
COL_A00600 = 28

COL_N01000 = 35
COL_A01000 = 36

COL_N26270 = 45
COL_A26270 = 46

COL_N00300 = 23
COL_A00300 = 24

COL_N00900 = 39
COL_A00900 = 40

COL_N01700 = 47
COL_A01700 = 48


VARIABLES = {
    "n1": COL_N1,
    "a00100": COL_A00100,
    "n00300": COL_N00300,
    "a00300": COL_A00300,
    "n00600": COL_N00600,
    "a00600": COL_A00600,
    "n01000": COL_N01000,
    "a01000": COL_A01000,
    "n00900": COL_N00900,
    "a00900": COL_A00900,
    "n26270": COL_N26270,
    "a26270": COL_A26270,
    "n01700": COL_N01700,
    "a01700": COL_A01700,
}


EXPECTED_STATE_200K_N1 = 423_160
EXPECTED_STATE_200K_A00100 = 197_286_593

ZERO_POP_ZCTAS = {
    "98154",
    "98158",
    "98174",
    "98430",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(
            lambda: f.read(1024 * 1024),
            b"",
        ):
            h.update(chunk)

    return h.hexdigest()


def clean_zip(value) -> str | None:
    if pd.isna(value):
        return None

    text = str(value).strip()

    if text.endswith(".0"):
        text = text[:-2]

    if not text.isdigit():
        return None

    return text.zfill(5)


def read_irs() -> pd.DataFrame:
    print()
    print("=" * 88)
    print("READ IRS TY2022 WASHINGTON ZIP SOI")
    print("=" * 88)

    raw = pd.read_excel(
        IRS_XLSX,
        sheet_name="Sheet1",
        header=None,
    )

    print(f"Workbook rows        : {len(raw):,}")
    print(f"Workbook columns     : {raw.shape[1]:,}")

    rows = pd.DataFrame()

    rows["zip"] = raw.iloc[:, COL_ZIP].map(
        clean_zip
    )

    rows["agi_label"] = (
        raw.iloc[:, COL_AGI_LABEL]
        .astype("string")
        .str.strip()
    )

    for name, col in VARIABLES.items():
        rows[name] = pd.to_numeric(
            raw.iloc[:, col],
            errors="coerce",
        )

    rows = rows.loc[
        rows["zip"].notna()
        & rows["agi_label"].notna()
    ].copy()

    print(f"Parsed IRS rows      : {len(rows):,}")
    print(
        f"Distinct ZIP values  : "
        f"{rows['zip'].nunique():,}"
    )

    print()
    print("AGI labels:")
    print(
        rows["agi_label"]
        .value_counts(dropna=False)
        .to_string()
    )

    return rows


def identify_state_control(
    rows: pd.DataFrame,
) -> pd.DataFrame:
    print()
    print("=" * 88)
    print("VERIFY STATEWIDE $200K+ CONTROL")
    print("=" * 88)

    state = rows.loc[
        rows["zip"].eq("00000")
        & rows["agi_label"].eq(
            "$200,000 or more"
        )
    ].copy()

    print(f"Candidate rows       : {len(state):,}")

    if len(state) != 1:
        print(
            state[
                [
                    "zip",
                    "agi_label",
                    "n1",
                    "a00100",
                ]
            ].to_string(index=False)
        )

        raise RuntimeError(
            "Could not uniquely identify statewide "
            "$200K+ IRS control."
        )

    row = state.iloc[0]

    print(
        f"N1                   : "
        f"{int(row['n1']):,}"
    )
    print(
        f"A00100 (thousands)   : "
        f"{int(row['a00100']):,}"
    )

    if int(row["n1"]) != EXPECTED_STATE_200K_N1:
        raise RuntimeError(
            "Unexpected statewide $200K+ N1."
        )

    if (
        int(row["a00100"])
        != EXPECTED_STATE_200K_A00100
    ):
        raise RuntimeError(
            "Unexpected statewide $200K+ AGI."
        )

    print("State control        : PASS")

    return state


def get_200k_rows(
    rows: pd.DataFrame,
) -> pd.DataFrame:
    high = rows.loc[
        rows["agi_label"].eq(
            "$200,000 or more"
        )
    ].copy()

    # Remove the statewide ZIP=00000 control.
    high = high.loc[
        ~high["zip"].eq("00000")
    ].copy()

    print()
    print("=" * 88)
    print("IRS ZIP $200K+ UNIVERSE")
    print("=" * 88)

    print(f"Rows                 : {len(high):,}")
    print(
        f"Distinct ZIPs        : "
        f"{high['zip'].nunique():,}"
    )

    duplicate_zips = int(
        high["zip"].duplicated().sum()
    )

    print(
        f"Duplicate ZIPs       : "
        f"{duplicate_zips:,}"
    )

    if duplicate_zips:
        raise RuntimeError(
            "Duplicate ZIPs in $200K+ universe."
        )

    return high


def read_crosswalk() -> tuple[
    pd.DataFrame,
    set[str],
]:
    print()
    print("=" * 88)
    print("READ FROZEN ZCTA TO CD116 CROSSWALK")
    print("=" * 88)

    crosswalk = pd.read_csv(
        CROSSWALK,
        dtype={
            "zcta5ce20": str,
            "cd116": str,
        },
    )

    crosswalk["zcta5ce20"] = (
        crosswalk["zcta5ce20"]
        .str.zfill(5)
    )

    zctas = set(
        crosswalk["zcta5ce20"]
        .dropna()
        .unique()
    )

    print(f"Crosswalk rows       : {len(crosswalk):,}")
    print(f"Distinct ZCTAs       : {len(zctas):,}")

    return crosswalk, zctas


def classify_zip(
    zip_code: str,
    zctas: set[str],
) -> str:
    if zip_code in ZERO_POP_ZCTAS:
        return "ZERO_POP_ZCTA"

    if zip_code in zctas:
        return "POSITIVE_POP_ZCTA"

    return "NO_ZCTA_MATCH"


def profile_coverage(
    high: pd.DataFrame,
    zctas: set[str],
) -> pd.DataFrame:
    print()
    print("=" * 88)
    print("IRS ZIP TO ZCTA COVERAGE")
    print("=" * 88)

    high = high.copy()

    high["coverage_class"] = (
        high["zip"]
        .map(
            lambda z: classify_zip(
                z,
                zctas,
            )
        )
    )

    summary = (
        high.groupby(
            "coverage_class",
            as_index=False,
        )
        .agg(
            zip_count=("zip", "nunique"),
            n1=("n1", "sum"),
            a00100=("a00100", "sum"),
            a00300=("a00300", "sum"),
            a00600=("a00600", "sum"),
            a01000=("a01000", "sum"),
            a00900=("a00900", "sum"),
            a26270=("a26270", "sum"),
            a01700=("a01700", "sum"),
        )
    )

    zip_n1 = float(
        high["n1"].sum()
    )

    zip_agi = float(
        high["a00100"].sum()
    )

    summary["n1_share"] = (
        summary["n1"] / zip_n1
    )

    summary["agi_share"] = (
        summary["a00100"] / zip_agi
    )

    print(summary.to_string(
        index=False,
        formatters={
            "n1_share":
                lambda x: f"{x:.8%}",
            "agi_share":
                lambda x: f"{x:.8%}",
        },
    ))

    print()
    print("ZIP-detail totals:")
    print(
        f"N1                   : "
        f"{int(zip_n1):,}"
    )
    print(
        f"A00100 (thousands)   : "
        f"{int(zip_agi):,}"
    )

    return high


def compare_zip_to_state(
    high: pd.DataFrame,
) -> None:
    print()
    print("=" * 88)
    print("ZIP DETAIL VS STATE CONTROL")
    print("=" * 88)

    zip_n1 = int(
        high["n1"].sum()
    )

    zip_agi = int(
        high["a00100"].sum()
    )

    print(
        f"State N1             : "
        f"{EXPECTED_STATE_200K_N1:,}"
    )
    print(
        f"ZIP-detail N1        : "
        f"{zip_n1:,}"
    )
    print(
        f"Difference           : "
        f"{zip_n1 - EXPECTED_STATE_200K_N1:+,}"
    )
    print(
        f"Coverage             : "
        f"{zip_n1 / EXPECTED_STATE_200K_N1:.8%}"
    )

    print()

    print(
        f"State AGI            : "
        f"{EXPECTED_STATE_200K_A00100:,}"
    )
    print(
        f"ZIP-detail AGI       : "
        f"{zip_agi:,}"
    )
    print(
        f"Difference           : "
        f"{zip_agi - EXPECTED_STATE_200K_A00100:+,}"
    )
    print(
        f"Coverage             : "
        f"{zip_agi / EXPECTED_STATE_200K_A00100:.8%}"
    )


def write_outputs(
    high: pd.DataFrame,
) -> None:
    print()
    print("=" * 88)
    print("WRITE DIAGNOSTIC OUTPUTS")
    print("=" * 88)

    OUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    high = high.sort_values(
        [
            "coverage_class",
            "zip",
        ]
    ).reset_index(drop=True)

    high.to_csv(
        OUT_COVERAGE,
        index=False,
    )

    unmatched = high.loc[
        high["coverage_class"].ne(
            "POSITIVE_POP_ZCTA"
        )
    ].copy()

    unmatched.to_csv(
        OUT_UNMATCHED,
        index=False,
    )

    print(
        f"Wrote                : "
        f"{OUT_COVERAGE.relative_to(ROOT)}"
    )
    print(
        f"SHA-256              : "
        f"{sha256(OUT_COVERAGE)}"
    )

    print()
    print(
        f"Wrote                : "
        f"{OUT_UNMATCHED.relative_to(ROOT)}"
    )
    print(
        f"SHA-256              : "
        f"{sha256(OUT_UNMATCHED)}"
    )

    if len(unmatched):
        print()
        print("Non-positive-population matches:")
        print(
            unmatched[
                [
                    "zip",
                    "coverage_class",
                    "n1",
                    "a00100",
                    "a00600",
                    "a01000",
                    "a26270",
                ]
            ]
            .sort_values(
                "a00100",
                ascending=False,
            )
            .to_string(index=False)
        )


def main() -> int:
    print("=" * 88)
    print(
        "MILLIONAIRE TAX LD MODEL - "
        "IRS TY2022 ZIP/ZCTA COVERAGE PROFILE"
    )
    print("=" * 88)

    print()
    print("COVERAGE DIAGNOSTIC ONLY")
    print("NO CD ALLOCATION")
    print("NO MODEL FITTING")
    print("NO LD MILLIONAIRE ESTIMATES")
    print("NO DATABASE WRITES")

    for path in (
        IRS_XLSX,
        CROSSWALK,
    ):
        if not path.exists():
            raise FileNotFoundError(path)

    print()
    print("SOURCES")
    print("-" * 88)

    print(
        f"IRS workbook         : "
        f"{IRS_XLSX.relative_to(ROOT)}"
    )
    print(
        f"Bytes                : "
        f"{IRS_XLSX.stat().st_size:,}"
    )
    print(
        f"SHA-256              : "
        f"{sha256(IRS_XLSX)}"
    )

    print()
    print(
        f"ZCTA/CD crosswalk    : "
        f"{CROSSWALK.relative_to(ROOT)}"
    )
    print(
        f"SHA-256              : "
        f"{sha256(CROSSWALK)}"
    )

    rows = read_irs()

    identify_state_control(rows)

    high = get_200k_rows(rows)

    _, zctas = read_crosswalk()

    high = profile_coverage(
        high,
        zctas,
    )

    compare_zip_to_state(high)

    write_outputs(high)

    print()
    print("=" * 88)
    print("IRS ZIP/ZCTA COVERAGE PROFILE COMPLETE")
    print("=" * 88)

    return 0


if __name__ == "__main__":
    sys.exit(main())