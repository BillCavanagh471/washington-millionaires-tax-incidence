from pathlib import Path
import csv


OUTPUT_DIR = Path("data/processed/model")

OUTPUT = (
    OUTPUT_DIR
    / "tax_relief_control_v0_1.csv"
)


# ------------------------------------------------------------
# Official final DOR fiscal-note controls.
#
# Source:
# ESSB 6346, Department of Revenue,
# final "PL" fiscal note, request 6346-11-2.
#
# Parentheses in the fiscal note are represented here as
# negative revenue effects.
# ------------------------------------------------------------

ROWS = [
    {
        "category": "millionaires_tax",
        "account": "GF-State",
        "tax_type": "New millionaire tax",
        "fy2027": 0,
        "fy2027_29": 2_698_000_000,
        "fy2029_31": 6_899_000_000,
        "incidence_class": "tax_source",
        "model_status": "control",
    },

    {
        "category": "retail_sales_tax",
        "account": "GF-State",
        "tax_type": "Retail sales tax",
        "fy2027": -48_700_000,
        "fy2027_29": -423_120_000,
        "fy2029_31": -1_708_090_000,
        "incidence_class": "mixed_tax_relief",
        "model_status": "requires_decomposition",
    },

    {
        "category": "bo_tax",
        "account": "GF-State",
        "tax_type": "Business and occupation tax",
        "fy2027": 1_100_000,
        "fy2027_29": -13_600_000,
        "fy2029_31": -50_800_000,
        "incidence_class": "business_tax_change",
        "model_status": "requires_decomposition",
    },

    {
        "category": "retail_sales_tax",
        "account": "Multimodal Transportation Account",
        "tax_type": "Retail sales tax",
        "fy2027": 0,
        "fy2027_29": -7_467_000,
        "fy2029_31": -26_730_000,
        "incidence_class": "mixed_tax_relief",
        "model_status": "requires_decomposition",
    },

    {
        "category": "bo_tax",
        "account": "Workforce Education Investment Account",
        "tax_type": "Business and occupation tax",
        "fy2027": 1_200_000,
        "fy2027_29": 47_900_000,
        "fy2029_31": 232_000_000,
        "incidence_class": "business_tax_change",
        "model_status": "requires_decomposition",
    },

    {
        "category": "retail_sales_tax",
        "account": "Performance Audits of Government Account",
        "tax_type": "Retail sales tax",
        "fy2027": -78_000,
        "fy2027_29": -703_000,
        "fy2029_31": -2_751_000,
        "incidence_class": "mixed_tax_relief",
        "model_status": "requires_decomposition",
    },
]


def money(value):
    return f"${value:,.2f}"


def main():

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    fieldnames = [
        "category",
        "account",
        "tax_type",
        "fy2027",
        "fy2027_29",
        "fy2029_31",
        "incidence_class",
        "model_status",
    ]

    with OUTPUT.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(ROWS)

    print(
        "ESSB 6346 TAX RELIEF CONTROL v0.1"
    )
    print("=" * 80)

    print()
    print(
        "Source: Final Department of Revenue "
        "fiscal note, ESSB 6346 E S SB PL, "
        "Request 6346-11-2"
    )

    print()
    print("2029-31 OFFICIAL CASH-RECEIPT EFFECTS")
    print("-" * 80)

    for row in ROWS:

        print(
            f"{row['account']:<42} "
            f"{row['tax_type']:<28} "
            f"{money(row['fy2029_31']):>20}"
        )

    millionaire_tax = next(
        row["fy2029_31"]
        for row in ROWS
        if row["category"] == "millionaires_tax"
    )

    gf_sales = next(
        row["fy2029_31"]
        for row in ROWS
        if (
            row["category"] == "retail_sales_tax"
            and row["account"] == "GF-State"
        )
    )

    gf_bo = next(
        row["fy2029_31"]
        for row in ROWS
        if (
            row["category"] == "bo_tax"
            and row["account"] == "GF-State"
        )
    )

    print()
    print("REFERENCE CALCULATIONS")
    print("-" * 80)

    print(
        f"Millionaire-tax 2029-31 control : "
        f"{money(millionaire_tax)}"
    )

    print(
        f"Simple two-year annual average  : "
        f"{money(millionaire_tax / 2)}"
    )

    print(
        f"GF sales-tax 2029-31 effect     : "
        f"{money(gf_sales)}"
    )

    print(
        f"GF B&O 2029-31 effect           : "
        f"{money(gf_bo)}"
    )

    print()
    print("IMPORTANT")
    print("-" * 80)

    print(
        "Do not treat the 2029-31 aggregate "
        "tax-relief effects as a uniform annual "
        "allocation."
    )

    print(
        "The underlying provisions have different "
        "effective dates and different beneficiary "
        "populations."
    )

    print(
        "Next step: extract annual provision-level "
        "DOR estimates from the final ten-year "
        "analysis."
    )

    print()
    print("OUTPUT")
    print("-" * 80)
    print(OUTPUT)


if __name__ == "__main__":
    main()