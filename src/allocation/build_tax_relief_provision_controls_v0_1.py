from pathlib import Path
import csv


OUTPUT_DIR = Path("data/processed/model")

PROVISION_OUTPUT = (
    OUTPUT_DIR
    / "tax_relief_provision_controls_v0_1.csv"
)

ANNUAL_OUTPUT = (
    OUTPUT_DIR
    / "tax_relief_dor_annual_controls_v0_1.csv"
)


# ============================================================
# PROVISION INVENTORY
#
# Source:
# ESSB 6346 E S SB PL
# Department of Revenue final fiscal note
# Request 6346-11-2
#
# IMPORTANT:
# DOR describes these provisions individually but does NOT
# provide a separate annual dollar estimate for every provision.
# Do not manufacture a provision-level dollar split.
# ============================================================

PROVISIONS = [
    {
        "provision_id": "WFTC_EXPANSION",
        "sections": "901-902",
        "description": (
            "Working Families Tax Credit eligibility expansion"
        ),
        "effective_date": "2029-01-01",
        "tax_family": "WFTC",
        "incidence_family": "household_income",
        "dor_dollar_status": "no_DOR_tax_revenue_impact",
        "geographic_status": "modeled_separately",
        "proxy_candidate": "WFTC LD allocation v0.2",
        "notes": (
            "Existing illustrative WFTC pool is modeled "
            "separately; do not double count."
        ),
    },

    {
        "provision_id": "GROOMING_HYGIENE",
        "sections": "903-905",
        "description": (
            "Sales and use tax exemption for grooming "
            "and hygiene products"
        ),
        "effective_date": "2029-01-01",
        "tax_family": "sales_use_tax",
        "incidence_family": "household_consumption",
        "dor_dollar_status": "embedded_in_aggregate",
        "geographic_status": "candidate",
        "proxy_candidate": "population_or_households",
        "notes": (
            "Broad household consumption category."
        ),
    },

    {
        "provision_id": "DIAPERS",
        "sections": "906",
        "description": (
            "Sales and use tax exemption for diapers"
        ),
        "effective_date": "2029-01-01",
        "tax_family": "sales_use_tax",
        "incidence_family": "household_consumption",
        "dor_dollar_status": "embedded_in_aggregate",
        "geographic_status": "candidate",
        "proxy_candidate": (
            "children_under_5_with_adjustment_if_desired"
        ),
        "notes": (
            "Definition also includes diapers used by "
            "people with bladder or bowel-control difficulty; "
            "under-5 population alone would therefore be "
            "an incomplete proxy."
        ),
    },

    {
        "provision_id": "OTC_DRUGS",
        "sections": "907-908",
        "description": (
            "Sales and use tax exemption for qualifying "
            "over-the-counter drugs"
        ),
        "effective_date": "2029-01-01",
        "tax_family": "sales_use_tax",
        "incidence_family": "household_health_consumption",
        "dor_dollar_status": "embedded_in_aggregate",
        "geographic_status": "candidate",
        "proxy_candidate": "population",
        "notes": (
            "DOR estimate excludes prescribed OTC medications "
            "already exempt and excludes grooming/hygiene."
        ),
    },

    {
        "provision_id": "SMALL_BUSINESS_BOC",
        "sections": "909-910",
        "description": (
            "Increase B&O small business credit and "
            "raise filing threshold to $250,000"
        ),
        "effective_date": "2029-01-01",
        "tax_family": "B&O",
        "incidence_family": "small_business",
        "dor_dollar_status": "embedded_in_aggregate",
        "geographic_status": "candidate",
        "proxy_candidate": (
            "small_business_establishments_or_employer_firms"
        ),
        "notes": (
            "Do not allocate using household population."
        ),
    },

    {
        "provision_id": "HEALTH_SURCHARGE_EXEMPTION",
        "sections": "911",
        "description": (
            "High-grossing business surcharge exemptions "
            "for hospitals, prescription-drug resellers, "
            "and licensed health-care providers"
        ),
        "effective_date": "2029-01-01",
        "tax_family": "B&O_surcharge",
        "incidence_family": "health_business",
        "dor_dollar_status": (
            "partly_nondisclosable_and_embedded"
        ),
        "geographic_status": "candidate_with_caution",
        "proxy_candidate": (
            "healthcare_provider_or_facility_geography"
        ),
        "notes": (
            "DOR states fewer than three affected health-care "
            "provider taxpayers for part of FY2029, making "
            "that impact nondisclosable."
        ),
    },

    {
        "provision_id": "CH422_SERVICE_REVERSAL",
        "sections": "1001-1003",
        "description": (
            "Remove specified IT, website, security, staffing, "
            "live-presentation, custom-software and related "
            "services from retail-sales treatment"
        ),
        "effective_date": "2030-01-01",
        "tax_family": "sales_use_and_B&O",
        "incidence_family": "business_services",
        "dor_dollar_status": "embedded_in_aggregate",
        "geographic_status": "difficult",
        "proxy_candidate": (
            "business_activity_or_neutral_allocation"
        ),
        "notes": (
            "Mixed business/service incidence. Avoid treating "
            "as general household tax relief."
        ),
    },

    {
        "provision_id": "LIVE_PRESENTATION_CLARIFICATION",
        "sections": "1101",
        "description": (
            "Exclude specified programs, instruction, "
            "performances and hospital clinical staffing "
            "from retail-sales treatment"
        ),
        "effective_date": "2026-07-01",
        "tax_family": "sales_use_and_B&O",
        "incidence_family": "mixed_services",
        "dor_dollar_status": "embedded_in_aggregate",
        "geographic_status": "candidate_with_caution",
        "proxy_candidate": (
            "population_or_relevant_service_population"
        ),
        "notes": (
            "Includes nonprofit programs, instruction, "
            "performances and hospital clinical staffing."
        ),
    },

    {
        "provision_id": "K12_LIBRARY_SERVICE_EXEMPTION",
        "sections": "1102-1103",
        "description": (
            "Sales/use tax exemption for specified services "
            "sold to K-12 schools, districts, ESDs, libraries "
            "and related entities"
        ),
        "effective_date": "2026-07-01",
        "tax_family": "sales_use_tax",
        "incidence_family": "public_institutions",
        "dor_dollar_status": "embedded_in_aggregate",
        "geographic_status": "candidate",
        "proxy_candidate": (
            "K12_enrollment_plus_population_or_library_proxy"
        ),
        "notes": (
            "Institutional tax relief; should not automatically "
            "be counted as household relief."
        ),
    },

    {
        "provision_id": "FOOD_WHOLESALE_SURCHARGE",
        "sections": "1104",
        "description": (
            "High-grossing business surcharge exemption "
            "for qualifying wholesale food and food ingredients"
        ),
        "effective_date": "2026-07-01",
        "tax_family": "B&O_surcharge",
        "incidence_family": "food_wholesale_business",
        "dor_dollar_status": "embedded_in_aggregate",
        "geographic_status": "difficult",
        "proxy_candidate": (
            "business_activity_or_neutral_allocation"
        ),
        "notes": (
            "Business-side incidence; geographic beneficiary "
            "location may differ from wholesaler location."
        ),
    },
]


# ============================================================
# DOR TEN-YEAR CASH-RECEIPT CONTROLS
#
# Page 116 of final fiscal note.
#
# Values are signed revenue effects:
# negative = lower government receipts
# positive = higher government receipts
#
# FY2026 is zero/blank for these lines in the DOR table.
# ============================================================

ANNUAL_CONTROLS = [
    {
        "tax_family": "B&O",
        "account_code": "001",
        "account_name": "General Fund-State",
        "fy2026": 0,
        "fy2027": 1_100_000,
        "fy2028": 800_000,
        "fy2029": -14_400_000,
        "fy2030": -89_900_000,
        "fy2031": 39_100_000,
        "fy2032": 42_400_000,
        "fy2033": 45_900_000,
        "fy2034": 48_700_000,
        "fy2035": 53_700_000,
        "total_2026_35": 127_400_000,
    },

    {
        "tax_family": "B&O",
        "account_code": "24J",
        "account_name": (
            "Workforce Education Investment Account"
        ),
        "fy2026": 0,
        "fy2027": 1_200_000,
        "fy2028": 1_300_000,
        "fy2029": 46_600_000,
        "fy2030": 113_900_000,
        "fy2031": 118_100_000,
        "fy2032": 122_500_000,
        "fy2033": 127_100_000,
        "fy2034": 131_800_000,
        "fy2035": 136_700_000,
        "total_2026_35": 799_200_000,
    },

    {
        "tax_family": "Retail sales tax",
        "account_code": "001",
        "account_name": "General Fund-State",
        "fy2026": 0,
        "fy2027": -48_700_000,
        "fy2028": -53_500_000,
        "fy2029": -369_620_000,
        "fy2030": -839_260_000,
        "fy2031": -868_830_000,
        "fy2032": -899_520_000,
        "fy2033": -931_260_000,
        "fy2034": -964_130_000,
        "fy2035": -998_240_000,
        "total_2026_35": -5_973_060_000,
    },

    {
        "tax_family": "Retail sales tax",
        "account_code": "218",
        "account_name": (
            "Multimodal Transportation Account"
        ),
        "fy2026": 0,
        "fy2027": 0,
        "fy2028": -851_000,
        "fy2029": -6_616_000,
        "fy2030": -13_100_000,
        "fy2031": -13_630_000,
        "fy2032": -14_070_000,
        "fy2033": -14_610_000,
        "fy2034": -15_060_000,
        "fy2035": -15_600_000,
        "total_2026_35": -93_537_000,
    },

    {
        "tax_family": "Retail sales tax",
        "account_code": "553",
        "account_name": (
            "Performance Audits of Government Account"
        ),
        "fy2026": 0,
        "fy2027": -78_000,
        "fy2028": -87_000,
        "fy2029": -616_000,
        "fy2030": -1_375_000,
        "fy2031": -1_376_000,
        "fy2032": -1_487_000,
        "fy2033": -1_489_000,
        "fy2034": -1_590_000,
        "fy2035": -1_591_000,
        "total_2026_35": -9_689_000,
    },

    {
        "tax_family": "Tax on Income",
        "account_code": "001",
        "account_name": "General Fund-State",
        "fy2026": 0,
        "fy2027": 0,
        "fy2028": 0,
        "fy2029": 2_698_000_000,
        "fy2030": 3_732_000_000,
        "fy2031": 3_167_000_000,
        "fy2032": 3_297_000_000,
        "fy2033": 3_439_000_000,
        "fy2034": 3_591_000_000,
        "fy2035": 3_753_000_000,
        "total_2026_35": 23_677_000_000,
    },
]


def money(value):
    return f"${value:,.2f}"


def write_csv(path, rows):
    if not rows:
        return

    with path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=list(rows[0].keys()),
        )
        writer.writeheader()
        writer.writerows(rows)


def validate_annual_controls():

    year_columns = [
        f"fy{year}"
        for year in range(2026, 2036)
    ]

    print()
    print("ANNUAL CONTROL VALIDATION")
    print("-" * 80)

    for row in ANNUAL_CONTROLS:

        calculated = sum(
            row[col]
            for col in year_columns
        )

        difference = (
            calculated
            - row["total_2026_35"]
        )

        print(
            f"{row['tax_family']:<20} "
            f"{row['account_code']:<5} "
            f"reported={money(row['total_2026_35']):>20} "
            f"calculated={money(calculated):>20} "
            f"diff={money(difference):>12}"
        )

        if difference != 0:
            raise ValueError(
                "Annual values do not reconcile to "
                f"DOR ten-year total for "
                f"{row['tax_family']} "
                f"{row['account_code']}."
            )


def main():

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    write_csv(
        PROVISION_OUTPUT,
        PROVISIONS,
    )

    write_csv(
        ANNUAL_OUTPUT,
        ANNUAL_CONTROLS,
    )

    print(
        "ESSB 6346 TAX RELIEF PROVISION CONTROLS v0.1"
    )
    print("=" * 80)

    print()
    print(
        f"Provision inventory rows : "
        f"{len(PROVISIONS)}"
    )

    print(
        f"DOR annual control rows  : "
        f"{len(ANNUAL_CONTROLS)}"
    )

    validate_annual_controls()

    print()
    print("PROVISION CLASSIFICATION")
    print("-" * 80)

    for row in PROVISIONS:
        print(
            f"{row['provision_id']:<34} "
            f"{row['effective_date']:<12} "
            f"{row['incidence_family']:<28} "
            f"{row['dor_dollar_status']}"
        )

    print()
    print("KEY DOR ANNUAL VALUES")
    print("-" * 80)

    for year in [2029, 2030, 2031]:

        income = next(
            row[f"fy{year}"]
            for row in ANNUAL_CONTROLS
            if row["tax_family"] == "Tax on Income"
        )

        sales = sum(
            row[f"fy{year}"]
            for row in ANNUAL_CONTROLS
            if row["tax_family"] == "Retail sales tax"
        )

        bo = sum(
            row[f"fy{year}"]
            for row in ANNUAL_CONTROLS
            if row["tax_family"] == "B&O"
        )

        print(
            f"FY{year}: "
            f"income tax={money(income):>18}  "
            f"sales tax={money(sales):>18}  "
            f"B&O={money(bo):>18}"
        )

    print()
    print("IMPORTANT")
    print("-" * 80)

    print(
        "DOR does not provide an independent dollar "
        "estimate for every statutory tax-relief provision."
    )

    print(
        "Provision-level amounts must therefore remain "
        "UNALLOCATED unless a defensible source supplies "
        "a separate estimate."
    )

    print(
        "The annual DOR tax/account controls are preserved "
        "without inventing a split among provisions."
    )

    print()
    print("OUTPUTS")
    print("-" * 80)
    print(PROVISION_OUTPUT)
    print(ANNUAL_OUTPUT)


if __name__ == "__main__":
    main()