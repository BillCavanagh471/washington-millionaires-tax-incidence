import csv
from pathlib import Path


MODEL_FILE = Path(
    "data/processed/model/wftc_ld_allocation_v0_2.csv"
)

OUTPUT_DIR = Path("data/processed/validation")
OUTPUT_FILE = OUTPUT_DIR / "wftc_dor_county_benchmark_v0_1.csv"

ASSIGNED_CONTROL = 278_574

# Official Washington DOR TY2024 WFTC approved applications
# assigned to a county.
DOR_COUNTY = {
    "Adams": 1709,
    "Asotin": 880,
    "Benton": 10507,
    "Chelan": 4112,
    "Clallam": 2685,
    "Clark": 17911,
    "Columbia": 178,
    "Cowlitz": 5283,
    "Douglas": 2454,
    "Ferry": 314,
    "Franklin": 6530,
    "Garfield": 81,
    "Grant": 7138,
    "Grays Harbor": 3463,
    "Island": 2188,
    "Jefferson": 934,
    "King": 60251,
    "Kitsap": 7486,
    "Kittitas": 1338,
    "Klickitat": 717,
    "Lewis": 3777,
    "Lincoln": 379,
    "Mason": 2623,
    "Okanogan": 2257,
    "Pacific": 836,
    "Pend Oreille": 621,
    "Pierce": 34238,
    "San Juan": 474,
    "Skagit": 5002,
    "Skamania": 354,
    "Snohomish": 22966,
    "Spokane": 24420,
    "Stevens": 2017,
    "Thurston": 9930,
    "Wahkiakum": 142,
    "Walla Walla": 2549,
    "Whatcom": 7375,
    "Whitman": 1263,
    "Yakima": 21192,
}

# Broad LD groupings used ONLY as a geographic plausibility check.
#
# These are intentionally NOT a county-to-LD allocation crosswalk.
# Legislative districts cross county boundaries, so do not interpret
# the resulting comparisons as reconciled county estimates.
REGIONAL_CHECKS = {
    "Spokane concentration": {
        "counties": ["Spokane"],
        "lds": [3, 4, 6, 7],
    },
    "Yakima concentration": {
        "counties": ["Yakima"],
        "lds": [14, 15],
    },
    "Clark concentration": {
        "counties": ["Clark"],
        "lds": [17, 18, 20, 49],
    },
    "Pierce concentration": {
        "counties": ["Pierce"],
        "lds": [2, 25, 27, 28, 29, 31],
    },
    "Snohomish concentration": {
        "counties": ["Snohomish"],
        "lds": [1, 10, 21, 32, 38, 39, 44],
    },
    "King concentration": {
        "counties": ["King"],
        "lds": [1, 5, 11, 30, 31, 32, 33, 34, 36, 37,
                41, 43, 45, 46, 47, 48],
    },
}


def read_model():
    with MODEL_FILE.open(
        "r",
        newline="",
        encoding="utf-8",
    ) as f:
        rows = list(csv.DictReader(f))

    return {
        int(r["legislative_district"]):
        float(r["estimated_wftc_approvals_v02"])
        for r in rows
    }


def main():

    model = read_model()

    if len(model) != 49:
        raise RuntimeError(
            f"Expected 49 LDs; received {len(model)}."
        )

    dor_total = sum(DOR_COUNTY.values())

    print("WFTC DOR COUNTY BENCHMARK v0.1")
    print("=" * 78)
    print()
    print("CONTROL CHECK")
    print("-" * 78)
    print(
        f"DOR assigned county approvals : "
        f"{dor_total:,}"
    )
    print(
        f"Expected control              : "
        f"{ASSIGNED_CONTROL:,}"
    )

    if dor_total != ASSIGNED_CONTROL:
        raise RuntimeError(
            "DOR county counts do not reconcile "
            "to assigned control."
        )

    print()
    print("TOP DOR COUNTIES")
    print("-" * 78)

    ranked = sorted(
        DOR_COUNTY.items(),
        key=lambda x: x[1],
        reverse=True,
    )

    for county, count in ranked[:10]:
        share = count / ASSIGNED_CONTROL
        print(
            f"{county:<15} "
            f"{count:>8,}   "
            f"{share:>6.2%}"
        )

    print()
    print("REGIONAL PLAUSIBILITY CHECK")
    print("-" * 78)
    print(
        "NOTE: LD groups overlap county boundaries. "
        "These are pattern checks, not reconciliations."
    )
    print()

    output_rows = []

    for name, spec in REGIONAL_CHECKS.items():

        dor_count = sum(
            DOR_COUNTY[c]
            for c in spec["counties"]
        )

        modeled_count = sum(
            model[ld]
            for ld in spec["lds"]
        )

        dor_share = (
            dor_count / ASSIGNED_CONTROL
        )

        modeled_share = (
            modeled_count / ASSIGNED_CONTROL
        )

        difference_pp = (
            modeled_share - dor_share
        ) * 100

        print(name)
        print(
            f"  DOR county approvals : "
            f"{dor_count:>8,.0f} "
            f"({dor_share:>6.2%})"
        )
        print(
            f"  LD proxy approvals   : "
            f"{modeled_count:>8,.0f} "
            f"({modeled_share:>6.2%})"
        )
        print(
            f"  Difference           : "
            f"{difference_pp:>+6.2f} percentage points"
        )
        print(
            f"  LDs                  : "
            + ", ".join(
                str(ld)
                for ld in spec["lds"]
            )
        )
        print()

        output_rows.append(
            {
                "regional_check": name,
                "dor_counties":
                    "; ".join(spec["counties"]),
                "legislative_districts":
                    "; ".join(
                        str(ld)
                        for ld in spec["lds"]
                    ),
                "dor_approvals": dor_count,
                "dor_share":
                    dor_share,
                "ld_proxy_approvals":
                    modeled_count,
                "ld_proxy_share":
                    modeled_share,
                "difference_percentage_points":
                    difference_pp,
            }
        )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    fields = [
        "regional_check",
        "dor_counties",
        "legislative_districts",
        "dor_approvals",
        "dor_share",
        "ld_proxy_approvals",
        "ld_proxy_share",
        "difference_percentage_points",
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
        writer.writerows(output_rows)

    print("-" * 78)
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()