"""
Millionaire Tax Incidence v0.2
Stage 9C - Freeze Excess-AGI Methodology and Limitations

Purpose
-------
Close the legislative-district millionaire-AGI modeling stage.

Stage 9C performs NO new statistical modeling and NO new allocation.

It records the methodological conclusion reached from Stages 9A and 9B:

1. Statewide IRS millionaire-return and millionaire-AGI controls are
   authoritative inputs.

2. Millionaire Geography v0.2 is the principal estimate of the
   distribution of millionaire returns among Washington's 49
   legislative districts.

3. Available public data do not provide an observed 49-LD millionaire
   AGI answer key sufficient to select a single preferred LD AGI model.

4. Stage 9B therefore remains a sensitivity analysis consisting of
   seven predeclared excess-AGI allocation scenarios.

5. No Stage 9B scenario is selected as the preferred or "true"
   legislative-district millionaire-AGI estimate.

6. Any downstream legislative-district dollar-incidence estimate that
   uses modeled millionaire AGI inherits this allocation uncertainty.

No historical LD millionaire estimates are used.
No model is fit.
No candidate is selected.
No database writes occur.
"""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]

BASE = (
    ROOT
    / "data"
    / "processed"
    / "validation"
    / "millionaire_excess_agi_v0_2"
)

STAGE9A_PATH = (
    BASE
    / "stage9a_cd_geographic_reliability_screen.csv"
)

STAGE9B_DETAIL_PATH = (
    BASE
    / "stage9b_excess_agi_sensitivity_by_ld.csv"
)

STAGE9B_SUMMARY_PATH = (
    BASE
    / "stage9b_excess_agi_sensitivity_summary.csv"
)

STAGE9B_PAIRWISE_PATH = (
    BASE
    / "stage9b_candidate_pairwise_comparison.csv"
)

OUTPUT_PATH = (
    BASE
    / "stage9c_methodology_record.txt"
)


EXPECTED_HASHES = {
    STAGE9A_PATH:
        "95bd31ca576f3aeedbe195714c8b67e237e25de6a1246015a97c7c1bcdc72105",

    STAGE9B_DETAIL_PATH:
        "393372c1e54b6dcc7e13dabf25100148306829b022281cd4addc87e4b776d66e",

    STAGE9B_SUMMARY_PATH:
        "76c660ba279229f1e4f9a95d4994d9b152f17ba2503fa61aaaf9535b3168b79f",

    STAGE9B_PAIRWISE_PATH:
        "86a65dc30aada1b092de37aa8c996603618fcd14d7f8f6343e2939b68d8ec165",
}


STATEWIDE_MILLIONAIRE_RETURNS = 21_530
STATEWIDE_MILLIONAIRE_AGI = 65_956_796_000
STATEWIDE_FLOOR_AGI = 21_530_000_000
STATEWIDE_EXCESS_AGI = 44_426_796_000


CANDIDATES = [
    "E0_COUNT",
    "E1_AGI",
    "E2_BUSINESS",
    "E3_PENSION",
    "E4_COUNT_AGI_GM",
    "E5_COUNT_AGI_BUSINESS_GM",
    "E6_COUNT_AGI_BUSINESS_PENSION_GM",
]


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


def csv_row_count(path: Path) -> int:
    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as f:
        reader = csv.reader(f)
        next(reader)

        return sum(
            1
            for _ in reader
        )


def verify_inputs() -> None:

    banner("VERIFY FROZEN STAGE 9 INPUTS")

    for path, expected_hash in EXPECTED_HASHES.items():

        require(
            path.exists(),
            f"Missing frozen artifact: {path}",
        )

        observed_hash = sha256_file(path)

        print(
            f"{path.name}"
        )

        print(
            f"  observed : {observed_hash}"
        )

        print(
            f"  expected : {expected_hash}"
        )

        require(
            observed_hash.lower()
            == expected_hash.lower(),
            f"Hash mismatch: {path.name}",
        )

        print(
            "  status   : PASS"
        )

        print()


def verify_structure() -> None:

    banner("VERIFY STAGE 9 STRUCTURE")

    stage9a_rows = csv_row_count(
        STAGE9A_PATH
    )

    detail_rows = csv_row_count(
        STAGE9B_DETAIL_PATH
    )

    summary_rows = csv_row_count(
        STAGE9B_SUMMARY_PATH
    )

    pairwise_rows = csv_row_count(
        STAGE9B_PAIRWISE_PATH
    )

    print(
        f"Stage 9A variables              : {stage9a_rows}"
    )

    print(
        f"Stage 9B LD rows                : {detail_rows}"
    )

    print(
        f"Stage 9B scenarios              : {summary_rows}"
    )

    print(
        f"Stage 9B pairwise comparisons   : {pairwise_rows}"
    )

    require(
        stage9a_rows == 7,
        "Expected 7 Stage 9A variables.",
    )

    require(
        detail_rows == 49,
        "Expected 49 Stage 9B LD rows.",
    )

    require(
        summary_rows == 7,
        "Expected 7 Stage 9B scenarios.",
    )

    require(
        pairwise_rows == 21,
        "Expected 21 pairwise comparisons.",
    )

    print()
    print("Stage 9 structural validation   : PASS")


def build_methodology_record() -> str:

    lines = [
        "=" * 100,
        "MILLIONAIRE TAX INCIDENCE v0.2 - STAGE 9 METHODOLOGY FREEZE",
        "=" * 100,
        "",
        "STATUS",
        "------",
        "",
        "Stage 9 is CLOSED.",
        "",
        "No preferred legislative-district millionaire-AGI model was selected.",
        "",
        "",
        "AUTHORITATIVE STATEWIDE CONTROLS",
        "--------------------------------",
        "",
        f"TY2022 millionaire returns      : {STATEWIDE_MILLIONAIRE_RETURNS:,}",
        f"TY2022 millionaire AGI          : ${STATEWIDE_MILLIONAIRE_AGI:,}",
        f"First-$1M floor AGI             : ${STATEWIDE_FLOOR_AGI:,}",
        f"Excess AGI                      : ${STATEWIDE_EXCESS_AGI:,}",
        "",
        "",
        "EVIDENCE HIERARCHY",
        "------------------",
        "",
        "1. STATEWIDE IRS CONTROLS",
        "",
        "   The statewide number of millionaire returns and aggregate",
        "   millionaire AGI are authoritative IRS controls.",
        "",
        "2. MILLIONAIRE GEOGRAPHY v0.2",
        "",
        "   The 49-LD distribution of millionaire returns is the principal",
        "   modeled geographic result.",
        "",
        "   It was constructed from independently allocated IRS ZIP data,",
        "   selected through predeclared out-of-sample validation against",
        "   independent Washington DOR capital-gains taxpayer geography,",
        "   and reconciled exactly to the statewide IRS millionaire-return",
        "   control.",
        "",
        "3. LEGISLATIVE-DISTRICT MILLIONAIRE AGI",
        "",
        "   Legislative-district millionaire AGI is materially less",
        "   identified by available public data.",
        "",
        "   No observed 49-LD millionaire-AGI answer key is available for",
        "   direct model fitting or independent model selection.",
        "",
        "   Stage 9 therefore does not designate a single preferred",
        "   legislative-district millionaire-AGI estimate.",
        "",
        "",
        "STAGE 9A FINDING",
        "----------------",
        "",
        "Congressional-district validation identified three IRS upper-tail",
        "dollar variables with HIGH geographic reliability:",
        "",
        "   A00100 - Adjusted gross income",
        "   A00900 - Business/profession net income",
        "   A01700 - Taxable pensions and annuities",
        "",
        "No variables were classified MODERATE.",
        "",
        "The following were classified LOW for geographic transportability:",
        "",
        "   A00300 - Taxable interest",
        "   A00600 - Ordinary dividends",
        "   A01000 - Net capital gain",
        "   A26270 - Partnership/S-corporation net income",
        "",
        "",
        "STAGE 9B FINDING",
        "----------------",
        "",
        "Seven predeclared excess-AGI allocation scenarios were retained:",
        "",
    ]

    for candidate in CANDIDATES:
        lines.append(
            f"   {candidate}"
        )

    lines.extend(
        [
            "",
            "Every scenario reconciles independently to the same statewide",
            f"excess-AGI control of ${STATEWIDE_EXCESS_AGI:,}.",
            "",
            "The scenarios show strong broad geographic agreement but",
            "material dollar uncertainty for some individual districts.",
            "",
            "Accordingly, Stage 9B is retained as a SENSITIVITY ANALYSIS.",
            "",
            "No E0-E6 scenario is designated the preferred, correct,",
            "best-fitting, or true LD millionaire-AGI distribution.",
            "",
            "",
            "DOWNSTREAM USE POLICY",
            "---------------------",
            "",
            "Millionaire-count geography may be used as the principal",
            "49-LD estimate, subject to its documented modeling limitations.",
            "",
            "LD millionaire-AGI values must be described as modeled",
            "sensitivity scenarios rather than observed values.",
            "",
            "Any downstream tax-dollar or dollar-incidence estimate based",
            "on LD millionaire AGI inherits Stage 9B allocation uncertainty.",
            "",
            "Where a single illustrative AGI scenario is displayed for",
            "communication purposes, it must be explicitly labeled",
            "illustrative and must not be described as empirically selected",
            "unless new independent validation evidence is obtained.",
            "",
            "For uncertainty-sensitive reporting, the E0-E6 range or",
            "scenario envelope is preferred to false point precision.",
            "",
            "",
            "PROVENANCE FIREWALL",
            "-------------------",
            "",
            "Historical legislative-district millionaire estimates did not",
            "enter Stage 9 predictor construction, validation, allocation,",
            "scenario construction, or methodological closure.",
            "",
            "Stage 9C performs no model fitting, no scenario selection,",
            "no new geographic allocation, and no database writes.",
            "",
            "",
            "REOPENING RULE",
            "--------------",
            "",
            "Stage 9 should be reopened only if materially new independent",
            "evidence becomes available that can identify or validate",
            "legislative-district millionaire AGI geography.",
            "",
            "Additional model complexity alone is not sufficient reason",
            "to reopen Stage 9.",
            "",
            "",
            "FINAL STATUS",
            "------------",
            "",
            "STAGE 9 FROZEN.",
            "",
        ]
    )

    return "\n".join(lines)


def main() -> None:

    banner(
        "MILLIONAIRE TAX INCIDENCE v0.2 - "
        "STAGE 9C METHODOLOGY FREEZE"
    )

    print("NO MODEL FITTING")
    print("NO SCENARIO SELECTION")
    print("NO NEW ALLOCATION")
    print("NO HISTORICAL LD MILLIONAIRE INPUTS")
    print("NO DATABASE WRITES")

    verify_inputs()

    verify_structure()

    banner("WRITE METHODOLOGY RECORD")

    record = build_methodology_record()

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        record,
        encoding="utf-8",
    )

    print(
        f"Output                           : "
        f"{OUTPUT_PATH.relative_to(ROOT)}"
    )

    print(
        f"SHA-256                          : "
        f"{sha256_file(OUTPUT_PATH)}"
    )

    banner("FROZEN METHODOLOGY RECORD")

    print(record)

    banner("STAGE 9C COMPLETE")

    print(
        "Stage 9 is closed."
    )

    print(
        "No preferred LD millionaire-AGI model has been selected."
    )

    print(
        "Future dollar-incidence reporting must preserve "
        "the documented Stage 9B uncertainty."
    )


if __name__ == "__main__":
    main()