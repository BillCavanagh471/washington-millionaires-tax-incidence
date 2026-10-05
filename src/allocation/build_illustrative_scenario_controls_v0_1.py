"""
Build FY2029/FY2030 illustrative scenario controls v0.1.

Purpose
-------
Create a compact, year-aware control table for the Washington Millionaires
Tax geographic-incidence model.

This script deliberately separates:

    1. Official DOR fiscal controls
    2. Illustrative benefit-pool assumptions
    3. Statutory/model components whose treatment remains unresolved

No legislative-district allocation is performed here.

IMPORTANT
---------
The illustrative benefit pools are modeling assumptions. They are NOT
forecasts of FY2029 or FY2030 appropriations and are NOT forced to equal
Millionaires Tax receipts.

Fair Start is preserved as unresolved in this version because the statutory
transfer is based on prior-fiscal-year receipts, while this project may also
want an FY-equivalent geographic-incidence scenario.

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

OUTPUT_FILE = OUTPUT_DIR / "illustrative_scenario_controls_v0_1.csv"


# ---------------------------------------------------------------------------
# Official DOR fiscal controls
#
# Dollar values are annual cash-receipt effects from the final DOR
# ten-year fiscal analysis.
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
#
# For v0.1 they are intentionally held constant between FY2029 and FY2030.
# Later versions may introduce year-specific assumptions, but only when
# explicitly justified.
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
# DO NOT calculate the final modeled value yet.
#
# The statute uses a transfer tied to prior-fiscal-year Millionaires Tax
# receipts. The geographic-incidence model may ultimately use either:
#
#   A. literal statutory cash-flow treatment, or
#   B. an explicitly labeled FY-equivalent illustrative treatment.
#
# v0.1 therefore preserves the component without choosing between them.
# ---------------------------------------------------------------------------

FAIR_START_RATE = 0.05
FAIR_START_STATUS = "UNRESOLVED_TIMING_TREATMENT"


def money(value):
    """Format numeric dollar values for console output."""
    if value is None:
        return "TBD"
    return f"${value:,.2f}"


def build_rows():
    rows = []

    for fiscal_year in sorted(DOR_CONTROLS):
        official = DOR_CONTROLS[fiscal_year]

        illustrative_total_excluding_fair_start = sum(
            ILLUSTRATIVE_BENEFIT_POOLS.values()
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
                    official["millionaires_tax_receipts"],
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
                    illustrative_total_excluding_fair_start,

                # Fair Start remains unresolved
                "fair_start_rate":
                    FAIR_START_RATE,
                "fair_start_modeled_amount":
                    None,
                "fair_start_status":
                    FAIR_START_STATUS,

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
    """Fail loudly if any core controls have drifted."""

    assert len(rows) == 2

    by_year = {row["scenario_fy"]: row for row in rows}

    # Official DOR controls
    assert by_year[2029]["millionaires_tax_receipts"] == 2_698_000_000
    assert by_year[2030]["millionaires_tax_receipts"] == 3_732_000_000

    assert by_year[2029]["sales_tax_effect"] == -376_852_000
    assert by_year[2030]["sales_tax_effect"] == -853_735_000

    assert by_year[2029]["bo_tax_effect"] == 32_200_000
    assert by_year[2030]["bo_tax_effect"] == 24_000_000

    # Net non-income-tax effects
    assert by_year[2029]["net_non_income_tax_effect"] == -344_652_000
    assert by_year[2030]["net_non_income_tax_effect"] == -829_735_000

    # Illustrative pools
    expected_benefit_total = 2_400_000_000

    for row in rows:
        assert (
            row["illustrative_benefits_excl_fair_start"]
            == expected_benefit_total
        )

        # Fair Start MUST remain unresolved in v0.1
        assert row["fair_start_modeled_amount"] is None
        assert row["fair_start_status"] == FAIR_START_STATUS


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
        "fair_start_status",

        "official_control_source",
        "benefit_pool_status",
        "scenario_status",
    ]

    with OUTPUT_FILE.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def print_report(rows):
    print()
    print("ESSB 6346 ILLUSTRATIVE SCENARIO CONTROLS v0.1")
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
            f"Total excluding Fair Start      : "
            f"{money(row['illustrative_benefits_excl_fair_start'])}"
        )

        print()
        print("FAIR START")
        print(
            f"Statutory rate                  : "
            f"{row['fair_start_rate']:.1%}"
        )
        print(
            f"Modeled amount                  : "
            f"{money(row['fair_start_modeled_amount'])}"
        )
        print(
            f"Status                          : "
            f"{row['fair_start_status']}"
        )

    print()
    print("IMPORTANT")
    print("-" * 80)
    print(
        "Official DOR cash-receipt controls and illustrative benefit pools "
        "are intentionally kept separate."
    )
    print(
        "The $2.400B illustrative benefit total is NOT forced to equal "
        "Millionaires Tax receipts."
    )
    print(
        "Sales-tax and B&O effects are preserved as fiscal controls and "
        "are NOT automatically treated as geographically allocated benefits."
    )
    print(
        "Fair Start remains unresolved pending an explicit decision on "
        "statutory cash-flow versus FY-equivalent illustrative treatment."
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