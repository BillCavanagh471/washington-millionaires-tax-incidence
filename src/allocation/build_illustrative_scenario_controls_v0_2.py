"""
Build FY2029/FY2030 illustrative scenario controls v0.2.

Changes from v0.1
-----------------
1. Resolves Fair Start for the illustrative geographic-incidence model.
2. Uses a same-fiscal-year-equivalent Fair Start amount equal to 5% of
   Millionaires Tax receipts for the selected scenario year.
3. Adds total geographically modeled illustrative benefits.
4. Adds the difference between Millionaires Tax receipts and modeled benefits.

IMPORTANT
---------
The Fair Start calculation in this model is an ILLUSTRATIVE FY-EQUIVALENT
normalization. It is NOT a representation of the Treasurer's literal
cash-transfer timing.

The statutory Fair Start transfer is based on prior-fiscal-year receipts.
The same-FY convention is used here so FY2029 and FY2030 can be compared
as geographic-incidence scenarios on a common basis.

Illustrative benefit pools are modeling assumptions, not forecasts of
appropriations, and are not forced to equal Millionaires Tax receipts.

Source for official controls
----------------------------
Final Department of Revenue fiscal note:
ESSB 6346 E S SB PL
Request 6346-11-2
"""

from pathlib import Path
import csv


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

OUTPUT_DIR = Path("data/processed/model")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = (
    OUTPUT_DIR / "illustrative_scenario_controls_v0_2.csv"
)


# ---------------------------------------------------------------------------
# Official DOR fiscal controls
# ---------------------------------------------------------------------------

DOR_CONTROLS = {
    2029: {
        "millionaires_tax_receipts": 2_698_000_000,
        "sales_tax_effect": -376_852_000,
        "bo_tax_effect": 32_200_000,
    },
    2030: {
        "millionaires_tax_receipts": 3_732_000_000,
        "sales_tax_effect": -853_735_000,
        "bo_tax_effect": 24_000_000,
    },
}


# ---------------------------------------------------------------------------
# Illustrative benefit assumptions
#
# These are scenario assumptions, NOT official appropriations.
# They remain constant between FY2029 and FY2030 in v0.2.
# ---------------------------------------------------------------------------

ILLUSTRATIVE_BENEFIT_POOLS = {
    "wftc": 250_000_000,
    "k12": 1_000_000_000,
    "health_human_services": 750_000_000,
    "higher_education": 400_000_000,
}


# ---------------------------------------------------------------------------
# Fair Start
#
# Statutory rate = 5%.
#
# MODEL CONVENTION:
# For geographic-incidence comparison, v0.2 calculates an illustrative
# same-FY-equivalent amount:
#
#     scenario-year Millionaires Tax receipts * 5%
#
# This is deliberately NOT labeled as the literal statutory cash transfer.
# ---------------------------------------------------------------------------

FAIR_START_RATE = 0.05

FAIR_START_MODEL_METHOD = (
    "ILLUSTRATIVE_SAME_FY_EQUIVALENT"
)

FAIR_START_TIMING_NOTE = (
    "Modeled as 5% of same-scenario-FY Millionaires Tax receipts for "
    "geographic comparison; statutory cash-transfer timing is based on "
    "prior-fiscal-year receipts."
)


def money(value):
    """Format dollar values for console output."""
    return f"${value:,.2f}"


def build_rows():
    rows = []

    base_benefit_total = sum(
        ILLUSTRATIVE_BENEFIT_POOLS.values()
    )

    for fiscal_year in sorted(DOR_CONTROLS):
        official = DOR_CONTROLS[fiscal_year]

        receipts = official["millionaires_tax_receipts"]

        fair_start_amount = receipts * FAIR_START_RATE

        modeled_benefit_total = (
            base_benefit_total
            + fair_start_amount
        )

        unallocated_difference = (
            receipts
            - modeled_benefit_total
        )

        net_non_income_tax_effect = (
            official["sales_tax_effect"]
            + official["bo_tax_effect"]
        )

        rows.append(
            {
                "scenario_fy": fiscal_year,

                # Official DOR controls
                "millionaires_tax_receipts":
                    receipts,
                "sales_tax_effect":
                    official["sales_tax_effect"],
                "bo_tax_effect":
                    official["bo_tax_effect"],
                "net_non_income_tax_effect":
                    net_non_income_tax_effect,

                # Illustrative benefit assumptions
                "wftc_pool":
                    ILLUSTRATIVE_BENEFIT_POOLS["wftc"],
                "k12_pool":
                    ILLUSTRATIVE_BENEFIT_POOLS["k12"],
                "health_human_services_pool":
                    ILLUSTRATIVE_BENEFIT_POOLS[
                        "health_human_services"
                    ],
                "higher_education_pool":
                    ILLUSTRATIVE_BENEFIT_POOLS[
                        "higher_education"
                    ],

                "illustrative_benefits_excl_fair_start":
                    base_benefit_total,

                # Fair Start
                "fair_start_rate":
                    FAIR_START_RATE,
                "fair_start_modeled_amount":
                    fair_start_amount,
                "fair_start_model_method":
                    FAIR_START_MODEL_METHOD,
                "fair_start_timing_note":
                    FAIR_START_TIMING_NOTE,

                # Scenario accounting
                "modeled_benefit_total":
                    modeled_benefit_total,
                "unallocated_difference":
                    unallocated_difference,

                # Provenance / semantic controls
                "official_control_source":
                    (
                        "Final DOR fiscal note ESSB 6346 "
                        "E S SB PL Request 6346-11-2"
                    ),
                "benefit_pool_status":
                    "ILLUSTRATIVE_ASSUMPTION",
                "scenario_status":
                    "ILLUSTRATIVE_NOT_FORECAST",
            }
        )

    return rows


def validate(rows):
    """Fail loudly if core controls or calculations drift."""

    assert len(rows) == 2

    by_year = {
        row["scenario_fy"]: row
        for row in rows
    }

    # ------------------------------------------------------------------
    # Official controls
    # ------------------------------------------------------------------

    assert (
        by_year[2029]["millionaires_tax_receipts"]
        == 2_698_000_000
    )
    assert (
        by_year[2030]["millionaires_tax_receipts"]
        == 3_732_000_000
    )

    assert (
        by_year[2029]["sales_tax_effect"]
        == -376_852_000
    )
    assert (
        by_year[2030]["sales_tax_effect"]
        == -853_735_000
    )

    assert (
        by_year[2029]["bo_tax_effect"]
        == 32_200_000
    )
    assert (
        by_year[2030]["bo_tax_effect"]
        == 24_000_000
    )

    assert (
        by_year[2029]["net_non_income_tax_effect"]
        == -344_652_000
    )
    assert (
        by_year[2030]["net_non_income_tax_effect"]
        == -829_735_000
    )

    # ------------------------------------------------------------------
    # Base illustrative pools
    # ------------------------------------------------------------------

    for row in rows:
        assert (
            row["illustrative_benefits_excl_fair_start"]
            == 2_400_000_000
        )

    # ------------------------------------------------------------------
    # Fair Start
    # ------------------------------------------------------------------

    assert (
        by_year[2029]["fair_start_modeled_amount"]
        == 134_900_000
    )

    assert (
        by_year[2030]["fair_start_modeled_amount"]
        == 186_600_000
    )

    # ------------------------------------------------------------------
    # Total modeled benefits
    # ------------------------------------------------------------------

    assert (
        by_year[2029]["modeled_benefit_total"]
        == 2_534_900_000
    )

    assert (
        by_year[2030]["modeled_benefit_total"]
        == 2_586_600_000
    )

    # ------------------------------------------------------------------
    # Unallocated difference
    # ------------------------------------------------------------------

    assert (
        by_year[2029]["unallocated_difference"]
        == 163_100_000
    )

    assert (
        by_year[2030]["unallocated_difference"]
        == 1_145_400_000
    )

    # ------------------------------------------------------------------
    # Accounting identities
    # ------------------------------------------------------------------

    for row in rows:
        reconstructed_receipts = (
            row["modeled_benefit_total"]
            + row["unallocated_difference"]
        )

        assert (
            reconstructed_receipts
            == row["millionaires_tax_receipts"]
        )


def write_csv(rows):
    fieldnames = [
        "scenario_fy",

        "millionaires_tax_receipts",
        "sales_tax_effect",
        "bo_tax_effect",
        "net_non_income_tax_effect",

        "wftc_pool",
        "k12_pool",
        "health_human_services_pool",
        "higher_education_pool",
        "illustrative_benefits_excl_fair_start",

        "fair_start_rate",
        "fair_start_modeled_amount",
        "fair_start_model_method",
        "fair_start_timing_note",

        "modeled_benefit_total",
        "unallocated_difference",

        "official_control_source",
        "benefit_pool_status",
        "scenario_status",
    ]

    with OUTPUT_FILE.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
        )
        writer.writeheader()
        writer.writerows(rows)


def print_report(rows):
    print()
    print(
        "ESSB 6346 ILLUSTRATIVE SCENARIO CONTROLS v0.2"
    )
    print("=" * 80)

    for row in rows:
        fy = row["scenario_fy"]

        print()
        print(f"FY{fy}")
        print("-" * 80)

        print("OFFICIAL DOR CASH-RECEIPT CONTROLS")
        print(
            f"Millionaires Tax receipts      : "
            f"{money(row['millionaires_tax_receipts'])}"
        )
        print(
            f"Retail sales tax effect        : "
            f"{money(row['sales_tax_effect'])}"
        )
        print(
            f"B&O tax effect                 : "
            f"{money(row['bo_tax_effect'])}"
        )
        print(
            f"Net non-income-tax effect      : "
            f"{money(row['net_non_income_tax_effect'])}"
        )

        print()
        print("ILLUSTRATIVE BENEFIT POOLS")
        print(
            f"WFTC                            : "
            f"{money(row['wftc_pool'])}"
        )
        print(
            f"K-12                            : "
            f"{money(row['k12_pool'])}"
        )
        print(
            f"Health / human services        : "
            f"{money(row['health_human_services_pool'])}"
        )
        print(
            f"Higher education                : "
            f"{money(row['higher_education_pool'])}"
        )
        print(
            f"Subtotal before Fair Start      : "
            f"{money(row['illustrative_benefits_excl_fair_start'])}"
        )

        print()
        print("FAIR START")
        print(
            f"Illustrative FY-equivalent rate : "
            f"{row['fair_start_rate']:.1%}"
        )
        print(
            f"Illustrative Fair Start amount  : "
            f"{money(row['fair_start_modeled_amount'])}"
        )
        print(
            f"Method                          : "
            f"{row['fair_start_model_method']}"
        )

        print()
        print("SCENARIO ACCOUNTING")
        print(
            f"Modeled benefit total           : "
            f"{money(row['modeled_benefit_total'])}"
        )
        print(
            f"Unallocated difference          : "
            f"{money(row['unallocated_difference'])}"
        )
        print(
            f"Millionaires Tax control        : "
            f"{money(row['millionaires_tax_receipts'])}"
        )

    print()
    print("IMPORTANT")
    print("-" * 80)
    print(
        "Fair Start is modeled as 5% of same-scenario-year Millionaires "
        "Tax receipts for geographic-incidence comparison."
    )
    print(
        "This is an illustrative FY-equivalent normalization and is NOT "
        "the literal statutory cash-transfer timing."
    )
    print(
        "The statutory transfer remains based on prior-fiscal-year "
        "Millionaires Tax receipts."
    )
    print(
        "The remaining difference between modeled benefits and receipts "
        "is preserved as UNALLOCATED; no geographic incidence is "
        "manufactured for it."
    )

    print()
    print("OUTPUT")
    print("-" * 80)
    print(OUTPUT_FILE)


def main():
    rows = build_rows()
    validate(rows)
    write_csv(rows)
    print_report(rows)


if __name__ == "__main__":
    main()