"""
Stage 7B - Fit and calibrate the frozen millionaire-count geography model.

Purpose
-------
Fit the Stage 7A winning model once on the full 46-LD DOR validation
universe, score all 49 Washington legislative districts, and convert
those scores into a geographic distribution that reconciles exactly
to the authoritative IRS TY2022 statewide $1M+ return count.

Frozen Stage 7A winner:
    M5_AGI_DIVIDENDS
    share_A00100 + share_A00600

Authoritative statewide millionaire control:
    21,530 Washington TY2022 returns with AGI >= $1,000,000

IMPORTANT
---------
- Historical LD millionaire estimates are prohibited inputs.
- DOR capital-gains taxpayer counts are an independent proxy for
  extreme-income geography, NOT observed IRS millionaire counts.
- DOR payment dollars do not enter model fitting.
- LD14/19/29 have no invented DOR targets. They are scored only after
  fitting, using their independently constructed IRS predictors.
- Fractional expected millionaire counts are preserved.
- No database writes.
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

PREDICTOR_PATH = (
    ROOT
    / "data"
    / "processed"
    / "validation"
    / "irs_ld_ty2022"
    / "irs_ty2022_ld_upper_tail_predictors.csv"
)

VALIDATION_PATH = (
    ROOT
    / "data"
    / "processed"
    / "validation"
    / "millionaire_count_v0_2"
    / "stage7a_validation_dataset.csv"
)

TOURNAMENT_PATH = (
    ROOT
    / "data"
    / "processed"
    / "validation"
    / "millionaire_count_v0_2"
    / "stage7a_model_tournament.csv"
)

OUTPUT_DIR = (
    ROOT
    / "data"
    / "processed"
    / "validation"
    / "millionaire_count_v0_2"
)

MODEL_OUTPUT = (
    OUTPUT_DIR
    / "stage7b_frozen_model_coefficients.csv"
)

SCORES_OUTPUT = (
    OUTPUT_DIR
    / "stage7b_ld_model_scores.csv"
)

ALLOCATION_OUTPUT = (
    OUTPUT_DIR
    / "millionaire_geography_v0_2_ty2022.csv"
)


# =============================================================================
# FROZEN INPUT HASHES
# =============================================================================

EXPECTED_PREDICTOR_SHA256 = (
    "f2b42b70202bf9dcee431b2914a286eccfc515772f516018683662887669653a"
)

EXPECTED_VALIDATION_SHA256 = (
    "9c3f249278bb6c7bff4012d3abb64448c5d6e670b5d01421295d4b08191db3f6"
)

EXPECTED_TOURNAMENT_SHA256 = (
    "12d728651fe0e5d6b8e2ff3989a829aada0a578cd614d513831c793eeb09cafd"
)


# =============================================================================
# FROZEN MODEL SPECIFICATION
# =============================================================================

WINNER_MODEL_ID = "M5_AGI_DIVIDENDS"

PREDICTORS = [
    "share_A00100",
    "share_A00600",
]

EXPECTED_STAGE7A_MAE = 13.099

STATEWIDE_MILLIONAIRE_RETURNS = 21_530

EXPECTED_LD_COUNT = 49
EXPECTED_VALIDATION_LD_COUNT = 46

DISCLOSURE_ONLY_LDS = {
    "014",
    "019",
    "029",
}


# =============================================================================
# HELPERS
# =============================================================================

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


def normalize_ld(value: object) -> str:
    text = str(value).strip()

    if text.endswith(".0"):
        text = text[:-2]

    if text.isdigit():
        return text.zfill(3)

    return text


def fit_ols(
    X: np.ndarray,
    y: np.ndarray,
) -> np.ndarray:
    """
    Ordinary least squares with intercept.
    """

    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)

    design = np.column_stack(
        [
            np.ones(len(X), dtype=float),
            X,
        ]
    )

    beta, _, _, _ = np.linalg.lstsq(
        design,
        y,
        rcond=None,
    )

    return beta


def predict_ols(
    beta: np.ndarray,
    X: np.ndarray,
) -> np.ndarray:
    X = np.asarray(X, dtype=float)

    design = np.column_stack(
        [
            np.ones(len(X), dtype=float),
            X,
        ]
    )

    return design @ beta


# =============================================================================
# FROZEN PROVENANCE
# =============================================================================

def validate_frozen_inputs() -> None:
    banner("FROZEN STAGE 7B INPUT PROVENANCE")

    frozen = [
        (
            "Stage 6B IRS predictors",
            PREDICTOR_PATH,
            EXPECTED_PREDICTOR_SHA256,
        ),
        (
            "Stage 7A validation dataset",
            VALIDATION_PATH,
            EXPECTED_VALIDATION_SHA256,
        ),
        (
            "Stage 7A tournament",
            TOURNAMENT_PATH,
            EXPECTED_TOURNAMENT_SHA256,
        ),
    ]

    for label, path, expected_hash in frozen:
        require(
            path.exists(),
            f"Missing frozen input: {path}",
        )

        actual_hash = sha256_file(path)

        print(f"{label}")
        print(f"  Path    : {path.relative_to(ROOT)}")
        print(f"  SHA-256 : {actual_hash}")

        require(
            actual_hash.lower() == expected_hash.lower(),
            f"Frozen hash mismatch: {label}",
        )

        print("  Status  : PASS")
        print()

    print("Frozen provenance validation    : PASS")


# =============================================================================
# CONFIRM STAGE 7A WINNER
# =============================================================================

def validate_stage7a_winner() -> None:
    banner("CONFIRM FROZEN STAGE 7A WINNER")

    tournament = pd.read_csv(TOURNAMENT_PATH)

    require(
        len(tournament) == 6,
        "Stage 7A tournament does not contain exactly six candidates.",
    )

    require(
        "rank_by_mae" in tournament.columns,
        "Tournament is missing rank_by_mae.",
    )

    winner = tournament.loc[
        tournament["rank_by_mae"].eq(1)
    ]

    require(
        len(winner) == 1,
        "Tournament does not contain exactly one rank-1 model.",
    )

    winner = winner.iloc[0]

    actual_model = str(winner["model_id"])

    actual_predictors = str(winner["predictors"])

    actual_mae = float(winner["loocv_mae"])

    require(
        actual_model == WINNER_MODEL_ID,
        (
            "Frozen Stage 7A winner mismatch: "
            f"{actual_model}"
        ),
    )

    require(
        actual_predictors
        == "share_A00100+share_A00600",
        (
            "Frozen Stage 7A predictor specification mismatch: "
            f"{actual_predictors}"
        ),
    )

    require(
        abs(actual_mae - EXPECTED_STAGE7A_MAE) < 0.001,
        (
            "Frozen Stage 7A MAE differs unexpectedly: "
            f"{actual_mae:.6f}"
        ),
    )

    print(f"Winner model                    : {actual_model}")
    print(f"Winner predictors               : {actual_predictors}")
    print(f"Winner LOOCV MAE                : {actual_mae:.6f}")
    print()
    print("Frozen winner validation        : PASS")


# =============================================================================
# READ AND PREPARE DATA
# =============================================================================

def read_predictors() -> pd.DataFrame:
    banner("READ 49-LD IRS PREDICTOR UNIVERSE")

    df = pd.read_csv(
        PREDICTOR_PATH,
        dtype={"ld": str},
    )

    df["ld"] = df["ld"].map(normalize_ld)

    require(
        len(df) == EXPECTED_LD_COUNT,
        f"Expected 49 LDs; found {len(df)}.",
    )

    require(
        df["ld"].nunique() == EXPECTED_LD_COUNT,
        "LD identifiers are not unique.",
    )

    expected_lds = {
        f"{i:03d}"
        for i in range(1, 50)
    }

    require(
        set(df["ld"]) == expected_lds,
        "Predictor universe is not exactly LD001-LD049.",
    )

    #
    # Recompute shares exactly as Stage 7A did.
    #
    for raw_col in [
        "A00100",
        "A00600",
    ]:
        require(
            raw_col in df.columns,
            f"Missing predictor: {raw_col}",
        )

        df[raw_col] = pd.to_numeric(
            df[raw_col],
            errors="raise",
        )

        total = float(df[raw_col].sum())

        require(
            total > 0,
            f"Non-positive predictor total: {raw_col}",
        )

        share_col = f"share_{raw_col}"

        df[share_col] = (
            df[raw_col].astype(float)
            / total
        )

        require(
            abs(float(df[share_col].sum()) - 1.0)
            <= 1e-12,
            f"{share_col} does not sum to 1.",
        )

    print(f"LD rows                         : {len(df):,}")
    print(
        f"share_A00100 sum                : "
        f"{df['share_A00100'].sum():.15f}"
    )
    print(
        f"share_A00600 sum                : "
        f"{df['share_A00600'].sum():.15f}"
    )
    print()
    print("49-LD predictor universe        : PASS")

    return df


def read_validation() -> pd.DataFrame:
    banner("READ 46-LD STAGE 7A VALIDATION SAMPLE")

    df = pd.read_csv(
        VALIDATION_PATH,
        dtype={"ld": str},
    )

    df["ld"] = df["ld"].map(normalize_ld)

    require(
        len(df) == EXPECTED_VALIDATION_LD_COUNT,
        (
            "Expected 46 validation LDs; "
            f"found {len(df)}."
        ),
    )

    require(
        df["ld"].nunique() == EXPECTED_VALIDATION_LD_COUNT,
        "Validation LD identifiers are not unique.",
    )

    actual_missing = {
        f"{i:03d}"
        for i in range(1, 50)
    } - set(df["ld"])

    require(
        actual_missing == DISCLOSURE_ONLY_LDS,
        (
            "Validation sample does not omit exactly "
            "LD014/019/029."
        ),
    )

    require(
        "taxpayers_with_net_payment" in df.columns,
        "Missing DOR validation target.",
    )

    df["taxpayers_with_net_payment"] = pd.to_numeric(
        df["taxpayers_with_net_payment"],
        errors="raise",
    )

    for col in PREDICTORS:
        require(
            col in df.columns,
            f"Validation dataset missing frozen predictor: {col}",
        )

        df[col] = pd.to_numeric(
            df[col],
            errors="raise",
        )

    require(
        int(df["taxpayers_with_net_payment"].sum()) == 3241,
        "DOR validation target does not sum to 3,241.",
    )

    print(f"Validation rows                 : {len(df):,}")
    print(
        "Validation target total         : "
        f"{df['taxpayers_with_net_payment'].sum():,.0f}"
    )
    print(
        "DOR-disclosure-only LDs         : "
        + ", ".join(sorted(DISCLOSURE_ONLY_LDS))
    )
    print()
    print("Stage 7A validation sample      : PASS")

    return df


# =============================================================================
# FIT FROZEN M5
# =============================================================================

def fit_frozen_model(
    validation: pd.DataFrame,
) -> tuple[np.ndarray, pd.DataFrame]:
    banner("FIT FROZEN M5 ON ALL 46 DISCLOSED LDS")

    X = validation[
        PREDICTORS
    ].to_numpy(dtype=float)

    y = validation[
        "taxpayers_with_net_payment"
    ].to_numpy(dtype=float)

    beta = fit_ols(X, y)

    fitted = predict_ols(
        beta,
        X,
    )

    residual = fitted - y

    coefficient_rows = [
        {
            "term": "intercept",
            "coefficient": float(beta[0]),
        },
        {
            "term": PREDICTORS[0],
            "coefficient": float(beta[1]),
        },
        {
            "term": PREDICTORS[1],
            "coefficient": float(beta[2]),
        },
    ]

    coefficients = pd.DataFrame(
        coefficient_rows
    )

    print("FROZEN MODEL COEFFICIENTS")
    print("-" * 100)

    print(
        coefficients.to_string(
            index=False,
            formatters={
                "coefficient": "{:,.12f}".format,
            },
        )
    )

    print()
    print("IN-SAMPLE FIT DIAGNOSTICS")
    print("-" * 100)

    mae = float(
        np.mean(np.abs(residual))
    )

    rmse = float(
        np.sqrt(np.mean(residual ** 2))
    )

    pearson = float(
        np.corrcoef(y, fitted)[0, 1]
    )

    print(f"Training observations           : {len(y):,}")
    print(f"Training MAE                    : {mae:,.6f}")
    print(f"Training RMSE                   : {rmse:,.6f}")
    print(f"Training Pearson                : {pearson:.6f}")
    print()
    print(
        "NOTE: These in-sample diagnostics do NOT replace "
        "the Stage 7A LOOCV selection metrics."
    )

    return beta, coefficients


# =============================================================================
# SCORE ALL 49 LDS
# =============================================================================

def score_all_lds(
    predictors: pd.DataFrame,
    beta: np.ndarray,
) -> pd.DataFrame:
    banner("SCORE ALL 49 LEGISLATIVE DISTRICTS")

    scored = predictors[
        [
            "ld",
            "A00100",
            "A00600",
            "share_A00100",
            "share_A00600",
        ]
    ].copy()

    X = scored[
        PREDICTORS
    ].to_numpy(dtype=float)

    scored["raw_model_score"] = predict_ols(
        beta,
        X,
    )

    scored["is_dor_disclosure_only_ld"] = (
        scored["ld"].isin(DISCLOSURE_ONLY_LDS)
    )

    negative = scored.loc[
        scored["raw_model_score"] < 0
    ].copy()

    zero = scored.loc[
        scored["raw_model_score"] == 0
    ].copy()

    print(
        f"Raw score sum                   : "
        f"{scored['raw_model_score'].sum():,.12f}"
    )
    print(
        f"Minimum raw score               : "
        f"{scored['raw_model_score'].min():,.12f}"
    )
    print(
        f"Maximum raw score               : "
        f"{scored['raw_model_score'].max():,.12f}"
    )
    print(
        f"Negative raw scores             : "
        f"{len(negative):,}"
    )
    print(
        f"Zero raw scores                 : "
        f"{len(zero):,}"
    )

    if len(negative) > 0:
        print()
        print("NEGATIVE RAW SCORES")
        print("-" * 100)
        print(
            negative[
                [
                    "ld",
                    "share_A00100",
                    "share_A00600",
                    "raw_model_score",
                ]
            ].to_string(
                index=False,
                formatters={
                    "share_A00100": "{:.9f}".format,
                    "share_A00600": "{:.9f}".format,
                    "raw_model_score": "{:,.6f}".format,
                },
            )
        )

    print()
    print("DOR-DISCLOSURE-ONLY LDS")
    print("-" * 100)

    print(
        scored.loc[
            scored["is_dor_disclosure_only_ld"],
            [
                "ld",
                "share_A00100",
                "share_A00600",
                "raw_model_score",
            ],
        ].to_string(
            index=False,
            formatters={
                "share_A00100": "{:.9f}".format,
                "share_A00600": "{:.9f}".format,
                "raw_model_score": "{:,.6f}".format,
            },
        )
    )

    return scored


# =============================================================================
# TRANSFORM SCORES INTO MILLIONAIRE GEOGRAPHY
# =============================================================================

def allocate_millionaires(
    scored: pd.DataFrame,
) -> pd.DataFrame:
    banner("CALIBRATE 49-LD GEOGRAPHY TO IRS STATEWIDE MILLIONAIRE CONTROL")

    result = scored.copy()

    #
    # Frozen Stage 7B nonnegativity rule:
    #
    # OLS may theoretically produce negative proxy counts. Negative counts
    # have no coherent interpretation as geographic incidence. Therefore,
    # raw predictions below zero are floored at zero BEFORE normalization.
    #
    # This rule is mechanical and is reported explicitly.
    #
    result["nonnegative_model_score"] = (
        result["raw_model_score"]
        .clip(lower=0.0)
    )

    raw_negative_count = int(
        (result["raw_model_score"] < 0).sum()
    )

    score_sum = float(
        result["nonnegative_model_score"].sum()
    )

    require(
        score_sum > 0,
        "Nonnegative model-score total is not positive.",
    )

    result["millionaire_share_v0_2"] = (
        result["nonnegative_model_score"]
        / score_sum
    )

    result["estimated_millionaire_returns_v0_2"] = (
        result["millionaire_share_v0_2"]
        * STATEWIDE_MILLIONAIRE_RETURNS
    )

    share_sum = float(
        result["millionaire_share_v0_2"].sum()
    )

    estimated_total = float(
        result[
            "estimated_millionaire_returns_v0_2"
        ].sum()
    )

    require(
        abs(share_sum - 1.0) <= 1e-12,
        "Millionaire shares do not sum to 1.",
    )

    require(
        abs(
            estimated_total
            - STATEWIDE_MILLIONAIRE_RETURNS
        ) <= 1e-8,
        (
            "Millionaire estimates do not reconcile "
            "to statewide control."
        ),
    )

    print(
        "Authoritative IRS statewide count: "
        f"{STATEWIDE_MILLIONAIRE_RETURNS:,}"
    )
    print(
        f"Raw negative predictions        : "
        f"{raw_negative_count:,}"
    )
    print(
        f"Nonnegative score sum           : "
        f"{score_sum:,.12f}"
    )
    print(
        f"Millionaire share sum           : "
        f"{share_sum:.15f}"
    )
    print(
        f"Estimated millionaire total     : "
        f"{estimated_total:,.12f}"
    )
    print()

    print("TOP 15 ESTIMATED MILLIONAIRE DISTRICTS")
    print("-" * 100)

    top = result.sort_values(
        "estimated_millionaire_returns_v0_2",
        ascending=False,
    ).head(15)

    print(
        top[
            [
                "ld",
                "raw_model_score",
                "millionaire_share_v0_2",
                "estimated_millionaire_returns_v0_2",
            ]
        ].to_string(
            index=False,
            formatters={
                "raw_model_score": "{:,.6f}".format,
                "millionaire_share_v0_2": "{:.6%}".format,
                "estimated_millionaire_returns_v0_2": "{:,.3f}".format,
            },
        )
    )

    print()
    print("WATCH LDS")
    print("-" * 100)

    print(
        result.loc[
            result["ld"].isin(
                {
                    "014",
                    "019",
                    "029",
                    "041",
                    "043",
                    "048",
                }
            ),
            [
                "ld",
                "raw_model_score",
                "millionaire_share_v0_2",
                "estimated_millionaire_returns_v0_2",
                "is_dor_disclosure_only_ld",
            ],
        ].sort_values(
            "ld"
        ).to_string(
            index=False,
            formatters={
                "raw_model_score": "{:,.6f}".format,
                "millionaire_share_v0_2": "{:.6%}".format,
                "estimated_millionaire_returns_v0_2": "{:,.3f}".format,
            },
        )
    )

    return result


# =============================================================================
# WRITE ARTIFACTS
# =============================================================================

def write_outputs(
    coefficients: pd.DataFrame,
    scored: pd.DataFrame,
    allocation: pd.DataFrame,
) -> None:
    banner("WRITE STAGE 7B ARTIFACTS")

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    coefficients.to_csv(
        MODEL_OUTPUT,
        index=False,
    )

    scored.to_csv(
        SCORES_OUTPUT,
        index=False,
    )

    allocation.to_csv(
        ALLOCATION_OUTPUT,
        index=False,
    )

    for path in [
        MODEL_OUTPUT,
        SCORES_OUTPUT,
        ALLOCATION_OUTPUT,
    ]:
        print(
            f"Wrote                            : "
            f"{path.relative_to(ROOT)}"
        )
        print(
            f"SHA-256                          : "
            f"{sha256_file(path)}"
        )
        print()


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:
    banner(
        "MILLIONAIRE TAX LD MODEL - STAGE 7B FIT AND CALIBRATION"
    )

    print("NO DATABASE WRITES")
    print("NO HISTORICAL LD MILLIONAIRE INPUTS")
    print("NO DOR PAYMENT-DOLLAR MODEL FITTING")
    print("NO INTEGERIZATION")
    print()
    print(
        "Frozen model: M5_AGI_DIVIDENDS "
        "(share_A00100 + share_A00600)"
    )
    print(
        "Statewide IRS TY2022 $1M+ return control: "
        f"{STATEWIDE_MILLIONAIRE_RETURNS:,}"
    )

    validate_frozen_inputs()
    validate_stage7a_winner()

    predictors = read_predictors()
    validation = read_validation()

    beta, coefficients = fit_frozen_model(
        validation=validation,
    )

    scored = score_all_lds(
        predictors=predictors,
        beta=beta,
    )

    allocation = allocate_millionaires(
        scored=scored,
    )

    write_outputs(
        coefficients=coefficients,
        scored=scored,
        allocation=allocation,
    )

    banner("STAGE 7B COMPLETE")

    print(
        "Stage 7B has produced a 49-LD fractional expected-count "
        "distribution reconciled exactly to the authoritative "
        f"IRS statewide control of {STATEWIDE_MILLIONAIRE_RETURNS:,}."
    )
    print()
    print("INTERPRETATION")
    print("-" * 100)
    print(
        "1. These are modeled legislative-district estimates, "
        "not observed IRS millionaire counts."
    )
    print(
        "2. M5 was selected in Stage 7A using strict LOOCV MAE "
        "against independent DOR taxpayer geography."
    )
    print(
        "3. Stage 7B fits that frozen model once on all 46 "
        "individually disclosed DOR districts."
    )
    print(
        "4. LD14/19/29 enter only at the scoring stage through "
        "their independently constructed IRS predictors."
    )
    print(
        "5. Any negative OLS scores are explicitly reported and "
        "mechanically floored at zero before geographic normalization."
    )
    print(
        "6. Fractional expected counts are the primary statistical "
        "estimate; no integerization has been performed."
    )
    print(
        "7. Historical LD millionaire estimates and legacy model "
        "outputs did not enter the computational path."
    )


if __name__ == "__main__":
    main()