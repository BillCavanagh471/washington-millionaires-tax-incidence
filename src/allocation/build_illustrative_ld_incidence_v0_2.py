"""
Build integrated Washington legislative-district incidence model v0.2.

MODEL ARCHITECTURE
------------------
Benefit geography:
    Component-specific legislative-district shares determine the
    geographic allocation of five modeled benefit pools.

Tax geography:
    Millionaires Tax LD weights v0.2 supplies already validated,
    scenario-year district tax amounts derived from Model 1 geography.

    The 47 observable districts collectively reconcile to the exact
    statewide tax controls:

        FY2029 = $2.698B
        FY2030 = $3.732B

    LD14 and LD29 lack disclosed source inputs required for the
    underlying Model 1 tax calculation. Their district tax incidence
    is therefore N/A, not zero and not imputed.

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

Both cases use exactly the same tax incidence where tax incidence
is available.

IMPORTANT
---------
Benefits remain calculable for all 49 districts.

Tax and net incidence are calculable for 47 districts.

LD14 and LD29 retain benefit estimates but have:
    estimated_tax_paid = N/A
    illustrative_net   = N/A
    average_net        = N/A

The five modeled benefit pools do not exhaust the official
Millionaires Tax revenue control. The remaining statewide amount is
preserved as UNALLOCATED.

Statewide accounting controls and district net-incidence statistics
are therefore reported separately.
"""

from pathlib import Path
import csv
import math


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

MODEL_DIR = Path("data/processed/model")

WFTC_FILE = MODEL_DIR / "wftc_ld_allocation_v0_2.csv"
K12_FILE = MODEL_DIR / "k12_ld_allocation_v0_1.csv"
HEALTH_FILE = MODEL_DIR / "health_ld_allocation_v0_1.csv"
HIGHER_ED_FILE = MODEL_DIR / "higher_ed_ld_allocation_v0_1.csv"
FAIR_START_FILE = MODEL_DIR / "fair_start_ld_allocation_v0_1.csv"

TAX_FILE = (
    MODEL_DIR
    / "millionaires_tax_ld_weights_v0_2.csv"
)

OUTPUT_FILE = (
    MODEL_DIR
    / "illustrative_ld_incidence_v0_2.csv"
)


# ---------------------------------------------------------------------------
# Exact statewide scenario controls
# ---------------------------------------------------------------------------

EXPECTED_LDS = list(range(1, 50))
TAX_UNAVAILABLE_LDS = {14, 29}

SCENARIOS = {
    2029: {
        "tax": 2_698_000_000.0,
        "wftc": 250_000_000.0,
        "k12": 1_000_000_000.0,
        "health": 750_000_000.0,
        "higher_ed": 400_000_000.0,
        "fair_start": 134_900_000.0,
        "tax_column": "tax_paid_fy2029_2_698b",
    },
    2030: {
        "tax": 3_732_000_000.0,
        "wftc": 250_000_000.0,
        "k12": 1_000_000_000.0,
        "health": 750_000_000.0,
        "higher_ed": 400_000_000.0,
        "fair_start": 186_600_000.0,
        "tax_column": "tax_paid_fy2030_3_732b",
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

        return list(
            csv.DictReader(handle)
        )


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


def as_optional_float(value):

    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    return float(
        text.replace("$", "").replace(",", "")
    )


def as_int(value):

    return int(
        float(str(value).strip())
    )


def money(value):

    if value is None:
        return "N/A"

    return f"${value:,.2f}"


def index_by_ld(
    rows,
    source_name,
):

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


def normalize_shares(
    raw_shares,
    source_name,
):
    """
    Normalize benefit source shares to sum exactly to 1.

    Tax geography is NOT normalized here. Tax v0.2 has already
    been independently constructed and validated.
    """

    total = math.fsum(
        raw_shares.values()
    )

    if total <= 0:
        raise ValueError(
            f"{source_name}: share total must be positive."
        )

    normalized = {
        district: value / total
        for district, value in raw_shares.items()
    }

    normalized_total = math.fsum(
        normalized.values()
    )

    if abs(
        normalized_total - 1.0
    ) > 1e-12:
        raise ValueError(
            f"{source_name}: normalized shares sum to "
            f"{normalized_total:.15f}"
        )

    return normalized, total


# ---------------------------------------------------------------------------
# Load benefit geographic shares
# ---------------------------------------------------------------------------

def load_benefit_geographic_shares():

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
    }

    normalized = {}
    original_totals = {}

    for name, shares in raw.items():

        (
            normalized[name],
            original_totals[name],
        ) = normalize_shares(
            shares,
            name.upper(),
        )

    return (
        normalized,
        original_totals,
    )


# ---------------------------------------------------------------------------
# Load accepted Tax Geography v0.2
# ---------------------------------------------------------------------------

def load_tax_geography():

    tax_rows = index_by_ld(
        read_csv(TAX_FILE),
        "TAX v0.2",
    )

    tax = {}

    for district in EXPECTED_LDS:

        row = tax_rows[district]

        status = str(
            row["tax_incidence_status"]
        ).strip()

        share = as_optional_float(
            row["model1_47district_share"]
        )

        fy2029_tax = as_optional_float(
            row["tax_paid_fy2029_2_698b"]
        )

        fy2030_tax = as_optional_float(
            row["tax_paid_fy2030_3_732b"]
        )

        if district in TAX_UNAVAILABLE_LDS:

            if status != "SOURCE_INPUTS_UNAVAILABLE":
                raise ValueError(
                    f"LD{district}: unexpected tax status "
                    f"{status!r}"
                )

            if any(
                value is not None
                for value in [
                    share,
                    fy2029_tax,
                    fy2030_tax,
                ]
            ):
                raise ValueError(
                    f"LD{district}: tax fields must be N/A."
                )

        else:

            if status != "OBSERVABLE":
                raise ValueError(
                    f"LD{district}: expected OBSERVABLE, "
                    f"found {status!r}"
                )

            if any(
                value is None
                for value in [
                    share,
                    fy2029_tax,
                    fy2030_tax,
                ]
            ):
                raise ValueError(
                    f"LD{district}: observable tax fields "
                    f"must not be blank."
                )

        tax[district] = {
            "status": status,
            "share": share,
            2029: fy2029_tax,
            2030: fy2030_tax,
        }

    observable_rows = [
        tax[d]
        for d in EXPECTED_LDS
        if tax[d]["status"] == "OBSERVABLE"
    ]

    if len(observable_rows) != 47:
        raise ValueError(
            "Tax v0.2 must contain exactly "
            "47 observable districts."
        )

    share_total = math.fsum(
        row["share"]
        for row in observable_rows
    )

    if abs(
        share_total - 1.0
    ) > 1e-12:
        raise ValueError(
            "Tax v0.2 geographic shares do not "
            f"sum to 1: {share_total:.15f}"
        )

    for fiscal_year in [2029, 2030]:

        tax_total = math.fsum(
            tax[d][fiscal_year]
            for d in EXPECTED_LDS
            if tax[d][fiscal_year] is not None
        )

        expected = SCENARIOS[
            fiscal_year
        ]["tax"]

        if abs(
            tax_total - expected
        ) >= 0.01:
            raise ValueError(
                f"FY{fiscal_year}: tax v0.2 "
                f"does not reconcile. "
                f"actual={tax_total:.12f}, "
                f"expected={expected:.12f}"
            )

    return tax


# ---------------------------------------------------------------------------
# Build integrated rows
# ---------------------------------------------------------------------------

def build_rows(
    benefit_shares,
    tax_geography,
):

    rows = []

    for fiscal_year in [2029, 2030]:

        controls = SCENARIOS[
            fiscal_year
        ]

        average_benefit = (
            controls["benefits"] / 49
        )

        for district in EXPECTED_LDS:

            # ---------------------------------------------------------------
            # Tax incidence
            #
            # IMPORTANT:
            # Tax Geography v0.2 already contains the accepted scenario-year
            # district dollars. Do not renormalize them here.
            # ---------------------------------------------------------------

            tax_record = tax_geography[
                district
            ]

            tax_paid = tax_record[
                fiscal_year
            ]

            tax_available = (
                tax_paid is not None
            )

            if tax_available:
                net_status = "CALCULATED"
            else:
                net_status = (
                    "TAX_INCIDENCE_UNAVAILABLE"
                )

            # ---------------------------------------------------------------
            # Exact statewide benefit controls x geographic shares
            # ---------------------------------------------------------------

            wftc = (
                benefit_shares[
                    "wftc"
                ][district]
                * controls["wftc"]
            )

            k12 = (
                benefit_shares[
                    "k12"
                ][district]
                * controls["k12"]
            )

            health = (
                benefit_shares[
                    "health"
                ][district]
                * controls["health"]
            )

            higher_ed = (
                benefit_shares[
                    "higher_ed"
                ][district]
                * controls["higher_ed"]
            )

            fair_start = (
                benefit_shares[
                    "fair_start"
                ][district]
                * controls["fair_start"]
            )

            illustrative_benefit = (
                wftc
                + k12
                + health
                + higher_ed
                + fair_start
            )

            geographic_effect = (
                illustrative_benefit
                - average_benefit
            )

            # ---------------------------------------------------------------
            # Net incidence
            # ---------------------------------------------------------------

            if tax_available:

                illustrative_net = (
                    illustrative_benefit
                    - tax_paid
                )

                average_net = (
                    average_benefit
                    - tax_paid
                )

                illustrative_minus_average_net = (
                    illustrative_net
                    - average_net
                )

            else:

                illustrative_net = None
                average_net = None
                illustrative_minus_average_net = None

            rows.append(
                {
                    "scenario_fy":
                        fiscal_year,

                    "legislative_district":
                        district,

                    # Tax availability
                    "tax_incidence_status":
                        tax_record["status"],

                    "net_incidence_status":
                        net_status,

                    # Geographic shares
                    "tax_incidence_share":
                        tax_record["share"],

                    "wftc_share":
                        benefit_shares[
                            "wftc"
                        ][district],

                    "k12_share":
                        benefit_shares[
                            "k12"
                        ][district],

                    "health_share":
                        benefit_shares[
                            "health"
                        ][district],

                    "higher_ed_share":
                        benefit_shares[
                            "higher_ed"
                        ][district],

                    "fair_start_share":
                        benefit_shares[
                            "fair_start"
                        ][district],

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
                        illustrative_minus_average_net,

                    # Statewide controls
                    "statewide_tax_control":
                        controls["tax"],

                    "statewide_modeled_benefit_control":
                        controls["benefits"],

                    "statewide_unallocated_amount":
                        controls["unallocated"],

                    # Semantic controls
                    "tax_geography_method":
                        (
                            "MODEL1_47LD_SHARE_"
                            "NORMALIZED_TO_STATE_CONTROL"
                        ),

                    "benefit_geography_method":
                        (
                            "COMPONENT_SHARES_X_"
                            "EXACT_STATE_CONTROL"
                        ),

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
            if row["scenario_fy"]
            == fiscal_year
        ]

        controls = SCENARIOS[
            fiscal_year
        ]

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

        # ---------------------------------------------------------------
        # Availability semantics
        # ---------------------------------------------------------------

        calculated_rows = [
            row
            for row in year_rows
            if row["net_incidence_status"]
            == "CALCULATED"
        ]

        unavailable_rows = [
            row
            for row in year_rows
            if row["net_incidence_status"]
            == "TAX_INCIDENCE_UNAVAILABLE"
        ]

        if len(calculated_rows) != 47:
            raise AssertionError(
                f"FY{fiscal_year}: expected "
                "47 calculated net rows."
            )

        if len(unavailable_rows) != 2:
            raise AssertionError(
                f"FY{fiscal_year}: expected "
                "2 unavailable net rows."
            )

        unavailable_lds = {
            row["legislative_district"]
            for row in unavailable_rows
        }

        if unavailable_lds != TAX_UNAVAILABLE_LDS:
            raise AssertionError(
                f"FY{fiscal_year}: unexpected "
                f"unavailable LDs {unavailable_lds}."
            )

        for row in unavailable_rows:

            if row["estimated_tax_paid"] is not None:
                raise AssertionError(
                    f"FY{fiscal_year} "
                    f"LD{row['legislative_district']}: "
                    "tax must be N/A."
                )

            if row["tax_incidence_share"] is not None:
                raise AssertionError(
                    f"FY{fiscal_year} "
                    f"LD{row['legislative_district']}: "
                    "tax share must be N/A."
                )

            if row["illustrative_net"] is not None:
                raise AssertionError(
                    f"FY{fiscal_year} "
                    f"LD{row['legislative_district']}: "
                    "illustrative net must be N/A."
                )

            if row["average_net"] is not None:
                raise AssertionError(
                    f"FY{fiscal_year} "
                    f"LD{row['legislative_district']}: "
                    "average net must be N/A."
                )

        # ---------------------------------------------------------------
        # Statewide tax and benefit controls
        # ---------------------------------------------------------------

        checks = {
            "tax": (
                math.fsum(
                    r["estimated_tax_paid"]
                    for r in calculated_rows
                ),
                controls["tax"],
            ),

            "wftc": (
                math.fsum(
                    r["wftc_benefit"]
                    for r in year_rows
                ),
                controls["wftc"],
            ),

            "k12": (
                math.fsum(
                    r["k12_benefit"]
                    for r in year_rows
                ),
                controls["k12"],
            ),

            "health": (
                math.fsum(
                    r["health_human_services_benefit"]
                    for r in year_rows
                ),
                controls["health"],
            ),

            "higher_ed": (
                math.fsum(
                    r["higher_education_benefit"]
                    for r in year_rows
                ),
                controls["higher_ed"],
            ),

            "fair_start": (
                math.fsum(
                    r["fair_start_benefit"]
                    for r in year_rows
                ),
                controls["fair_start"],
            ),

            "illustrative benefits": (
                math.fsum(
                    r["illustrative_benefit_total"]
                    for r in year_rows
                ),
                controls["benefits"],
            ),

            "average benefits": (
                math.fsum(
                    r["average_benefit_total"]
                    for r in year_rows
                ),
                controls["benefits"],
            ),
        }

        for name, (
            actual,
            expected,
        ) in checks.items():

            if abs(
                actual - expected
            ) >= 0.01:

                raise AssertionError(
                    f"FY{fiscal_year} {name}: "
                    f"actual={actual:.12f}, "
                    f"expected={expected:.12f}, "
                    f"difference="
                    f"{actual - expected:.12f}"
                )

        # ---------------------------------------------------------------
        # Statewide residual identity
        #
        # This is a statewide accounting control, NOT the sum of the
        # 47 district net-incidence values.
        # ---------------------------------------------------------------

        statewide_accounting_net = (
            controls["benefits"]
            - controls["tax"]
        )

        if abs(
            statewide_accounting_net
            + controls["unallocated"]
        ) >= 0.01:
            raise AssertionError(
                f"FY{fiscal_year}: "
                "statewide residual identity failed."
            )

        # ---------------------------------------------------------------
        # Benefit redistribution still sums to zero across all 49 LDs
        # ---------------------------------------------------------------

        redistribution = math.fsum(
            r[
                "illustrative_minus_average_benefit"
            ]
            for r in year_rows
        )

        if abs(
            redistribution
        ) >= 0.01:
            raise AssertionError(
                f"FY{fiscal_year}: geographic "
                "benefit redistribution does not "
                "sum to zero."
            )

        # ---------------------------------------------------------------
        # For the 47 calculable districts, tax is identical in both
        # cases, so net-case difference must equal benefit-case difference.
        # ---------------------------------------------------------------

        for row in calculated_rows:

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
                    "case-difference identity failed."
                )


# ---------------------------------------------------------------------------
# Write output
# ---------------------------------------------------------------------------

def write_csv(rows):

    fieldnames = [
        "scenario_fy",
        "legislative_district",

        "tax_incidence_status",
        "net_incidence_status",

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

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

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

        for row in rows:

            output_row = dict(row)

            # Preserve unavailable numeric values as blank CSV cells.
            for field in [
                "tax_incidence_share",
                "estimated_tax_paid",
                "illustrative_net",
                "average_net",
                "illustrative_minus_average_net",
            ]:
                if output_row[field] is None:
                    output_row[field] = ""

            writer.writerow(
                output_row
            )


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_share_controls(
    original_totals,
):

    print()
    print("BENEFIT SOURCE SHARE CONTROLS")
    print("-" * 92)

    for name in [
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
        "Benefit source shares are normalized internally "
        "before application to exact statewide controls."
    )

    print(
        "Tax geography is NOT renormalized by the "
        "integrated model."
    )


def print_year_report(
    rows,
    fiscal_year,
):

    year_rows = [
        row
        for row in rows
        if row["scenario_fy"]
        == fiscal_year
    ]

    controls = SCENARIOS[
        fiscal_year
    ]

    calculated_rows = [
        row
        for row in year_rows
        if row["net_incidence_status"]
        == "CALCULATED"
    ]

    unavailable_rows = [
        row
        for row in year_rows
        if row["net_incidence_status"]
        == "TAX_INCIDENCE_UNAVAILABLE"
    ]

    print()
    print(
        f"FY{fiscal_year}"
    )
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

    statewide_accounting_net = (
        controls["benefits"]
        - controls["tax"]
    )

    print(
        f"Statewide accounting difference : "
        f"{money(statewide_accounting_net)}"
    )

    print()
    print("DISTRICT INCIDENCE COVERAGE")
    print("-" * 92)

    print(
        f"Benefit estimates available     : "
        f"{len(year_rows)} LDs"
    )

    print(
        f"Tax/net incidence calculable    : "
        f"{len(calculated_rows)} LDs"
    )

    print(
        f"Tax/net incidence unavailable   : "
        f"{len(unavailable_rows)} LDs "
        f"(LD14, LD29)"
    )

    positive = sum(
        1
        for row in calculated_rows
        if row["illustrative_net"] > 0
    )

    negative = sum(
        1
        for row in calculated_rows
        if row["illustrative_net"] < 0
    )

    zero = sum(
        1
        for row in calculated_rows
        if row["illustrative_net"] == 0
    )

    print()
    print("47-DISTRICT INCIDENCE SUMMARY")
    print("-" * 92)

    print(
        f"Illustrative positive-net LDs   : "
        f"{positive}"
    )

    print(
        f"Illustrative negative-net LDs   : "
        f"{negative}"
    )

    print(
        f"Illustrative zero-net LDs       : "
        f"{zero}"
    )

    print(
        "District net totals are not labeled "
        "as statewide accounting totals."
    )

    print()
    print(
        "ILLUSTRATIVE CASE — LARGEST POSITIVE NETS"
    )
    print("-" * 92)

    ranked = sorted(
        calculated_rows,
        key=lambda row:
            row["illustrative_net"],
        reverse=True,
    )

    for row in ranked[:10]:

        print(
            f"LD {row['legislative_district']:>2}: "
            f"net="
            f"{money(row['illustrative_net']):>18}  "
            f"benefits="
            f"{money(row['illustrative_benefit_total']):>18}  "
            f"tax="
            f"{money(row['estimated_tax_paid'])}"
        )

    print()
    print(
        "ILLUSTRATIVE CASE — LARGEST NEGATIVE NETS"
    )
    print("-" * 92)

    for row in reversed(
        ranked[-10:]
    ):

        print(
            f"LD {row['legislative_district']:>2}: "
            f"net="
            f"{money(row['illustrative_net']):>18}  "
            f"benefits="
            f"{money(row['illustrative_benefit_total']):>18}  "
            f"tax="
            f"{money(row['estimated_tax_paid'])}"
        )

    print()
    print(
        "LARGEST GEOGRAPHIC BENEFIT SHIFTS FROM 1/49"
    )
    print("-" * 92)

    shifts = sorted(
        year_rows,
        key=lambda row: abs(
            row[
                "illustrative_minus_average_benefit"
            ]
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

    print()
    print("TAX INCIDENCE UNAVAILABLE")
    print("-" * 92)

    for row in unavailable_rows:

        print(
            f"LD {row['legislative_district']:>2}: "
            f"benefits="
            f"{money(row['illustrative_benefit_total']):>18}  "
            "tax=N/A  net=N/A"
        )


def print_report(
    rows,
    original_totals,
):

    print()
    print(
        "INTEGRATED LEGISLATIVE-DISTRICT "
        "INCIDENCE MODEL v0.2"
    )
    print("=" * 92)

    print_share_controls(
        original_totals
    )

    for fiscal_year in [
        2029,
        2030,
    ]:

        print_year_report(
            rows,
            fiscal_year,
        )

    print()
    print("VALIDATION")
    print("=" * 92)

    print(
        "Rows                              : "
        "98 PASS"
    )

    print(
        "Legislative districts per year   : "
        "49 PASS"
    )

    print(
        "Benefit estimates per year        : "
        "49 PASS"
    )

    print(
        "Tax/net calculable per year       : "
        "47 PASS"
    )

    print(
        "LD14/LD29 tax and net             : "
        "N/A PASS"
    )

    print(
        "Tax statewide controls            : "
        "PASS"
    )

    print(
        "Five benefit statewide controls   : "
        "PASS"
    )

    print(
        "Average/Illustrative benefit total: "
        "IDENTICAL PASS"
    )

    print(
        "Geographic benefit redistribution : "
        "SUMS TO ZERO PASS"
    )

    print(
        "Statewide residual identity       : "
        "PASS"
    )

    print()
    print("INTERPRETATION")
    print("-" * 92)

    print(
        "Benefit geography is modeled for all "
        "49 legislative districts."
    )

    print(
        "Tax and net incidence are reported only "
        "for the 47 districts with observable "
        "source tax geography."
    )

    print(
        "LD14 and LD29 are retained in the benefit "
        "model but their tax and net incidence "
        "remain N/A."
    )

    print(
        "Average Case and Illustrative Case contain "
        "exactly the same statewide modeled benefit "
        "dollars."
    )

    print(
        "Their difference isolates geographic "
        "redistribution within the modeled "
        "benefit pool."
    )

    print(
        "The statewide accounting difference equals "
        "revenue not geographically allocated among "
        "the five modeled benefit categories."
    )

    print(
        "It must not be interpreted as the sum of "
        "the 47 calculable district net values."
    )

    print()
    print("OUTPUT")
    print("-" * 92)

    print(
        OUTPUT_FILE
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():

    (
        benefit_shares,
        original_totals,
    ) = load_benefit_geographic_shares()

    tax_geography = (
        load_tax_geography()
    )

    rows = build_rows(
        benefit_shares,
        tax_geography,
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