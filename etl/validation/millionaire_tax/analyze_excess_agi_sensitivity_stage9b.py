"""
Millionaire Tax Incidence v0.2
Stage 9B - Excess-AGI Allocation Sensitivity Analysis

Purpose
-------
Construct seven PREDECLARED alternative geographic allocations of the
statewide TY2022 millionaire excess-AGI control.

This is a sensitivity analysis, NOT a model-selection tournament.

No candidate is declared a winner.
No historical LD millionaire estimates are used.
No observed LD millionaire AGI is assumed to exist.
No database writes occur.

Statewide controls
------------------
Millionaire returns:
    21,530

Aggregate millionaire AGI:
    $65,956,796,000

First-$1M floor:
    $21,530,000,000

Excess AGI:
    $44,426,796,000

For every candidate and every LD:

    AGI_i = $1,000,000 * N_i + ExcessAGI_i

with:

    ExcessAGI_i >= 0

and statewide reconciliation:

    sum(N_i)         = 21,530
    sum(ExcessAGI_i) = $44,426,796,000
    sum(AGI_i)       = $65,956,796,000
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd


# =============================================================================
# PATHS
# =============================================================================

ROOT = Path(__file__).resolve().parents[3]

COUNT_PATH = (
    ROOT
    / "data"
    / "processed"
    / "validation"
    / "millionaire_count_v0_2"
    / "millionaire_geography_v0_2_ty2022.csv"
)

LD_PREDICTOR_PATH = (
    ROOT
    / "data"
    / "processed"
    / "validation"
    / "irs_ld_ty2022"
    / "irs_ty2022_ld_upper_tail_predictors.csv"
)

STAGE9A_PATH = (
    ROOT
    / "data"
    / "processed"
    / "validation"
    / "millionaire_excess_agi_v0_2"
    / "stage9a_cd_geographic_reliability_screen.csv"
)

OUTPUT_DIR = (
    ROOT
    / "data"
    / "processed"
    / "validation"
    / "millionaire_excess_agi_v0_2"
)

DETAIL_OUTPUT = (
    OUTPUT_DIR
    / "stage9b_excess_agi_sensitivity_by_ld.csv"
)

SUMMARY_OUTPUT = (
    OUTPUT_DIR
    / "stage9b_excess_agi_sensitivity_summary.csv"
)

PAIRWISE_OUTPUT = (
    OUTPUT_DIR
    / "stage9b_candidate_pairwise_comparison.csv"
)


# =============================================================================
# FROZEN INPUT HASHES
# =============================================================================

EXPECTED_COUNT_SHA256 = (
    "6eb3fc8a02eef8dc73b9a752f6532664ec92cab98d3851c9a574ad004390047a"
)

EXPECTED_LD_PREDICTOR_SHA256 = (
    "f2b42b70202bf9dcee431b2914a286eccfc515772f516018683662887669653a"
)

EXPECTED_STAGE9A_SHA256 = (
    "95bd31ca576f3aeedbe195714c8b67e237e25de6a1246015a97c7c1bcdc72105"
)


# =============================================================================
# STATEWIDE CONTROLS
# =============================================================================

STATEWIDE_MILLIONAIRE_RETURNS = 21_530.0
STATEWIDE_MILLIONAIRE_AGI = 65_956_796_000.0
MILLIONAIRE_FLOOR_PER_RETURN = 1_000_000.0

STATEWIDE_FLOOR_AGI = (
    STATEWIDE_MILLIONAIRE_RETURNS
    * MILLIONAIRE_FLOOR_PER_RETURN
)

STATEWIDE_EXCESS_AGI = (
    STATEWIDE_MILLIONAIRE_AGI
    - STATEWIDE_FLOOR_AGI
)


# =============================================================================
# PREDECLARED HIGH-RELIABILITY VARIABLES
# =============================================================================

HIGH_RELIABILITY_VARIABLES = {
    "A00100",
    "A00900",
    "A01700",
}


# =============================================================================
# PREDECLARED CANDIDATES
# =============================================================================

CANDIDATE_DESCRIPTIONS = {
    "E0_COUNT": (
        "Frozen millionaire-count share"
    ),
    "E1_AGI": (
        "IRS $200K+ AGI share"
    ),
    "E2_BUSINESS": (
        "IRS $200K+ business/profession income share"
    ),
    "E3_PENSION": (
        "IRS $200K+ taxable pension/annuity share"
    ),
    "E4_COUNT_AGI_GM": (
        "Geometric mean of millionaire-count share and AGI share"
    ),
    "E5_COUNT_AGI_BUSINESS_GM": (
        "Geometric mean of millionaire-count, AGI, and business shares"
    ),
    "E6_COUNT_AGI_BUSINESS_PENSION_GM": (
        "Geometric mean of millionaire-count, AGI, business, and pension shares"
    ),
}


# =============================================================================
# HELPERS
# =============================================================================

def banner(title: str) -> None:
    print()
    print("=" * 110)
    print(title)
    print("=" * 110)
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


def normalize_ld(value: object) -> str:
    text = str(value).strip()

    if text.endswith(".0"):
        text = text[:-2]

    if text.isdigit():
        return text.zfill(3)

    return text


def normalize_positive_signal(values: pd.Series) -> pd.Series:
    """
    Convert a nonnegative signal into shares summing exactly to 1
    up to ordinary floating-point precision.
    """
    x = pd.to_numeric(
        values,
        errors="raise",
    ).astype(float)

    require(
        np.isfinite(x.to_numpy()).all(),
        "Signal contains nonfinite values.",
    )

    require(
        (x >= 0.0).all(),
        "Signal contains negative values.",
    )

    total = float(x.sum())

    require(
        total > 0.0,
        "Signal total must be positive.",
    )

    return x / total


def geometric_mean_signals(
    signals: list[pd.Series],
) -> pd.Series:
    """
    Row-wise geometric mean.

    All constituent signals are nonnegative shares.

    A zero constituent produces a zero geometric-mean signal for
    that LD. The resulting signal is normalized afterward.
    """
    matrix = np.column_stack(
        [
            pd.to_numeric(
                signal,
                errors="raise",
            ).astype(float).to_numpy()
            for signal in signals
        ]
    )

    require(
        np.isfinite(matrix).all(),
        "Geometric-mean input contains nonfinite values.",
    )

    require(
        (matrix >= 0.0).all(),
        "Geometric-mean input contains negative values.",
    )

    product = np.prod(
        matrix,
        axis=1,
    )

    gm = np.power(
        product,
        1.0 / matrix.shape[1],
    )

    return pd.Series(
        gm,
        index=signals[0].index,
    )


def pearson(x: pd.Series, y: pd.Series) -> float:
    return float(
        np.corrcoef(
            x.astype(float).to_numpy(),
            y.astype(float).to_numpy(),
        )[0, 1]
    )


def spearman(x: pd.Series, y: pd.Series) -> float:
    xr = x.rank(method="average")
    yr = y.rank(method="average")

    return pearson(xr, yr)


# =============================================================================
# INPUT VALIDATION
# =============================================================================

def validate_frozen_inputs() -> None:
    banner("STAGE 9B FROZEN INPUT PROVENANCE")

    required_files = [
        COUNT_PATH,
        LD_PREDICTOR_PATH,
        STAGE9A_PATH,
    ]

    for path in required_files:
        require(
            path.exists(),
            f"Missing required input: {path}",
        )

    count_hash = sha256_file(COUNT_PATH)
    predictor_hash = sha256_file(LD_PREDICTOR_PATH)
    stage9a_hash = sha256_file(STAGE9A_PATH)

    print(f"Frozen count geography          : {COUNT_PATH.relative_to(ROOT)}")
    print(f"SHA-256                         : {count_hash}")
    print()

    print(f"Frozen LD predictors            : {LD_PREDICTOR_PATH.relative_to(ROOT)}")
    print(f"SHA-256                         : {predictor_hash}")
    print()

    print(f"Frozen Stage 9A screen          : {STAGE9A_PATH.relative_to(ROOT)}")
    print(f"SHA-256                         : {stage9a_hash}")
    print()

    require(
        count_hash.lower() == EXPECTED_COUNT_SHA256.lower(),
        "Frozen millionaire-count geography hash mismatch.",
    )

    require(
        predictor_hash.lower() == EXPECTED_LD_PREDICTOR_SHA256.lower(),
        "Frozen Stage 6B LD predictor hash mismatch.",
    )

    require(
        stage9a_hash.lower() == EXPECTED_STAGE9A_SHA256.lower(),
        "Frozen Stage 9A reliability-screen hash mismatch.",
    )

    print("Frozen input validation         : PASS")


def validate_stage9a() -> None:
    banner("VERIFY STAGE 9A PREDICTOR FIREWALL")

    screen = pd.read_csv(
        STAGE9A_PATH
    )

    require(
        "variable" in screen.columns,
        "Stage 9A output lacks variable column.",
    )

    require(
        "reliability_class" in screen.columns,
        "Stage 9A output lacks reliability_class column.",
    )

    observed_high = set(
        screen.loc[
            screen["reliability_class"] == "HIGH",
            "variable",
        ].astype(str)
    )

    print(
        "Observed HIGH variables         : "
        + ", ".join(sorted(observed_high))
    )

    require(
        observed_high == HIGH_RELIABILITY_VARIABLES,
        (
            "Stage 9A HIGH-reliability variable set differs "
            "from frozen expectation."
        ),
    )

    print("Stage 9A predictor firewall     : PASS")


# =============================================================================
# READ / JOIN INPUTS
# =============================================================================

def read_inputs() -> pd.DataFrame:
    banner("READ FROZEN LD INPUTS")

    counts = pd.read_csv(
        COUNT_PATH,
        dtype={"ld": str},
    )

    predictors = pd.read_csv(
        LD_PREDICTOR_PATH,
        dtype={"ld": str},
    )

    counts["ld"] = counts["ld"].map(
        normalize_ld
    )

    predictors["ld"] = predictors["ld"].map(
        normalize_ld
    )

    require(
        len(counts) == 49,
        f"Expected 49 count rows; found {len(counts)}.",
    )

    require(
        len(predictors) == 49,
        f"Expected 49 predictor rows; found {len(predictors)}.",
    )

    require(
        counts["ld"].nunique() == 49,
        "Count LD identifiers are not unique.",
    )

    require(
        predictors["ld"].nunique() == 49,
        "Predictor LD identifiers are not unique.",
    )

    expected_lds = {
        f"{i:03d}"
        for i in range(1, 50)
    }

    require(
        set(counts["ld"]) == expected_lds,
        "Count universe is not exactly LD001-LD049.",
    )

    require(
        set(predictors["ld"]) == expected_lds,
        "Predictor universe is not exactly LD001-LD049.",
    )

    count_column = (
        "estimated_millionaire_returns_v0_2"
    )

    require(
        count_column in counts.columns,
        f"Missing frozen count column: {count_column}",
    )

    #
    # Use raw allocated predictor dollars and normalize them here.
    # This avoids dependence on assumptions about share-column names.
    #
    predictor_columns = [
        "A00100",
        "A00900",
        "A01700",
    ]

    for column in predictor_columns:
        require(
            column in predictors.columns,
            f"Missing LD predictor column: {column}",
        )

    merged = counts[
        [
            "ld",
            count_column,
        ]
    ].merge(
        predictors[
            [
                "ld",
                "A00100",
                "A00900",
                "A01700",
            ]
        ],
        on="ld",
        how="outer",
        validate="one_to_one",
        indicator=True,
    )

    require(
        len(merged) == 49,
        "Joined Stage 9B input does not contain 49 rows.",
    )

    require(
        (merged["_merge"] == "both").all(),
        "Count/predictor LD join is incomplete.",
    )

    merged = merged.drop(
        columns="_merge"
    )

    count_total = float(
        merged[count_column].sum()
    )

    require(
        abs(
            count_total
            - STATEWIDE_MILLIONAIRE_RETURNS
        ) <= 1e-8,
        (
            "Frozen millionaire-count geography does not "
            "reconcile to 21,530."
        ),
    )

    print(f"LD rows                         : {len(merged)}")
    print(f"Frozen millionaire returns      : {count_total:,.12f}")
    print("LD input join                   : PASS")

    return merged


# =============================================================================
# BUILD PREDECLARED SIGNALS
# =============================================================================

def build_candidate_signals(
    df: pd.DataFrame,
) -> dict[str, pd.Series]:

    banner("BUILD PREDECLARED EXCESS-AGI SIGNALS")

    count_share = normalize_positive_signal(
        df["estimated_millionaire_returns_v0_2"]
    )

    agi_share = normalize_positive_signal(
        df["A00100"]
    )

    business_share = normalize_positive_signal(
        df["A00900"]
    )

    pension_share = normalize_positive_signal(
        df["A01700"]
    )

    raw_signals = {
        "E0_COUNT":
            count_share,

        "E1_AGI":
            agi_share,

        "E2_BUSINESS":
            business_share,

        "E3_PENSION":
            pension_share,

        "E4_COUNT_AGI_GM":
            geometric_mean_signals(
                [
                    count_share,
                    agi_share,
                ]
            ),

        "E5_COUNT_AGI_BUSINESS_GM":
            geometric_mean_signals(
                [
                    count_share,
                    agi_share,
                    business_share,
                ]
            ),

        "E6_COUNT_AGI_BUSINESS_PENSION_GM":
            geometric_mean_signals(
                [
                    count_share,
                    agi_share,
                    business_share,
                    pension_share,
                ]
            ),
    }

    candidate_signals = {}

    for candidate, signal in raw_signals.items():
        normalized = normalize_positive_signal(
            signal
        )

        candidate_signals[candidate] = normalized

        print(
            f"{candidate:<36} "
            f"share sum={normalized.sum():.15f}  "
            f"min={normalized.min():.9f}  "
            f"max={normalized.max():.9f}"
        )

    require(
        set(candidate_signals)
        == set(CANDIDATE_DESCRIPTIONS),
        "Candidate universe differs from predeclared E0-E6 set.",
    )

    print()
    print("Candidate construction          : PASS")

    return candidate_signals


# =============================================================================
# CONSTRUCT SENSITIVITY ALLOCATIONS
# =============================================================================

def build_allocations(
    df: pd.DataFrame,
    signals: dict[str, pd.Series],
) -> pd.DataFrame:

    banner("ALLOCATE STATEWIDE EXCESS AGI")

    out = df.copy()

    floor_agi = (
        out["estimated_millionaire_returns_v0_2"]
        * MILLIONAIRE_FLOOR_PER_RETURN
    )

    out["millionaire_floor_agi"] = (
        floor_agi
    )

    for candidate, share in signals.items():

        excess_col = (
            f"{candidate}_excess_agi"
        )

        total_col = (
            f"{candidate}_millionaire_agi"
        )

        mean_col = (
            f"{candidate}_mean_agi_per_millionaire_return"
        )

        share_col = (
            f"{candidate}_excess_agi_share"
        )

        out[share_col] = share

        out[excess_col] = (
            share
            * STATEWIDE_EXCESS_AGI
        )

        out[total_col] = (
            out["millionaire_floor_agi"]
            + out[excess_col]
        )

        out[mean_col] = (
            out[total_col]
            / out["estimated_millionaire_returns_v0_2"]
        )

        excess_total = float(
            out[excess_col].sum()
        )

        agi_total = float(
            out[total_col].sum()
        )

        min_excess = float(
            out[excess_col].min()
        )

        min_mean = float(
            out[mean_col].min()
        )

        require(
            min_excess >= -1e-6,
            f"{candidate}: negative excess AGI produced.",
        )

        require(
            abs(
                excess_total
                - STATEWIDE_EXCESS_AGI
            ) <= 1e-4,
            (
                f"{candidate}: excess AGI does not reconcile "
                f"to statewide control."
            ),
        )

        require(
            abs(
                agi_total
                - STATEWIDE_MILLIONAIRE_AGI
            ) <= 1e-4,
            (
                f"{candidate}: total millionaire AGI does not "
                f"reconcile to statewide control."
            ),
        )

        require(
            min_mean >= MILLIONAIRE_FLOOR_PER_RETURN - 1e-6,
            (
                f"{candidate}: mean millionaire AGI below "
                "$1 million."
            ),
        )

        print(
            f"{candidate:<36} "
            f"Excess=${excess_total / 1e9:10.6f}B  "
            f"Total=${agi_total / 1e9:10.6f}B  "
            f"MinMean=${min_mean / 1e6:8.3f}M"
        )

    print()
    print("All candidate reconciliations   : PASS")

    return out


# =============================================================================
# SUMMARY
# =============================================================================

def build_summary(
    detail: pd.DataFrame,
) -> pd.DataFrame:

    banner("CANDIDATE SENSITIVITY SUMMARY")

    rows = []

    for candidate, description in CANDIDATE_DESCRIPTIONS.items():

        share_col = (
            f"{candidate}_excess_agi_share"
        )

        excess_col = (
            f"{candidate}_excess_agi"
        )

        total_col = (
            f"{candidate}_millionaire_agi"
        )

        mean_col = (
            f"{candidate}_mean_agi_per_millionaire_return"
        )

        ranked = detail.sort_values(
            total_col,
            ascending=False,
        )

        top1 = ranked.iloc[0]
        top3 = ranked.head(3)
        top5 = ranked.head(5)

        rows.append(
            {
                "candidate": candidate,
                "description": description,

                "excess_agi_total":
                    float(detail[excess_col].sum()),

                "millionaire_agi_total":
                    float(detail[total_col].sum()),

                "minimum_mean_agi":
                    float(detail[mean_col].min()),

                "maximum_mean_agi":
                    float(detail[mean_col].max()),

                "top_ld":
                    top1["ld"],

                "top_ld_millionaire_agi":
                    float(top1[total_col]),

                "top_ld_excess_share":
                    float(top1[share_col]),

                "top3_millionaire_agi_share":
                    float(
                        top3[total_col].sum()
                        / STATEWIDE_MILLIONAIRE_AGI
                    ),

                "top5_millionaire_agi_share":
                    float(
                        top5[total_col].sum()
                        / STATEWIDE_MILLIONAIRE_AGI
                    ),
            }
        )

    summary = pd.DataFrame(rows)

    print(
        summary[
            [
                "candidate",
                "top_ld",
                "minimum_mean_agi",
                "maximum_mean_agi",
                "top3_millionaire_agi_share",
                "top5_millionaire_agi_share",
            ]
        ].to_string(
            index=False,
            formatters={
                "minimum_mean_agi":
                    lambda x: f"${x / 1e6:,.3f}M",

                "maximum_mean_agi":
                    lambda x: f"${x / 1e6:,.3f}M",

                "top3_millionaire_agi_share":
                    lambda x: f"{100*x:.3f}%",

                "top5_millionaire_agi_share":
                    lambda x: f"{100*x:.3f}%",
            },
        )
    )

    return summary


# =============================================================================
# PAIRWISE SENSITIVITY
# =============================================================================

def build_pairwise_comparison(
    detail: pd.DataFrame,
) -> pd.DataFrame:

    banner("PAIRWISE CANDIDATE SENSITIVITY")

    candidates = list(
        CANDIDATE_DESCRIPTIONS
    )

    rows = []

    for i, candidate_a in enumerate(candidates):
        for candidate_b in candidates[i + 1:]:

            a = detail[
                f"{candidate_a}_millionaire_agi"
            ].astype(float)

            b = detail[
                f"{candidate_b}_millionaire_agi"
            ].astype(float)

            difference = a - b

            abs_difference = difference.abs()

            worst_index = abs_difference.idxmax()

            rows.append(
                {
                    "candidate_a": candidate_a,
                    "candidate_b": candidate_b,

                    "pearson_ld_agi":
                        pearson(a, b),

                    "spearman_ld_agi":
                        spearman(a, b),

                    "mean_absolute_ld_difference":
                        float(abs_difference.mean()),

                    "maximum_absolute_ld_difference":
                        float(abs_difference.max()),

                    "worst_ld":
                        detail.loc[worst_index, "ld"],
                }
            )

    pairwise = pd.DataFrame(rows)

    print(
        pairwise.to_string(
            index=False,
            formatters={
                "pearson_ld_agi":
                    lambda x: f"{x:.6f}",

                "spearman_ld_agi":
                    lambda x: f"{x:.6f}",

                "mean_absolute_ld_difference":
                    lambda x: f"${x / 1e6:,.3f}M",

                "maximum_absolute_ld_difference":
                    lambda x: f"${x / 1e6:,.3f}M",
            },
        )
    )

    return pairwise


# =============================================================================
# WATCH DISTRICTS
# =============================================================================

def print_watch_districts(
    detail: pd.DataFrame,
) -> None:

    banner("WATCH DISTRICTS")

    watch = [
        "014",
        "019",
        "029",
        "041",
        "043",
        "048",
    ]

    columns = [
        "ld",
        "estimated_millionaire_returns_v0_2",
    ]

    for candidate in CANDIDATE_DESCRIPTIONS:
        columns.append(
            f"{candidate}_millionaire_agi"
        )

    subset = (
        detail[
            detail["ld"].isin(watch)
        ][columns]
        .sort_values("ld")
        .copy()
    )

    formatters = {
        "estimated_millionaire_returns_v0_2":
            lambda x: f"{x:,.3f}",
    }

    for candidate in CANDIDATE_DESCRIPTIONS:
        column = (
            f"{candidate}_millionaire_agi"
        )

        formatters[column] = (
            lambda x: f"${x / 1e9:,.3f}B"
        )

    print(
        subset.to_string(
            index=False,
            formatters=formatters,
        )
    )


# =============================================================================
# CROSS-CANDIDATE LD ENVELOPE
# =============================================================================

def print_ld_uncertainty_envelope(
    detail: pd.DataFrame,
) -> None:

    banner("LARGEST CROSS-CANDIDATE LD AGI ENVELOPES")

    agi_columns = [
        f"{candidate}_millionaire_agi"
        for candidate in CANDIDATE_DESCRIPTIONS
    ]

    envelope = detail[
        [
            "ld",
            "estimated_millionaire_returns_v0_2",
        ]
    ].copy()

    envelope["minimum_candidate_agi"] = (
        detail[agi_columns].min(axis=1)
    )

    envelope["maximum_candidate_agi"] = (
        detail[agi_columns].max(axis=1)
    )

    envelope["candidate_agi_range"] = (
        envelope["maximum_candidate_agi"]
        - envelope["minimum_candidate_agi"]
    )

    envelope["range_as_share_statewide_agi"] = (
        envelope["candidate_agi_range"]
        / STATEWIDE_MILLIONAIRE_AGI
    )

    envelope = (
        envelope
        .sort_values(
            "candidate_agi_range",
            ascending=False,
        )
        .head(15)
    )

    print(
        envelope.to_string(
            index=False,
            formatters={
                "estimated_millionaire_returns_v0_2":
                    lambda x: f"{x:,.3f}",

                "minimum_candidate_agi":
                    lambda x: f"${x / 1e9:,.3f}B",

                "maximum_candidate_agi":
                    lambda x: f"${x / 1e9:,.3f}B",

                "candidate_agi_range":
                    lambda x: f"${x / 1e9:,.3f}B",

                "range_as_share_statewide_agi":
                    lambda x: f"{100*x:.3f}%",
            },
        )
    )


# =============================================================================
# WRITE OUTPUTS
# =============================================================================

def write_outputs(
    detail: pd.DataFrame,
    summary: pd.DataFrame,
    pairwise: pd.DataFrame,
) -> None:

    banner("WRITE STAGE 9B OUTPUTS")

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    detail = (
        detail
        .sort_values("ld")
        .reset_index(drop=True)
    )

    summary = (
        summary
        .reset_index(drop=True)
    )

    pairwise = (
        pairwise
        .reset_index(drop=True)
    )

    detail.to_csv(
        DETAIL_OUTPUT,
        index=False,
    )

    summary.to_csv(
        SUMMARY_OUTPUT,
        index=False,
    )

    pairwise.to_csv(
        PAIRWISE_OUTPUT,
        index=False,
    )

    for path in [
        DETAIL_OUTPUT,
        SUMMARY_OUTPUT,
        PAIRWISE_OUTPUT,
    ]:
        print(
            f"{path.name:<50} "
            f"{sha256_file(path)}"
        )


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:

    banner(
        "MILLIONAIRE TAX INCIDENCE v0.2 - "
        "STAGE 9B EXCESS-AGI SENSITIVITY ANALYSIS"
    )

    print("SENSITIVITY ANALYSIS - NOT MODEL SELECTION")
    print("NO CANDIDATE WINNER WILL BE DECLARED")
    print("NO HISTORICAL LD MILLIONAIRE INPUTS")
    print("NO OBSERVED LD MILLIONAIRE AGI ASSUMED")
    print("NO DATABASE WRITES")
    print()

    banner("STATEWIDE CONTROLS")

    print(
        f"Millionaire returns             : "
        f"{STATEWIDE_MILLIONAIRE_RETURNS:,.0f}"
    )

    print(
        f"Aggregate millionaire AGI       : "
        f"${STATEWIDE_MILLIONAIRE_AGI:,.0f}"
    )

    print(
        f"First-$1M floor AGI             : "
        f"${STATEWIDE_FLOOR_AGI:,.0f}"
    )

    print(
        f"Excess AGI control              : "
        f"${STATEWIDE_EXCESS_AGI:,.0f}"
    )

    require(
        abs(
            STATEWIDE_EXCESS_AGI
            - 44_426_796_000.0
        ) <= 1e-6,
        "Statewide excess-AGI arithmetic control failed.",
    )

    validate_frozen_inputs()

    validate_stage9a()

    inputs = read_inputs()

    signals = build_candidate_signals(
        inputs
    )

    detail = build_allocations(
        inputs,
        signals,
    )

    summary = build_summary(
        detail
    )

    pairwise = build_pairwise_comparison(
        detail
    )

    print_watch_districts(
        detail
    )

    print_ld_uncertainty_envelope(
        detail
    )

    write_outputs(
        detail=detail,
        summary=summary,
        pairwise=pairwise,
    )

    banner("STAGE 9B COMPLETE")

    print(
        "Seven predeclared excess-AGI allocation rules were "
        "constructed and reconciled independently to the same "
        "$44.426796 billion statewide excess-AGI control."
    )

    print()

    print(
        "No candidate has been selected as the preferred model."
    )

    print()

    print(
        "Stage 9B measures sensitivity of LD millionaire AGI "
        "to defensible alternative geographic allocation rules."
    )


if __name__ == "__main__":
    main()