"""
Build integrated Washington legislative-district incidence model v0.1.

MODEL ARCHITECTURE
------------------
Geographic evidence = component-specific legislative-district shares.
Fiscal assumptions/controls = exact statewide dollar controls.
Final LD dollars = geographic share * statewide control.

This avoids propagating harmless cent-level rounding from intermediate
component dollar columns.

SCENARIOS
---------
Average Case:
    Divide the exact statewide modeled benefit pool equally among
    Washington's 49 legislative districts.

Illustrative Case:
    Distribute the exact same statewide modeled benefit pool using
    independently derived geographic allocation shares for:

        WFTC
        K-12
        Health / human services
        Higher education
        Fair Start

TAX SIDE
--------
Both cases use exactly the same estimated district-level Millionaires
Tax incidence.

The original Model 2 tax estimates supply geographic shares only.
Those shares are normalized here to exact DOR scenario-year controls:

    FY2029 = $2.698B
    FY2030 = $3.732B

IMPORTANT
---------
The five modeled benefit pools do not exhaust the official Millionaires
Tax revenue control.

The remaining amount is preserved as UNALLOCATED. No geographic
incidence is manufactured for that residual.

Therefore a negative statewide modeled net is NOT a statewide fiscal
loss. It is the arithmetic consequence of comparing the complete tax
control with only the benefit categories geographically allocated in
this illustrative model.
"""

from pathlib import Path
import csv


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

MODEL_DIR = Path("data/processed/model")

WFTC_FILE = MODEL_DIR / "wftc_ld_allocation_v0_2.csv"
K12_FILE = MODEL_DIR / "k12_ld_allocation_v0_1.csv"
HEALTH_FILE = MODEL_DIR / "health_ld_allocation_v0_1.csv"
HIGHER_ED_FILE = MODEL_DIR / "higher_ed_ld_allocation_v0_1.csv"
FAIR_START_FILE = MODEL_DIR / "fair_start_ld_allocation_v0_1.csv"
TAX_FILE = MODEL_DIR / "millionaires_tax_ld_weights_v0_1.csv"

OUTPUT_FILE = MODEL_DIR / "illustrative_ld_incidence_v0_1.csv"


# ---------------------------------------------------------------------------
# Exact statewide scenario controls
# ---------------------------------------------------------------------------

EXPECTED_LDS = list(range(1, 50))

SCENARIOS = {
    2029: {
        "tax": 2_698_000_000.0,
        "wftc": 250_000_000.0,
        "k12": 1_000_000_000.0,
        "health": 750_000_000.0,
        "higher_ed": 400_000_000.0,
        "fair_start": 134_900_000.0,
    },
    2030: {
        "tax": 3_732_000_000.0,
        "wftc": 250_000_000.0,
        "k12": 1_000_000_000.0,
        "health": 750_000_000.0,
        "higher_ed": 400_000_000.0,
        "fair_start": 186_600_000.0,
    },
}

for controls in SCENARIOS.values():
    controls["benefits"] = (
        controls["wftc"]
        + controls["k12"]
        + controls["health"]
        + controls["higher_ed"]
        + controls["fair_start"]
    )

    controls["unallocated"] = (
        controls["tax"]
        - controls["benefits"]
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def read_csv(path):
    if not path.exists():
        raise FileNotFoundError(
            f"Missing required file: {path}"
        )

    with path.open(
        "r",
        newline="",
        encoding="utf-8-sig",
    ) as handle:
        return list(csv.DictReader(handle))


def as_float(value):
    if value is None:
        raise ValueError(
            "Unexpected null numeric value."
        )

    text = str(value).strip()

    if not text:
        raise ValueError(
            "Unexpected blank numeric value."
        )

    return float(
        text.replace("$", "").replace(",", "")
    )


def as_int(value):
    return int(float(str(value).strip()))


def money(value):
    return f"${value:,.2f}"


def index_by_ld(rows, source_name):
    indexed = {}

    for row in rows:
        district = as_int(
            row["legislative_district"]
        )

        if district in indexed:
            raise ValueError(
                f"{source_name}: duplicate LD {district}"
            )

        indexed[district] = row

    districts = sorted(indexed)

    if districts != EXPECTED_LDS:
        raise ValueError(
            f"{source_name}: expected LDs 1-49; "
            f"found {districts}"
        )

    return indexed


def normalize_shares(raw_shares, source_name):
    """
    Normalize source shares to sum exactly to 1 mathematically.

    This does not change their relative geographic distribution.
    It merely protects the final integration from floating-point
    or serialized-decimal residue.
    """

    total = sum(raw_shares.values())

    if total <= 0:
        raise ValueError(
            f"{source_name}: share total must be positive."
        )

    normalized = {
        district: value / total
        for district, value in raw_shares.items()
    }

    normalized_total = sum(normalized.values())

    if abs(normalized_total - 1.0) > 1e-12:
        raise ValueError(
            f"{source_name}: normalized shares sum to "
            f"{normalized_total:.15f}"
        )

    return normalized, total


# ---------------------------------------------------------------------------
# Load and derive geographic shares
# ---------------------------------------------------------------------------

def load_geographic_shares():

    wftc_rows = index_by_ld(
        read_csv(WFTC_FILE),
        "WFTC",
    )

    k12_rows = index_by_ld(
        read_csv(K12_FILE),
        "K12",
    )

    health_rows = index_by_ld(
        read_csv(HEALTH_FILE),
        "HEALTH",
    )

    higher_ed_rows = index_by_ld(
        read_csv(HIGHER_ED_FILE),
        "HIGHER_ED",
    )

    fair_start_rows = index_by_ld(
        read_csv(FAIR_START_FILE),
        "FAIR_START",
    )

    tax_rows = index_by_ld(
        read_csv(TAX_FILE),
        "TAX",
    )

    raw = {
        "wftc": {
            d: as_float(
                wftc_rows[d][
                    "share_of_statewide_wftc"
                ]
            )
            for d in EXPECTED_LDS
        },

        "k12": {
            d: as_float(
                k12_rows[d][
                    "public_k12_share"
                ]
            )
            for d in EXPECTED_LDS
        },

        "health": {
            d: as_float(
                health_rows[d][
                    "medicaid_share"
                ]
            )
            for d in EXPECTED_LDS
        },

        "higher_ed": {
            d: as_float(
                higher_ed_rows[d][
                    "public_higher_ed_share"
                ]
            )
            for d in EXPECTED_LDS
        },

        "fair_start": {
            d: as_float(
                fair_start_rows[d][
                    "under5_share"
                ]
            )
            for d in EXPECTED_LDS
        },

        "tax": {
            d: as_float(
                tax_rows[d][
                    "tax_incidence_share"
                ]
            )
            for d in EXPECTED_LDS
        },
    }

    normalized = {}
    original_totals = {}

    for name, shares in raw.items():
        normalized[name], original_totals[name] = (
            normalize_shares(
                shares,
                name.upper(),
            )
        )

    return normalized, original_totals


# ---------------------------------------------------------------------------
# Build integrated rows
# ---------------------------------------------------------------------------

def build_rows(shares):
    rows = []

    for fiscal_year in [2029, 2030]:

        controls = SCENARIOS[fiscal_year]

        average_benefit = (
            controls["benefits"] / 49
        )

        for district in EXPECTED_LDS:

            # -----------------------------------------------------------
            # Exact statewide controls x geographic shares
            # -----------------------------------------------------------

            tax_paid = (
                shares["tax"][district]
                * controls["tax"]
            )

            wftc = (
                shares["wftc"][district]
                * controls["wftc"]
            )

            k12 = (
                shares["k12"][district]
                * controls["k12"]
            )

            health = (
                shares["health"][district]
                * controls["health"]
            )

            higher_ed = (
                shares["higher_ed"][district]
                * controls["higher_ed"]
            )

            fair_start = (
                shares["fair_start"][district]
                * controls["fair_start"]
            )

            illustrative_benefit = (
                wftc
                + k12
                + health
                + higher_ed
                + fair_start
            )

            illustrative_net = (
                illustrative_benefit
                - tax_paid
            )

            average_net = (
                average_benefit
                - tax_paid
            )

            geographic_effect = (
                illustrative_benefit
                - average_benefit
            )

            rows.append(
                {
                    "scenario_fy":
                        fiscal_year,

                    "legislative_district":
                        district,

                    # Geographic shares
                    "tax_incidence_share":
                        shares["tax"][district],

                    "wftc_share":
                        shares["wftc"][district],

                    "k12_share":
                        shares["k12"][district],

                    "health_share":
                        shares["health"][district],

                    "higher_ed_share":
                        shares["higher_ed"][district],

                    "fair_start_share":
                        shares["fair_start"][district],

                    # Tax incidence
                    "estimated_tax_paid":
                        tax_paid,

                    # Illustrative benefit components
                    "wftc_benefit":
                        wftc,

                    "k12_benefit":
                        k12,

                    "health_human_services_benefit":
                        health,

                    "higher_education_benefit":
                        higher_ed,

                    "fair_start_benefit":
                        fair_start,

                    # Illustrative Case
                    "illustrative_benefit_total":
                        illustrative_benefit,

                    "illustrative_net":
                        illustrative_net,

                    # Average Case
                    "average_benefit_total":
                        average_benefit,

                    "average_net":
                        average_net,

                    # Geographic redistribution
                    "illustrative_minus_average_benefit":
                        geographic_effect,

                    "illustrative_minus_average_net":
                        illustrative_net
                        - average_net,

                    # Statewide controls
                    "statewide_tax_control":
                        controls["tax"],

                    "statewide_modeled_benefit_control":
                        controls["benefits"],

                    "statewide_unallocated_amount":
                        controls["unallocated"],

                    # Semantic controls
                    "tax_geography_method":
                        "MODEL2_SHARE_NORMALIZED_TO_DOR",

                    "benefit_geography_method":
                        "COMPONENT_SHARES_X_EXACT_STATE_CONTROL",

                    "scenario_status":
                        "ILLUSTRATIVE_NOT_FORECAST",
                }
            )

    return rows


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate(rows):

    if len(rows) != 98:
        raise AssertionError(
            f"Expected 98 rows, found {len(rows)}."
        )

    for fiscal_year in [2029, 2030]:

        year_rows = [
            row
            for row in rows
            if row["scenario_fy"] == fiscal_year
        ]

        controls = SCENARIOS[fiscal_year]

        if len(year_rows) != 49:
            raise AssertionError(
                f"FY{fiscal_year}: expected 49 rows."
            )

        districts = sorted(
            row["legislative_district"]
            for row in year_rows
        )

        if districts != EXPECTED_LDS:
            raise AssertionError(
                f"FY{fiscal_year}: LD set is invalid."
            )

        checks = {
            "tax": (
                sum(
                    r["estimated_tax_paid"]
                    for r in year_rows
                ),
                controls["tax"],
            ),

            "wftc": (
                sum(
                    r["wftc_benefit"]
                    for r in year_rows
                ),
                controls["wftc"],
            ),

            "k12": (
                sum(
                    r["k12_benefit"]
                    for r in year_rows
                ),
                controls["k12"],
            ),

            "health": (
                sum(
                    r["health_human_services_benefit"]
                    for r in year_rows
                ),
                controls["health"],
            ),

            "higher_ed": (
                sum(
                    r["higher_education_benefit"]
                    for r in year_rows
                ),
                controls["higher_ed"],
            ),

            "fair_start": (
                sum(
                    r["fair_start_benefit"]
                    for r in year_rows
                ),
                controls["fair_start"],
            ),

            "illustrative benefits": (
                sum(
                    r["illustrative_benefit_total"]
                    for r in year_rows
                ),
                controls["benefits"],
            ),

            "average benefits": (
                sum(
                    r["average_benefit_total"]
                    for r in year_rows
                ),
                controls["benefits"],
            ),
        }

        # One-cent reconciliation tolerance after normalization.
        for name, (actual, expected) in checks.items():

            if abs(actual - expected) >= 0.01:
                raise AssertionError(
                    f"FY{fiscal_year} {name}: "
                    f"actual={actual:.12f}, "
                    f"expected={expected:.12f}, "
                    f"difference={actual - expected:.12f}"
                )

        expected_net = (
            controls["benefits"]
            - controls["tax"]
        )

        illustrative_net = sum(
            r["illustrative_net"]
            for r in year_rows
        )

        average_net = sum(
            r["average_net"]
            for r in year_rows
        )

        if abs(
            illustrative_net - expected_net
        ) >= 0.01:
            raise AssertionError(
                f"FY{fiscal_year}: illustrative net "
                f"does not reconcile."
            )

        if abs(
            average_net - expected_net
        ) >= 0.01:
            raise AssertionError(
                f"FY{fiscal_year}: average net "
                f"does not reconcile."
            )

        if abs(
            expected_net
            + controls["unallocated"]
        ) >= 0.01:
            raise AssertionError(
                f"FY{fiscal_year}: residual identity failed."
            )

        redistribution = sum(
            r["illustrative_minus_average_benefit"]
            for r in year_rows
        )

        if abs(redistribution) >= 0.01:
            raise AssertionError(
                f"FY{fiscal_year}: geographic redistribution "
                f"does not sum to zero."
            )

        for row in year_rows:

            net_difference = (
                row["illustrative_net"]
                - row["average_net"]
            )

            benefit_difference = (
                row[
                    "illustrative_minus_average_benefit"
                ]
            )

            if abs(
                net_difference
                - benefit_difference
            ) >= 0.01:
                raise AssertionError(
                    f"FY{fiscal_year} "
                    f"LD{row['legislative_district']}: "
                    f"case-difference identity failed."
                )


# ---------------------------------------------------------------------------
# Write output
# ---------------------------------------------------------------------------

def write_csv(rows):

    fieldnames = [
        "scenario_fy",
        "legislative_district",

        "tax_incidence_share",
        "wftc_share",
        "k12_share",
        "health_share",
        "higher_ed_share",
        "fair_start_share",

        "estimated_tax_paid",

        "wftc_benefit",
        "k12_benefit",
        "health_human_services_benefit",
        "higher_education_benefit",
        "fair_start_benefit",

        "illustrative_benefit_total",
        "illustrative_net",

        "average_benefit_total",
        "average_net",

        "illustrative_minus_average_benefit",
        "illustrative_minus_average_net",

        "statewide_tax_control",
        "statewide_modeled_benefit_control",
        "statewide_unallocated_amount",

        "tax_geography_method",
        "benefit_geography_method",
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


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_share_controls(original_totals):

    print()
    print("SOURCE SHARE CONTROLS")
    print("-" * 92)

    for name in [
        "tax",
        "wftc",
        "k12",
        "health",
        "higher_ed",
        "fair_start",
    ]:
        print(
            f"{name.upper():<15}: "
            f"source sum = "
            f"{original_totals[name]:.15f}"
        )

    print()
    print(
        "Source shares are normalized internally before application "
        "to exact statewide controls."
    )


def print_year_report(rows, fiscal_year):

    year_rows = [
        row
        for row in rows
        if row["scenario_fy"] == fiscal_year
    ]

    controls = SCENARIOS[fiscal_year]

    print()
    print(f"FY{fiscal_year}")
    print("=" * 92)

    print()
    print("STATEWIDE CONTROLS")
    print("-" * 92)

    print(
        f"Millionaires Tax control       : "
        f"{money(controls['tax'])}"
    )

    print(
        f"WFTC                            : "
        f"{money(controls['wftc'])}"
    )

    print(
        f"K-12                            : "
        f"{money(controls['k12'])}"
    )

    print(
        f"Health / human services         : "
        f"{money(controls['health'])}"
    )

    print(
        f"Higher education                : "
        f"{money(controls['higher_ed'])}"
    )

    print(
        f"Fair Start                      : "
        f"{money(controls['fair_start'])}"
    )

    print(
        f"Modeled benefit total           : "
        f"{money(controls['benefits'])}"
    )

    print(
        f"Unallocated                     : "
        f"{money(controls['unallocated'])}"
    )

    illustrative_net = sum(
        r["illustrative_net"]
        for r in year_rows
    )

    average_net = sum(
        r["average_net"]
        for r in year_rows
    )

    positive = sum(
        1
        for r in year_rows
        if r["illustrative_net"] > 0
    )

    negative = sum(
        1
        for r in year_rows
        if r["illustrative_net"] < 0
    )

    print()
    print("INCIDENCE SUMMARY")
    print("-" * 92)

    print(
        f"Illustrative statewide net      : "
        f"{money(illustrative_net)}"
    )

    print(
        f"Average-case statewide net      : "
        f"{money(average_net)}"
    )

    print(
        f"Illustrative positive-net LDs   : "
        f"{positive}"
    )

    print(
        f"Illustrative negative-net LDs   : "
        f"{negative}"
    )

    print()
    print("ILLUSTRATIVE CASE — LARGEST POSITIVE NETS")
    print("-" * 92)

    ranked = sorted(
        year_rows,
        key=lambda r: r["illustrative_net"],
        reverse=True,
    )

    for row in ranked[:10]:
        print(
            f"LD {row['legislative_district']:>2}: "
            f"net={money(row['illustrative_net']):>18}  "
            f"benefits="
            f"{money(row['illustrative_benefit_total']):>18}  "
            f"tax={money(row['estimated_tax_paid'])}"
        )

    print()
    print("ILLUSTRATIVE CASE — LARGEST NEGATIVE NETS")
    print("-" * 92)

    for row in reversed(ranked[-10:]):
        print(
            f"LD {row['legislative_district']:>2}: "
            f"net={money(row['illustrative_net']):>18}  "
            f"benefits="
            f"{money(row['illustrative_benefit_total']):>18}  "
            f"tax={money(row['estimated_tax_paid'])}"
        )

    print()
    print("LARGEST GEOGRAPHIC SHIFTS FROM 1/49")
    print("-" * 92)

    shifts = sorted(
        year_rows,
        key=lambda r: abs(
            r["illustrative_minus_average_benefit"]
        ),
        reverse=True,
    )

    for row in shifts[:10]:
        print(
            f"LD {row['legislative_district']:>2}: "
            f"shift="
            f"{money(row['illustrative_minus_average_benefit']):>18}  "
            f"illustrative="
            f"{money(row['illustrative_benefit_total']):>18}  "
            f"average="
            f"{money(row['average_benefit_total'])}"
        )


def print_report(rows, original_totals):

    print()
    print(
        "INTEGRATED LEGISLATIVE-DISTRICT INCIDENCE MODEL v0.1"
    )
    print("=" * 92)

    print_share_controls(
        original_totals
    )

    for fiscal_year in [2029, 2030]:
        print_year_report(
            rows,
            fiscal_year,
        )

    print()
    print("VALIDATION")
    print("=" * 92)

    print("Rows                              : 98 PASS")
    print("Legislative districts per year   : 49 PASS")
    print("Geographic source shares          : NORMALIZED")
    print("Tax statewide controls            : PASS")
    print("Five benefit statewide controls   : PASS")
    print("Average/Illustrative totals       : IDENTICAL PASS")
    print("Geographic redistribution         : SUMS TO ZERO PASS")
    print("Statewide residual identity       : PASS")

    print()
    print("INTERPRETATION")
    print("-" * 92)

    print(
        "Geographic source shares determine district distribution; "
        "exact statewide controls determine dollars."
    )

    print(
        "Average Case and Illustrative Case contain exactly the same "
        "statewide modeled benefit dollars."
    )

    print(
        "Their difference therefore isolates geographic redistribution "
        "within the modeled benefit pool."
    )

    print(
        "The statewide negative modeled net equals revenue that remains "
        "UNALLOCATED in this model."
    )

    print(
        "It must not be interpreted as a statewide fiscal loss."
    )

    print()
    print("OUTPUT")
    print("-" * 92)
    print(OUTPUT_FILE)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():

    shares, original_totals = (
        load_geographic_shares()
    )

    rows = build_rows(
        shares
    )

    validate(
        rows
    )

    write_csv(
        rows
    )

    print_report(
        rows,
        original_totals,
    )


if __name__ == "__main__":
    main()