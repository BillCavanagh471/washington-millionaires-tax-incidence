"""
Millionaire Tax Incidence v0.2
Stage 9A - Congressional-district geographic reliability screen.

Purpose
-------
Evaluate how reliably IRS TY2022 ZIP-derived upper-tail dollar variables
transport geographically to independently published IRS Congressional
District SOI values.

This is NOT an excess-AGI model.

No millionaire AGI is estimated.
No legislative-district model is fit.
No statewide millionaire controls are allocated.
No historical LD millionaire estimates are used.
No database writes occur.

Primary metric:
    Mean absolute error in congressional-district share.

Predeclared reliability classification:
    HIGH      <= 0.75 percentage points share MAE
    MODERATE  > 0.75 and <= 1.50 percentage points
    LOW       > 1.50 percentage points
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[3]

INPUT_PATH = (
    ROOT
    / "data"
    / "processed"
    / "validation"
    / "irs_cd_ty2022"
    / "irs_ty2022_zip_to_cd_comparison.csv"
)

OUTPUT_DIR = (
    ROOT
    / "data"
    / "processed"
    / "validation"
    / "millionaire_excess_agi_v0_2"
)

OUTPUT_PATH = (
    OUTPUT_DIR
    / "stage9a_cd_geographic_reliability_screen.csv"
)


VARIABLES = [
    "A00100",   # AGI
    "A00300",   # taxable interest
    "A00600",   # ordinary dividends
    "A00900",   # business/profession net income
    "A01000",   # net capital gain
    "A01700",   # taxable pensions/annuities
    "A26270",   # partnership/S-corp net income
]


DESCRIPTIONS = {
    "A00100": "Adjusted gross income",
    "A00300": "Taxable interest",
    "A00600": "Ordinary dividends",
    "A00900": "Business/profession net income",
    "A01000": "Net capital gain",
    "A01700": "Taxable pensions and annuities",
    "A26270": "Partnership/S-corporation net income",
}


def banner(title: str) -> None:
    print()
    print("=" * 100)
    print(title)
    print("=" * 100)
    print()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)

    return h.hexdigest()


def pearson(x: np.ndarray, y: np.ndarray) -> float:
    return float(
        np.corrcoef(x, y)[0, 1]
    )


def spearman(x: np.ndarray, y: np.ndarray) -> float:
    xr = pd.Series(x).rank(method="average").to_numpy()
    yr = pd.Series(y).rank(method="average").to_numpy()

    return pearson(xr, yr)


def reliability_class(
    share_mae_percentage_points: float,
) -> str:

    if share_mae_percentage_points <= 0.75:
        return "HIGH"

    if share_mae_percentage_points <= 1.50:
        return "MODERATE"

    return "LOW"


def main() -> None:

    banner(
        "MILLIONAIRE TAX INCIDENCE v0.2 - "
        "STAGE 9A CD GEOGRAPHIC RELIABILITY SCREEN"
    )

    print("READ ONLY")
    print("NO EXCESS-AGI MODEL FITTING")
    print("NO LD MILLIONAIRE AGI ESTIMATION")
    print("NO STATEWIDE MILLIONAIRE CONTROL ALLOCATION")
    print("NO HISTORICAL LD MILLIONAIRE INPUTS")
    print("NO DATABASE WRITES")
    print()

    require(
        INPUT_PATH.exists(),
        f"Missing Stage 5 comparison artifact: {INPUT_PATH}",
    )

    input_hash = sha256_file(INPUT_PATH)

    print(
        f"Input artifact                  : "
        f"{INPUT_PATH.relative_to(ROOT)}"
    )

    print(
        f"Input SHA-256                   : {input_hash}"
    )

    df = pd.read_csv(INPUT_PATH)

    require(
        len(df) == 10,
        f"Expected 10 Washington CDs; found {len(df)}.",
    )

    require(
        df["cd"].nunique() == 10,
        "Congressional district identifiers are not unique.",
    )

    require(
        set(df["cd"].astype(int)) == set(range(1, 11)),
        "Congressional district universe is not exactly 1-10.",
    )

    print()
    print(f"Congressional districts         : {len(df)}")
    print("CD universe                     : 1-10 PASS")

    rows = []

    banner("VARIABLE RELIABILITY RESULTS")

    for variable in VARIABLES:

        required_columns = [
            f"predicted_{variable}",
            f"official_{variable}",
            f"predicted_share_{variable}",
            f"official_share_{variable}",
        ]

        for column in required_columns:
            require(
                column in df.columns,
                f"Missing required column: {column}",
            )

        predicted = (
            pd.to_numeric(
                df[f"predicted_{variable}"],
                errors="raise",
            )
            .to_numpy(dtype=float)
        )

        official = (
            pd.to_numeric(
                df[f"official_{variable}"],
                errors="raise",
            )
            .to_numpy(dtype=float)
        )

        predicted_share = (
            pd.to_numeric(
                df[f"predicted_share_{variable}"],
                errors="raise",
            )
            .to_numpy(dtype=float)
        )

        official_share = (
            pd.to_numeric(
                df[f"official_share_{variable}"],
                errors="raise",
            )
            .to_numpy(dtype=float)
        )

        require(
            np.isfinite(predicted).all(),
            f"{variable}: nonfinite predicted values.",
        )

        require(
            np.isfinite(official).all(),
            f"{variable}: nonfinite official values.",
        )

        require(
            np.isfinite(predicted_share).all(),
            f"{variable}: nonfinite predicted shares.",
        )

        require(
            np.isfinite(official_share).all(),
            f"{variable}: nonfinite official shares.",
        )

        predicted_total = float(
            predicted.sum()
        )

        official_total = float(
            official.sum()
        )

        require(
            official_total != 0.0,
            f"{variable}: official total is zero.",
        )

        predicted_share_sum = float(
            predicted_share.sum()
        )

        official_share_sum = float(
            official_share.sum()
        )

        require(
            abs(predicted_share_sum - 1.0) <= 1e-6,
            (
                f"{variable}: predicted shares do not "
                f"sum to 1: {predicted_share_sum}"
            ),
        )

        require(
            abs(official_share_sum - 1.0) <= 1e-6,
            (
                f"{variable}: official shares do not "
                f"sum to 1: {official_share_sum}"
            ),
        )

        share_error = (
            predicted_share
            - official_share
        )

        share_mae_pp = float(
            np.mean(
                np.abs(share_error)
            )
            * 100.0
        )

        max_abs_share_error_pp = float(
            np.max(
                np.abs(share_error)
            )
            * 100.0
        )

        worst_index = int(
            np.argmax(
                np.abs(share_error)
            )
        )

        worst_cd = int(
            df.iloc[worst_index]["cd"]
        )

        pearson_r = pearson(
            predicted_share,
            official_share,
        )

        spearman_r = spearman(
            predicted_share,
            official_share,
        )

        total_ratio = (
            predicted_total
            / official_total
        )

        classification = reliability_class(
            share_mae_pp
        )

        rows.append(
            {
                "variable": variable,
                "description": DESCRIPTIONS[variable],
                "predicted_total": predicted_total,
                "official_total": official_total,
                "predicted_to_official_ratio": total_ratio,
                "share_mae_percentage_points": share_mae_pp,
                "max_abs_share_error_percentage_points":
                    max_abs_share_error_pp,
                "worst_cd": worst_cd,
                "pearson_share": pearson_r,
                "spearman_share": spearman_r,
                "reliability_class": classification,
            }
        )

        print(
            f"{variable:<8} "
            f"{DESCRIPTIONS[variable]:<38} "
            f"MAE={share_mae_pp:6.3f} pp  "
            f"MAX={max_abs_share_error_pp:6.3f} pp  "
            f"Pearson={pearson_r:8.6f}  "
            f"Spearman={spearman_r:8.6f}  "
            f"Ratio={total_ratio:8.6f}  "
            f"{classification}"
        )

    results = pd.DataFrame(rows)

    class_order = {
        "HIGH": 0,
        "MODERATE": 1,
        "LOW": 2,
    }

    results["_class_order"] = (
        results["reliability_class"]
        .map(class_order)
    )

    results = (
        results
        .sort_values(
            [
                "_class_order",
                "share_mae_percentage_points",
                "variable",
            ]
        )
        .drop(columns="_class_order")
        .reset_index(drop=True)
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    results.to_csv(
        OUTPUT_PATH,
        index=False,
    )

    banner("RANKED RELIABILITY SCREEN")

    print(
        results[
            [
                "variable",
                "description",
                "share_mae_percentage_points",
                "max_abs_share_error_percentage_points",
                "pearson_share",
                "spearman_share",
                "predicted_to_official_ratio",
                "reliability_class",
            ]
        ].to_string(
            index=False,
            formatters={
                "share_mae_percentage_points":
                    lambda x: f"{x:.6f}",
                "max_abs_share_error_percentage_points":
                    lambda x: f"{x:.6f}",
                "pearson_share":
                    lambda x: f"{x:.6f}",
                "spearman_share":
                    lambda x: f"{x:.6f}",
                "predicted_to_official_ratio":
                    lambda x: f"{x:.6f}",
            },
        )
    )

    banner("PREDECLARED CLASSIFICATION COUNTS")

    for classification in [
        "HIGH",
        "MODERATE",
        "LOW",
    ]:
        subset = results[
            results["reliability_class"]
            == classification
        ]

        variables = ", ".join(
            subset["variable"].tolist()
        )

        print(
            f"{classification:<10}: "
            f"{len(subset):>2}  "
            f"{variables if variables else '(none)'}"
        )

    banner("OUTPUT")

    print(
        f"Reliability screen              : "
        f"{OUTPUT_PATH.relative_to(ROOT)}"
    )

    print(
        f"Output SHA-256                  : "
        f"{sha256_file(OUTPUT_PATH)}"
    )

    banner("STAGE 9A COMPLETE")

    print(
        "Interpretation boundary:"
    )

    print(
        "This screen evaluates geographic transportability "
        "of IRS ZIP-derived upper-tail dollar variables to "
        "official IRS Congressional District geography."
    )

    print()

    print(
        "It does NOT establish observed millionaire AGI by "
        "legislative district and does NOT allocate the "
        "$44.426796 billion statewide millionaire excess-AGI control."
    )


if __name__ == "__main__":
    main()