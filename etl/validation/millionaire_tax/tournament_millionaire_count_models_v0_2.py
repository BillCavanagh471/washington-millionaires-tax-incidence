"""
Stage 7A - Millionaire-count geographic model tournament.

Purpose
-------
Compare a small, predeclared set of candidate models for Washington
legislative-district upper-tail geography.

The outcome used for external validation is Washington DOR TY2022
capital-gains taxpayers with net payment for the 46 individually
disclosed legislative districts.

IMPORTANT:
- DOR capital-gains taxpayers are an external proxy for extreme-income
  geography. They are NOT observed IRS $1M+ taxpayer counts.
- Historical legislative-district millionaire estimates are prohibited.
- DOR payment dollars do not select the model.
- No statewide 21,530-millionaire calibration occurs in Stage 7A.
- No database writes.
"""

from __future__ import annotations

import hashlib
import math
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

DOR_PATH = (
    ROOT
    / "data"
    / "processed"
    / "validation"
    / "dor_capital_gains_ty2022"
    / "dor_ty2022_capital_gains_by_ld.csv"
)

OUTPUT_DIR = (
    ROOT
    / "data"
    / "processed"
    / "validation"
    / "millionaire_count_v0_2"
)

TOURNAMENT_OUTPUT = OUTPUT_DIR / "stage7a_model_tournament.csv"
LOOCV_OUTPUT = OUTPUT_DIR / "stage7a_loocv_predictions.csv"
JOINED_OUTPUT = OUTPUT_DIR / "stage7a_validation_dataset.csv"


# =============================================================================
# FROZEN INPUT HASHES
# =============================================================================

EXPECTED_PREDICTOR_SHA256 = (
    "f2b42b70202bf9dcee431b2914a286eccfc515772f516018683662887669653a"
)

EXPECTED_DOR_SHA256 = (
    "f073b45abb91e1b11da4e0a838a63e16d268e2d84e0e1e08ef2e1be6cf82a998"
)


# =============================================================================
# FROZEN CONTROLS
# =============================================================================

EXPECTED_LD_COUNT = 49
EXPECTED_DOR_DISCLOSED_LDS = 46
EXPECTED_DOR_DISCLOSED_TAXPAYERS = 3241
EXPECTED_DOR_DISCLOSED_PAYMENTS = 722_857_253

EXPECTED_DOR_ALL_ROWS = 49
EXPECTED_DOR_ALL_TAXPAYERS = 3594
EXPECTED_DOR_COMPONENT_PAYMENTS = 780_401_875
DOR_PRINTED_PAYMENT_TOTAL = 780_401_874

EXPECTED_SPECIAL_ROWS = {
    "014_019_029",
    "OUT_OF_STATE",
    "UNKNOWN",
}

WATCH_LDS = {"041", "043", "048"}


# =============================================================================
# PREDECLARED CANDIDATE MODELS
# =============================================================================
#
# All IRS predictors enter as Stage 6B legislative-district shares.
#
# Primary model-selection criterion:
#     strict LOOCV MAE in DOR taxpayer counts
#
# Secondary diagnostics:
#     RMSE
#     Pearson correlation
#     Spearman rank correlation
#     mean signed error
#     maximum absolute error
#     LD41 / LD43 / LD48 holdout errors
#
# No candidate may be added or removed after tournament results are seen
# without explicitly creating a new model-development stage/version.
#

MODELS = {
    "M0_N1": [
        "share_N1",
    ],
    "M1_N1_AGI": [
        "share_N1",
        "share_A00100",
    ],
    "M2_N1_DIVIDENDS": [
        "share_N1",
        "share_A00600",
    ],
    "M3_N1_CAPGAINS": [
        "share_N1",
        "share_A01000",
    ],
    "M4_N1_PARTNERSHIP": [
        "share_N1",
        "share_A26270",
    ],
    "M5_AGI_DIVIDENDS": [
        "share_A00100",
        "share_A00600",
    ],
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


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)

    return h.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def normalize_ld(value: object) -> str:
    """
    Normalize individually disclosed LD identifiers to three digits while
    preserving special DOR identifiers exactly.
    """

    text = str(value).strip()

    if text in EXPECTED_SPECIAL_ROWS:
        return text

    if text.endswith(".0"):
        text = text[:-2]

    if text.isdigit():
        return text.zfill(3)

    return text


def average_ranks(values: np.ndarray) -> np.ndarray:
    """
    Return 1-based average ranks, equivalent to standard tied-rank behavior.
    """

    return (
        pd.Series(values)
        .rank(method="average")
        .to_numpy(dtype=float)
    )


def pearson_corr(x: np.ndarray, y: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)

    if len(x) < 2:
        return float("nan")

    if np.allclose(x, x[0]) or np.allclose(y, y[0]):
        return float("nan")

    return float(np.corrcoef(x, y)[0, 1])


def spearman_corr(x: np.ndarray, y: np.ndarray) -> float:
    return pearson_corr(
        average_ranks(np.asarray(x, dtype=float)),
        average_ranks(np.asarray(y, dtype=float)),
    )


def fit_ols(
    X: np.ndarray,
    y: np.ndarray,
) -> np.ndarray:
    """
    Ordinary least squares with intercept.

    numpy.linalg.lstsq is used deliberately so Stage 7A does not require
    scipy or scikit-learn.
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
# INPUT VALIDATION
# =============================================================================

def validate_hashes() -> None:
    banner("FROZEN SOURCE PROVENANCE")

    require(
        PREDICTOR_PATH.exists(),
        f"Missing predictor file: {PREDICTOR_PATH}",
    )

    require(
        DOR_PATH.exists(),
        f"Missing DOR validation file: {DOR_PATH}",
    )

    predictor_hash = sha256_file(PREDICTOR_PATH)
    dor_hash = sha256_file(DOR_PATH)

    print(f"IRS LD predictor source          : {PREDICTOR_PATH.relative_to(ROOT)}")
    print(f"IRS LD predictor SHA-256        : {predictor_hash}")
    print()
    print(f"DOR validation source           : {DOR_PATH.relative_to(ROOT)}")
    print(f"DOR validation SHA-256          : {dor_hash}")
    print()

    require(
        predictor_hash.lower() == EXPECTED_PREDICTOR_SHA256.lower(),
        "IRS LD predictor SHA-256 does not match frozen Stage 6B artifact.",
    )

    require(
        dor_hash.lower() == EXPECTED_DOR_SHA256.lower(),
        "DOR validation SHA-256 does not match frozen Stage 7 source.",
    )

    print("Frozen source hash validation   : PASS")


def read_predictors() -> pd.DataFrame:
    banner("READ STAGE 6B IRS LD PREDICTORS")

    df = pd.read_csv(
        PREDICTOR_PATH,
        dtype={"ld": str},
    )

    df["ld"] = df["ld"].map(normalize_ld)

    require(
        len(df) == EXPECTED_LD_COUNT,
        f"Expected {EXPECTED_LD_COUNT} predictor rows; found {len(df)}.",
    )

    require(
        df["ld"].nunique() == EXPECTED_LD_COUNT,
        "Predictor LD identifiers are not unique.",
    )

    expected_lds = {f"{i:03d}" for i in range(1, 50)}

    require(
        set(df["ld"]) == expected_lds,
        "Predictor dataset does not contain exactly LD001-LD049.",
    )

    required_raw = [
        "N1",
        "A00100",
        "A00600",
        "A01000",
        "A26270",
    ]

    for col in required_raw:
        require(
            col in df.columns,
            f"Missing required predictor column: {col}",
        )

        df[col] = pd.to_numeric(
            df[col],
            errors="raise",
        )

    #
    # Recompute the shares used by the tournament directly from the frozen
    # Stage 6B totals. This avoids dependence on display formatting and makes
    # the model-input transformation explicit.
    #
    for col in required_raw:
        total = float(df[col].sum())

        require(
            total > 0,
            f"Predictor total must be positive: {col}",
        )

        share_col = f"share_{col}"

        df[share_col] = (
            df[col].astype(float)
            / total
        )

        error = abs(float(df[share_col].sum()) - 1.0)

        require(
            error <= 1e-12,
            f"{share_col} does not sum to 1.0.",
        )

    print(f"LD rows                         : {len(df):,}")
    print(f"Distinct LDs                    : {df['ld'].nunique():,}")
    print()

    for col in required_raw:
        share_col = f"share_{col}"
        print(
            f"{share_col:<30}: "
            f"{df[share_col].sum():.15f}"
        )

    print()
    print("Stage 6B predictor validation   : PASS")

    return df


def read_dor() -> tuple[pd.DataFrame, pd.DataFrame]:
    banner("READ AUTHORITATIVE DOR TY2022 VALIDATION TARGET")

    df = pd.read_csv(
        DOR_PATH,
        dtype={"ld": str},
    )

    df["ld"] = df["ld"].map(normalize_ld)

    df["taxpayers_with_net_payment"] = pd.to_numeric(
        df["taxpayers_with_net_payment"],
        errors="raise",
    )

    df["net_payment"] = pd.to_numeric(
        df["net_payment"],
        errors="raise",
    )

    require(
        len(df) == EXPECTED_DOR_ALL_ROWS,
        f"Expected {EXPECTED_DOR_ALL_ROWS} DOR rows; found {len(df)}.",
    )

    require(
        df["ld"].nunique() == EXPECTED_DOR_ALL_ROWS,
        "DOR LD/special identifiers are not unique.",
    )

    all_taxpayers = int(
        df["taxpayers_with_net_payment"].sum()
    )

    component_payments = int(
        df["net_payment"].sum()
    )

    require(
        all_taxpayers == EXPECTED_DOR_ALL_TAXPAYERS,
        (
            "DOR all-component taxpayer total mismatch: "
            f"{all_taxpayers:,}"
        ),
    )

    require(
        component_payments == EXPECTED_DOR_COMPONENT_PAYMENTS,
        (
            "DOR component payment total mismatch: "
            f"${component_payments:,.0f}"
        ),
    )

    special = df[
        df["ld"].isin(EXPECTED_SPECIAL_ROWS)
    ].copy()

    require(
        set(special["ld"]) == EXPECTED_SPECIAL_ROWS,
        "DOR special-row universe mismatch.",
    )

    disclosed = df[
        df["ld"].str.fullmatch(r"\d{3}")
    ].copy()

    require(
        len(disclosed) == EXPECTED_DOR_DISCLOSED_LDS,
        (
            "Expected "
            f"{EXPECTED_DOR_DISCLOSED_LDS} individually disclosed LDs; "
            f"found {len(disclosed)}."
        ),
    )

    disclosed_taxpayers = int(
        disclosed["taxpayers_with_net_payment"].sum()
    )

    disclosed_payments = int(
        disclosed["net_payment"].sum()
    )

    require(
        disclosed_taxpayers == EXPECTED_DOR_DISCLOSED_TAXPAYERS,
        (
            "Individually disclosed DOR taxpayer control mismatch: "
            f"{disclosed_taxpayers:,}"
        ),
    )

    require(
        disclosed_payments == EXPECTED_DOR_DISCLOSED_PAYMENTS,
        (
            "Individually disclosed DOR payment control mismatch: "
            f"${disclosed_payments:,.0f}"
        ),
    )

    #
    # Watch-LD controls.
    #
    watch_expected = {
        "041": (371, 38_977_961),
        "043": (403, 71_887_515),
        "048": (423, 394_135_035),
    }

    for ld, (expected_n, expected_payment) in watch_expected.items():
        row = disclosed.loc[
            disclosed["ld"].eq(ld)
        ]

        require(
            len(row) == 1,
            f"Missing or duplicate DOR watch LD: {ld}",
        )

        actual_n = int(
            row.iloc[0]["taxpayers_with_net_payment"]
        )

        actual_payment = int(
            row.iloc[0]["net_payment"]
        )

        require(
            actual_n == expected_n,
            f"DOR LD{ld} taxpayer control mismatch.",
        )

        require(
            actual_payment == expected_payment,
            f"DOR LD{ld} payment control mismatch.",
        )

    printed_difference = (
        component_payments
        - DOR_PRINTED_PAYMENT_TOTAL
    )

    print(f"DOR rows                        : {len(df):,}")
    print(f"All-component taxpayers         : {all_taxpayers:,}")
    print(
        "All-component payments          : "
        f"${component_payments:,.0f}"
    )
    print(
        "DOR printed payment total       : "
        f"${DOR_PRINTED_PAYMENT_TOTAL:,.0f}"
    )
    print(
        "Published component-minus-total : "
        f"${printed_difference:,.0f}"
    )
    print()
    print(
        "Individually disclosed LDs      : "
        f"{len(disclosed):,}"
    )
    print(
        "Disclosed-LD taxpayers          : "
        f"{disclosed_taxpayers:,}"
    )
    print(
        "Disclosed-LD payments           : "
        f"${disclosed_payments:,.0f}"
    )
    print()

    print("WATCH LD CONTROLS")
    print("-" * 100)

    print(
        disclosed.loc[
            disclosed["ld"].isin(WATCH_LDS),
            [
                "ld",
                "taxpayers_with_net_payment",
                "net_payment",
            ],
        ].to_string(index=False)
    )

    print()
    print("DOR validation target           : PASS")
    print()
    print(
        "Rule: DOR taxpayer counts are an independent "
        "extreme-income-geography proxy, NOT observed IRS millionaire counts."
    )
    print(
        "Rule: DOR payment amounts are diagnostic only "
        "and cannot select the millionaire-count model."
    )
    print(
        "Rule: LD14/19/29 remain a combined disclosure group "
        "and receive NO invented individual DOR counts."
    )

    return df, disclosed


# =============================================================================
# VALIDATION DATASET
# =============================================================================

def build_validation_dataset(
    predictors: pd.DataFrame,
    disclosed_dor: pd.DataFrame,
) -> pd.DataFrame:
    banner("BUILD 46-LD MODEL-VALIDATION DATASET")

    merged = predictors.merge(
        disclosed_dor[
            [
                "ld",
                "taxpayers_with_net_payment",
                "net_payment",
            ]
        ],
        on="ld",
        how="inner",
        validate="one_to_one",
    )

    require(
        len(merged) == EXPECTED_DOR_DISCLOSED_LDS,
        (
            "Validation join did not produce exactly "
            f"{EXPECTED_DOR_DISCLOSED_LDS} rows."
        ),
    )

    expected_missing = {"014", "019", "029"}

    actual_missing = (
        set(predictors["ld"])
        - set(merged["ld"])
    )

    require(
        actual_missing == expected_missing,
        (
            "Validation dataset missing-LD universe differs from "
            "the expected DOR disclosure group 014/019/029."
        ),
    )

    merged = merged.sort_values("ld").reset_index(drop=True)

    print(f"Validation rows                 : {len(merged):,}")
    print(
        "Predictor-only LDs              : "
        + ", ".join(sorted(actual_missing))
    )
    print(
        "DOR taxpayer target total       : "
        f"{merged['taxpayers_with_net_payment'].sum():,.0f}"
    )

    print()
    print("46-LD validation dataset        : PASS")

    return merged


# =============================================================================
# STRICT LEAVE-ONE-OUT CROSS-VALIDATION
# =============================================================================

def run_loocv(
    validation: pd.DataFrame,
    model_id: str,
    predictor_columns: list[str],
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []

    y_all = validation[
        "taxpayers_with_net_payment"
    ].to_numpy(dtype=float)

    for held_out_index in range(len(validation)):
        train_mask = np.ones(
            len(validation),
            dtype=bool,
        )

        train_mask[held_out_index] = False

        X_train = validation.loc[
            train_mask,
            predictor_columns,
        ].to_numpy(dtype=float)

        y_train = y_all[train_mask]

        X_test = validation.loc[
            [held_out_index],
            predictor_columns,
        ].to_numpy(dtype=float)

        beta = fit_ols(
            X_train,
            y_train,
        )

        predicted = float(
            predict_ols(
                beta,
                X_test,
            )[0]
        )

        actual = float(
            y_all[held_out_index]
        )

        error = predicted - actual

        rows.append(
            {
                "model_id": model_id,
                "ld": validation.loc[
                    held_out_index,
                    "ld",
                ],
                "actual_dor_taxpayers": actual,
                "predicted_dor_taxpayers": predicted,
                "signed_error": error,
                "absolute_error": abs(error),
                "squared_error": error ** 2,
                "percent_error": (
                    error / actual
                    if actual != 0
                    else np.nan
                ),
            }
        )

    return pd.DataFrame(rows)


def summarize_model(
    model_id: str,
    predictor_columns: list[str],
    predictions: pd.DataFrame,
) -> dict[str, object]:
    actual = predictions[
        "actual_dor_taxpayers"
    ].to_numpy(dtype=float)

    predicted = predictions[
        "predicted_dor_taxpayers"
    ].to_numpy(dtype=float)

    error = predicted - actual

    mae = float(
        np.mean(np.abs(error))
    )

    rmse = float(
        math.sqrt(np.mean(error ** 2))
    )

    mean_signed_error = float(
        np.mean(error)
    )

    max_abs_error = float(
        np.max(np.abs(error))
    )

    pearson = pearson_corr(
        actual,
        predicted,
    )

    spearman = spearman_corr(
        actual,
        predicted,
    )

    summary: dict[str, object] = {
        "model_id": model_id,
        "predictors": "+".join(predictor_columns),
        "n_validation_lds": len(predictions),
        "loocv_mae": mae,
        "loocv_rmse": rmse,
        "loocv_mean_signed_error": mean_signed_error,
        "loocv_max_abs_error": max_abs_error,
        "loocv_pearson": pearson,
        "loocv_spearman": spearman,
    }

    for ld in sorted(WATCH_LDS):
        row = predictions.loc[
            predictions["ld"].eq(ld)
        ]

        require(
            len(row) == 1,
            f"Missing watch LD {ld} from LOOCV output.",
        )

        summary[
            f"ld{ld}_actual"
        ] = float(
            row.iloc[0]["actual_dor_taxpayers"]
        )

        summary[
            f"ld{ld}_predicted"
        ] = float(
            row.iloc[0]["predicted_dor_taxpayers"]
        )

        summary[
            f"ld{ld}_signed_error"
        ] = float(
            row.iloc[0]["signed_error"]
        )

        summary[
            f"ld{ld}_percent_error"
        ] = float(
            row.iloc[0]["percent_error"]
        )

    return summary


# =============================================================================
# MODEL TOURNAMENT
# =============================================================================

def run_tournament(
    validation: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    banner("STAGE 7A - PREDECLARED MODEL TOURNAMENT")

    print("Primary selection criterion      : strict LOOCV MAE")
    print("Validation target                : DOR TY2022 taxpayer count")
    print("Validation universe              : 46 individually disclosed LDs")
    print("Candidate count                  : 6")
    print()

    all_predictions: list[pd.DataFrame] = []
    summaries: list[dict[str, object]] = []

    for model_id, predictor_columns in MODELS.items():
        for col in predictor_columns:
            require(
                col in validation.columns,
                f"{model_id} missing predictor: {col}",
            )

        predictions = run_loocv(
            validation=validation,
            model_id=model_id,
            predictor_columns=predictor_columns,
        )

        summary = summarize_model(
            model_id=model_id,
            predictor_columns=predictor_columns,
            predictions=predictions,
        )

        all_predictions.append(predictions)
        summaries.append(summary)

    tournament = pd.DataFrame(summaries)

    tournament = tournament.sort_values(
        [
            "loocv_mae",
            "loocv_rmse",
            "model_id",
        ],
        ascending=[
            True,
            True,
            True,
        ],
    ).reset_index(drop=True)

    tournament.insert(
        0,
        "rank_by_mae",
        np.arange(1, len(tournament) + 1),
    )

    predictions = pd.concat(
        all_predictions,
        ignore_index=True,
    )

    print(
        tournament[
            [
                "rank_by_mae",
                "model_id",
                "predictors",
                "loocv_mae",
                "loocv_rmse",
                "loocv_pearson",
                "loocv_spearman",
                "loocv_mean_signed_error",
                "loocv_max_abs_error",
            ]
        ].to_string(
            index=False,
            formatters={
                "loocv_mae": "{:,.3f}".format,
                "loocv_rmse": "{:,.3f}".format,
                "loocv_pearson": "{:.6f}".format,
                "loocv_spearman": "{:.6f}".format,
                "loocv_mean_signed_error": "{:,.3f}".format,
                "loocv_max_abs_error": "{:,.3f}".format,
            },
        )
    )

    print()
    print("WATCH-LD STRICT HOLDOUT RESULTS")
    print("-" * 100)

    watch = predictions[
        predictions["ld"].isin(WATCH_LDS)
    ].copy()

    watch["percent_error_display"] = (
        100.0 * watch["percent_error"]
    )

    watch = watch.merge(
        tournament[
            [
                "model_id",
                "rank_by_mae",
            ]
        ],
        on="model_id",
        how="left",
        validate="many_to_one",
    )

    watch = watch.sort_values(
        [
            "rank_by_mae",
            "ld",
        ]
    )

    print(
        watch[
            [
                "rank_by_mae",
                "model_id",
                "ld",
                "actual_dor_taxpayers",
                "predicted_dor_taxpayers",
                "signed_error",
                "percent_error_display",
            ]
        ].to_string(
            index=False,
            formatters={
                "actual_dor_taxpayers": "{:,.0f}".format,
                "predicted_dor_taxpayers": "{:,.3f}".format,
                "signed_error": "{:+,.3f}".format,
                "percent_error_display": "{:+.2f}%".format,
            },
        )
    )

    return tournament, predictions


# =============================================================================
# OUTPUTS
# =============================================================================

def write_outputs(
    validation: pd.DataFrame,
    tournament: pd.DataFrame,
    predictions: pd.DataFrame,
) -> None:
    banner("WRITE STAGE 7A ARTIFACTS")

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    validation.to_csv(
        JOINED_OUTPUT,
        index=False,
    )

    tournament.to_csv(
        TOURNAMENT_OUTPUT,
        index=False,
    )

    predictions.to_csv(
        LOOCV_OUTPUT,
        index=False,
    )

    for path in [
        JOINED_OUTPUT,
        TOURNAMENT_OUTPUT,
        LOOCV_OUTPUT,
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
        "MILLIONAIRE TAX LD MODEL - STAGE 7A MODEL TOURNAMENT"
    )

    print("READ ONLY WITH RESPECT TO SOURCE DATA")
    print("NO DATABASE WRITES")
    print("NO STATEWIDE MILLIONAIRE CALIBRATION")
    print("NO HISTORICAL LD MILLIONAIRE INPUTS")
    print()
    print(
        "PURPOSE: Compare a frozen, predeclared set of candidate "
        "models against independent DOR TY2022 extreme-income geography."
    )

    validate_hashes()

    predictors = read_predictors()
    _, disclosed_dor = read_dor()

    validation = build_validation_dataset(
        predictors=predictors,
        disclosed_dor=disclosed_dor,
    )

    tournament, predictions = run_tournament(
        validation=validation,
    )

    write_outputs(
        validation=validation,
        tournament=tournament,
        predictions=predictions,
    )

    banner("STAGE 7A COMPLETE")

    winner = tournament.iloc[0]

    print(
        f"Primary LOOCV-MAE winner         : "
        f"{winner['model_id']}"
    )
    print(
        f"Winner predictors                : "
        f"{winner['predictors']}"
    )
    print(
        f"Winner LOOCV MAE                 : "
        f"{winner['loocv_mae']:,.3f}"
    )
    print()
    print("INTERPRETATION RULES")
    print("-" * 100)
    print(
        "1. DOR capital-gains taxpayer counts are an independent "
        "extreme-income-geography proxy, not observed IRS $1M+ counts."
    )
    print(
        "2. Primary model selection is determined solely by strict "
        "LOOCV MAE across the 46 individually disclosed LDs."
    )
    print(
        "3. DOR payment dollars are diagnostic only and do not "
        "select the model."
    )
    print(
        "4. LD14/19/29 remain jointly disclosed by DOR and receive "
        "no invented validation targets."
    )
    print(
        "5. Historical LD millionaire estimates and legacy "
        "millionaire-model outputs are prohibited inputs."
    )
    print(
        "6. No statewide 21,530-millionaire calibration occurs "
        "in Stage 7A."
    )
    print(
        "7. The Stage 7A winner is a geographic model candidate; "
        "Stage 7B will separately fit the frozen winner and "
        "reconcile the resulting 49-LD distribution to the "
        "authoritative IRS statewide $1M+ return control."
    )


if __name__ == "__main__":
    main()