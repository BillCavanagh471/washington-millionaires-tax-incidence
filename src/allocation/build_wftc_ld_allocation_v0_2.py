import csv
import json
from pathlib import Path


ROOT = Path(".")
CENSUS_DIR = ROOT / "data" / "raw" / "census"
OUTPUT_DIR = ROOT / "data" / "processed" / "model"

INCOME_FILE = (
    CENSUS_DIR / "acs2024_wa_ld_household_income.csv"
)
FAMILY_FILE = (
    CENSUS_DIR / "acs2024_wa_ld_family_children.csv"
)
MEDIAN_FILE = (
    CENSUS_DIR / "acs2024_wa_ld_median_household_income.csv"
)
FAMILY_RAW = (
    CENSUS_DIR / "acs2024_wa_ld_family_children_raw.json"
)

OUTPUT_FILE = OUTPUT_DIR / "wftc_ld_allocation_v0_2.csv"
COMPARISON_FILE = OUTPUT_DIR / "wftc_ld_v0_1_vs_v0_2.csv"

# Official DOR statewide geographic control.
WFTC_ASSIGNED = 278_574


# B19001 household income bands.
#
# This is intentionally an illustrative propensity score, NOT an
# estimate of legal WFTC eligibility.
#
# Lower-income bands receive higher propensity weights.
# Bands above $75,000 receive zero weight in v0.2.
#
# These assumptions are deliberately visible and replaceable.
INCOME_WEIGHTS = {
    "B19001_002E": 1.00,  # < $10,000
    "B19001_003E": 1.00,  # $10,000-$14,999
    "B19001_004E": 1.00,  # $15,000-$19,999
    "B19001_005E": 1.00,  # $20,000-$24,999
    "B19001_006E": 1.00,  # $25,000-$29,999
    "B19001_007E": 0.90,  # $30,000-$34,999
    "B19001_008E": 0.80,  # $35,000-$39,999
    "B19001_009E": 0.70,  # $40,000-$44,999
    "B19001_010E": 0.60,  # $45,000-$49,999
    "B19001_011E": 0.45,  # $50,000-$59,999
    "B19001_012E": 0.25,  # $60,000-$74,999
}


def read_csv(path):
    with path.open(
        "r",
        newline="",
        encoding="utf-8",
    ) as f:
        return list(csv.DictReader(f))


def load_family_labels():
    """
    Read Census metadata preserved during acquisition and return
    variable -> Census label.
    """
    with FAMILY_RAW.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    variables = raw["metadata"]["variables"]

    return {
        variable: details.get("label", "")
        for variable, details in variables.items()
    }


def identify_family_variables(labels):
    """
    Select leaf-level B17010 estimates representing families with
    related children under 18.

    We avoid subtotal variables so the same family is not counted
    multiple times.
    """
    selected = []

    age_leaf_phrases = (
        "Under 5 years only",
        "Under 5 years and 5 to 17 years",
        "5 to 17 years only",
    )

    for variable, label in labels.items():

        if not variable.startswith("B17010_"):
            continue

        if not variable.endswith("E"):
            continue

        if not any(
            phrase in label
            for phrase in age_leaf_phrases
        ):
            continue

        if (
            "With related children of the householder "
            "under 18 years"
        ) not in label:
            continue

        selected.append(variable)

    return sorted(selected)


def main():

    income_rows = read_csv(INCOME_FILE)
    family_rows = read_csv(FAMILY_FILE)
    median_rows = read_csv(MEDIAN_FILE)

    if not (
        len(income_rows)
        == len(family_rows)
        == len(median_rows)
        == 49
    ):
        raise RuntimeError(
            "Expected 49 legislative districts in all inputs."
        )

    income = {
        int(r["legislative_district"]): r
        for r in income_rows
    }

    family = {
        int(r["legislative_district"]): r
        for r in family_rows
    }

    median = {
        int(r["legislative_district"]): r
        for r in median_rows
    }

    labels = load_family_labels()
    child_variables = identify_family_variables(labels)

    print("WFTC LD ALLOCATION MODEL v0.2")
    print("=" * 72)
    print()
    print(
        f"B17010 child-family leaf variables selected: "
        f"{len(child_variables)}"
    )

    if not child_variables:
        raise RuntimeError(
            "No B17010 child-family leaf variables identified."
        )

    model = []

    for ld in range(1, 50):

        inc = income[ld]
        fam = family[ld]
        med = median[ld]

        households = int(inc["B19001_001E"])

        income_score = sum(
            int(inc[var]) * weight
            for var, weight in INCOME_WEIGHTS.items()
        )

        families_total = int(fam["B17010_001E"])

        families_with_children = sum(
            int(fam[var])
            for var in child_variables
        )

        if families_total > 0:
            child_family_share = (
                families_with_children / families_total
            )
        else:
            child_family_share = 0.0

        #
        # Modest adjustment:
        #
        # A district at 30% families-with-children receives
        # factor 1.30.
        #
        # This prevents the family variable from overwhelming
        # the much more direct income-distribution signal.
        #
        child_adjustment = 1.0 + child_family_share

        combined_weight = (
            income_score * child_adjustment
        )

        # v0.1 reconstruction:
        #
        # Earlier v0.1 used population / median income.
        # The working spreadsheet population was 157,251 for
        # every LD, so relative weights reduce to 1 / median.
        #
        median_income = int(
            med["median_household_income"]
        )

        v01_weight = 1.0 / median_income

        model.append(
            {
                "legislative_district": ld,
                "households": households,
                "median_household_income": median_income,
                "income_propensity_score": income_score,
                "families_total": families_total,
                "families_with_children_proxy":
                    families_with_children,
                "child_family_share": child_family_share,
                "child_adjustment": child_adjustment,
                "combined_wftc_weight": combined_weight,
                "v01_weight": v01_weight,
            }
        )

    total_weight = sum(
        r["combined_wftc_weight"]
        for r in model
    )

    total_v01_weight = sum(
        r["v01_weight"]
        for r in model
    )

    for r in model:

        r["share_of_statewide_wftc"] = (
            r["combined_wftc_weight"]
            / total_weight
        )

        r["estimated_wftc_approvals_v02"] = (
            WFTC_ASSIGNED
            * r["share_of_statewide_wftc"]
        )

        r["estimated_wftc_approvals_v01"] = (
            WFTC_ASSIGNED
            * r["v01_weight"]
            / total_v01_weight
        )

        r["change_v02_minus_v01"] = (
            r["estimated_wftc_approvals_v02"]
            - r["estimated_wftc_approvals_v01"]
        )

        r["percent_change_from_v01"] = (
            r["change_v02_minus_v01"]
            / r["estimated_wftc_approvals_v01"]
        )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    fields = [
        "legislative_district",
        "households",
        "median_household_income",
        "income_propensity_score",
        "families_total",
        "families_with_children_proxy",
        "child_family_share",
        "child_adjustment",
        "combined_wftc_weight",
        "share_of_statewide_wftc",
        "estimated_wftc_approvals_v02",
    ]

    with OUTPUT_FILE.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fields,
        )

        writer.writeheader()

        for r in model:
            writer.writerow(
                {
                    field: r[field]
                    for field in fields
                }
            )

    comparison_fields = [
        "legislative_district",
        "estimated_wftc_approvals_v01",
        "estimated_wftc_approvals_v02",
        "change_v02_minus_v01",
        "percent_change_from_v01",
    ]

    with COMPARISON_FILE.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=comparison_fields,
        )

        writer.writeheader()

        for r in model:
            writer.writerow(
                {
                    field: r[field]
                    for field in comparison_fields
                }
            )

    total_v02 = sum(
        r["estimated_wftc_approvals_v02"]
        for r in model
    )

    total_v01 = sum(
        r["estimated_wftc_approvals_v01"]
        for r in model
    )

    print()
    print("STATEWIDE RECONCILIATION")
    print("-" * 72)
    print(
        f"DOR geographic control : "
        f"{WFTC_ASSIGNED:,.0f}"
    )
    print(
        f"v0.1 reconstructed     : "
        f"{total_v01:,.6f}"
    )
    print(
        f"v0.2 modeled           : "
        f"{total_v02:,.6f}"
    )

    print()
    print("LARGEST ABSOLUTE CHANGES FROM v0.1")
    print("-" * 72)

    largest = sorted(
        model,
        key=lambda r: abs(
            r["change_v02_minus_v01"]
        ),
        reverse=True,
    )[:10]

    for r in largest:
        print(
            f"LD {r['legislative_district']:>2}: "
            f"v0.1 "
            f"{r['estimated_wftc_approvals_v01']:>8,.0f}  "
            f"v0.2 "
            f"{r['estimated_wftc_approvals_v02']:>8,.0f}  "
            f"change "
            f"{r['change_v02_minus_v01']:>+8,.0f} "
            f"({r['percent_change_from_v01']:+.1%})"
        )

    print()
    print("TOP 10 v0.2 WFTC INCIDENCE")
    print("-" * 72)

    top = sorted(
        model,
        key=lambda r:
            r["estimated_wftc_approvals_v02"],
        reverse=True,
    )[:10]

    for r in top:
        print(
            f"LD {r['legislative_district']:>2}: "
            f"{r['estimated_wftc_approvals_v02']:,.0f}"
        )

    print()
    print("Output:")
    print(f"  {OUTPUT_FILE}")
    print(f"  {COMPARISON_FILE}")


if __name__ == "__main__":
    main()