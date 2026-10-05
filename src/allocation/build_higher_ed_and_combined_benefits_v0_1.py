from pathlib import Path
import csv


HIGHER_ED_INPUT = Path(
    "data/raw/census/acs2024_wa_ld_higher_ed.csv"
)

EXISTING_INPUT = Path(
    "data/processed/model/illustrative_benefit_components_v0_2.csv"
)

OUTPUT_DIR = Path("data/processed/model")

HIGHER_ED_OUTPUT = (
    OUTPUT_DIR / "higher_ed_ld_allocation_v0_1.csv"
)

COMBINED_OUTPUT = (
    OUTPUT_DIR / "illustrative_benefit_components_v0_3.csv"
)


EXPECTED_LDS = 49
PUBLIC_HIGHER_ED_CONTROL = 346_210

HIGHER_ED_LOW_POOL = 250_000_000
HIGHER_ED_CENTRAL_POOL = 400_000_000
HIGHER_ED_HIGH_POOL = 550_000_000

WFTC_CENTRAL_POOL = 250_000_000
K12_CENTRAL_POOL = 1_000_000_000
HEALTH_CENTRAL_POOL = 750_000_000

COMBINED_CENTRAL_POOL = (
    WFTC_CENTRAL_POOL
    + K12_CENTRAL_POOL
    + HEALTH_CENTRAL_POOL
    + HIGHER_ED_CENTRAL_POOL
)


def money(value):
    return round(value, 2)


def load_csv(path):

    if not path.exists():
        raise FileNotFoundError(
            f"Input not found: {path}"
        )

    with path.open(
        newline="",
        encoding="utf-8",
    ) as f:

        reader = csv.DictReader(f)
        rows = list(reader)

    return rows


def main():

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    higher_ed_rows = load_csv(
        HIGHER_ED_INPUT
    )

    existing_rows = load_csv(
        EXISTING_INPUT
    )

    # ------------------------------------------------------------
    # Basic validation.
    # ------------------------------------------------------------

    if len(higher_ed_rows) != EXPECTED_LDS:
        raise RuntimeError(
            f"Expected {EXPECTED_LDS} higher-ed rows; "
            f"found {len(higher_ed_rows)}."
        )

    if len(existing_rows) != EXPECTED_LDS:
        raise RuntimeError(
            f"Expected {EXPECTED_LDS} existing-model rows; "
            f"found {len(existing_rows)}."
        )

    # ------------------------------------------------------------
    # Index higher-ed geography.
    # ------------------------------------------------------------

    higher_ed_by_ld = {}

    for row in higher_ed_rows:

        ld = int(
            row["legislative_district"]
        )

        public_enrollment = int(
            row[
                "public_higher_ed_enrollment_estimate"
            ]
        )

        public_share = float(
            row[
                "public_higher_ed_ld_share"
            ]
        )

        if ld in higher_ed_by_ld:
            raise RuntimeError(
                f"Duplicate higher-ed LD {ld}."
            )

        higher_ed_by_ld[ld] = {
            "public_enrollment":
                public_enrollment,
            "public_share":
                public_share,
        }

    # ------------------------------------------------------------
    # Index existing three-component model.
    # ------------------------------------------------------------

    existing_by_ld = {}

    for row in existing_rows:

        ld = int(
            row["legislative_district"]
        )

        if ld in existing_by_ld:
            raise RuntimeError(
                f"Duplicate existing-model LD {ld}."
            )

        existing_by_ld[ld] = row

    expected_lds = set(range(1, 50))

    if set(higher_ed_by_ld) != expected_lds:
        raise RuntimeError(
            "Higher-ed districts are not exactly 1-49."
        )

    if set(existing_by_ld) != expected_lds:
        raise RuntimeError(
            "Existing-model districts are not exactly 1-49."
        )

    # ------------------------------------------------------------
    # Validate statewide public higher-ed control.
    # ------------------------------------------------------------

    observed_control = sum(
        item["public_enrollment"]
        for item in higher_ed_by_ld.values()
    )

    if observed_control != PUBLIC_HIGHER_ED_CONTROL:
        raise RuntimeError(
            "Public higher-ed statewide control mismatch. "
            f"Expected {PUBLIC_HIGHER_ED_CONTROL:,}; "
            f"found {observed_control:,}."
        )

    # ------------------------------------------------------------
    # Build standalone higher-ed allocation.
    # ------------------------------------------------------------

    equal_low = (
        HIGHER_ED_LOW_POOL / EXPECTED_LDS
    )

    equal_central = (
        HIGHER_ED_CENTRAL_POOL / EXPECTED_LDS
    )

    equal_high = (
        HIGHER_ED_HIGH_POOL / EXPECTED_LDS
    )

    allocation_rows = []

    for ld in range(1, 50):

        item = higher_ed_by_ld[ld]

        share = item["public_share"]

        low = (
            HIGHER_ED_LOW_POOL * share
        )

        central = (
            HIGHER_ED_CENTRAL_POOL * share
        )

        high = (
            HIGHER_ED_HIGH_POOL * share
        )

        allocation_rows.append(
            {
                "legislative_district": ld,

                "public_higher_ed_enrollment_estimate":
                    item["public_enrollment"],

                "public_higher_ed_share":
                    share,

                "higher_ed_low_250m":
                    money(low),

                "higher_ed_central_400m":
                    money(central),

                "higher_ed_high_550m":
                    money(high),

                "equal_higher_ed_low_250m":
                    money(equal_low),

                "equal_higher_ed_central_400m":
                    money(equal_central),

                "equal_higher_ed_high_550m":
                    money(equal_high),

                "higher_ed_central_difference_from_equal":
                    money(
                        central - equal_central
                    ),

                "higher_ed_central_ratio_to_equal":
                    central / equal_central,
            }
        )

    # ------------------------------------------------------------
    # Write standalone higher-ed model.
    # ------------------------------------------------------------

    with HIGHER_ED_OUTPUT.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=list(
                allocation_rows[0].keys()
            ),
        )

        writer.writeheader()
        writer.writerows(
            allocation_rows
        )

    higher_ed_allocation_by_ld = {
        row["legislative_district"]: row
        for row in allocation_rows
    }

    # ------------------------------------------------------------
    # Build four-component central model.
    # ------------------------------------------------------------

    equal_combined = (
        COMBINED_CENTRAL_POOL
        / EXPECTED_LDS
    )

    combined_rows = []

    for ld in range(1, 50):

        old = existing_by_ld[ld]
        he = higher_ed_allocation_by_ld[ld]

        wftc = float(
            old["wftc_central_250m"]
        )

        k12 = float(
            old["k12_central_1b"]
        )

        health = float(
            old["health_central_750m"]
        )

        higher_ed = float(
            he["higher_ed_central_400m"]
        )

        combined = (
            wftc
            + k12
            + health
            + higher_ed
        )

        combined_share = (
            combined
            / COMBINED_CENTRAL_POOL
        )

        difference = (
            combined
            - equal_combined
        )

        combined_rows.append(
            {
                "legislative_district":
                    ld,

                "wftc_central_250m":
                    money(wftc),

                "k12_central_1b":
                    money(k12),

                "health_central_750m":
                    money(health),

                "public_higher_ed_enrollment":
                    he[
                        "public_higher_ed_enrollment_estimate"
                    ],

                "higher_ed_central_400m":
                    money(higher_ed),

                "combined_wftc_k12_health_higher_ed":
                    money(combined),

                "combined_share":
                    combined_share,

                "equal_combined_2_4b":
                    money(equal_combined),

                "difference_from_equal":
                    money(difference),

                "ratio_to_equal":
                    combined / equal_combined,
            }
        )

    # ------------------------------------------------------------
    # Write combined model.
    # ------------------------------------------------------------

    with COMBINED_OUTPUT.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=list(
                combined_rows[0].keys()
            ),
        )

        writer.writeheader()
        writer.writerows(
            combined_rows
        )

    # ------------------------------------------------------------
    # Validation.
    # ------------------------------------------------------------

    share_sum = sum(
        row["public_higher_ed_share"]
        for row in allocation_rows
    )

    low_total = sum(
        row["higher_ed_low_250m"]
        for row in allocation_rows
    )

    central_total = sum(
        row["higher_ed_central_400m"]
        for row in allocation_rows
    )

    high_total = sum(
        row["higher_ed_high_550m"]
        for row in allocation_rows
    )

    wftc_total = sum(
        row["wftc_central_250m"]
        for row in combined_rows
    )

    k12_total = sum(
        row["k12_central_1b"]
        for row in combined_rows
    )

    health_total = sum(
        row["health_central_750m"]
        for row in combined_rows
    )

    he_total = sum(
        row["higher_ed_central_400m"]
        for row in combined_rows
    )

    combined_total = sum(
        row[
            "combined_wftc_k12_health_higher_ed"
        ]
        for row in combined_rows
    )

    combined_share_sum = sum(
        row["combined_share"]
        for row in combined_rows
    )

    difference_total = sum(
        row["difference_from_equal"]
        for row in combined_rows
    )

    print(
        "HIGHER EDUCATION + FOUR-COMPONENT "
        "ILLUSTRATIVE BENEFIT MODEL v0.1"
    )
    print("=" * 80)

    print()
    print("HIGHER EDUCATION MODEL")
    print("-" * 80)

    print(
        "Geography : 2024 ACS 5-Year B14004 "
        "public college / graduate enrollment"
    )

    print(
        "Use       : relative geographic "
        "allocation weights by residence"
    )

    print("Low pool  : $250,000,000")
    print("Central   : $400,000,000")
    print("High pool : $550,000,000")

    print()
    print("HIGHER EDUCATION CONTROLS")
    print("-" * 80)

    print(
        f"Legislative districts       : "
        f"{len(allocation_rows)}"
    )

    print(
        f"Public enrollment control   : "
        f"{observed_control:,}"
    )

    print(
        f"Public LD share sum         : "
        f"{share_sum:.12f}"
    )

    print(
        f"Low allocation total        : "
        f"${low_total:,.2f}"
    )

    print(
        f"Central allocation total    : "
        f"${central_total:,.2f}"
    )

    print(
        f"High allocation total       : "
        f"${high_total:,.2f}"
    )

    print()
    print("FOUR-COMPONENT CENTRAL MODEL")
    print("-" * 80)

    print(
        f"WFTC                       : "
        f"${wftc_total:,.2f}"
    )

    print(
        f"K-12                       : "
        f"${k12_total:,.2f}"
    )

    print(
        f"Health                     : "
        f"${health_total:,.2f}"
    )

    print(
        f"Higher education           : "
        f"${he_total:,.2f}"
    )

    print(
        f"Combined                   : "
        f"${combined_total:,.2f}"
    )

    print(
        f"Combined share sum         : "
        f"{combined_share_sum:.12f}"
    )

    print(
        f"Difference-from-equal sum  : "
        f"${difference_total:,.2f}"
    )

    print()
    print("LARGEST ABOVE EQUAL SHARE")
    print("-" * 80)

    for row in sorted(
        combined_rows,
        key=lambda x:
            x["difference_from_equal"],
        reverse=True,
    )[:10]:

        print(
            f"LD {row['legislative_district']:>2}: "
            f"WFTC=${row['wftc_central_250m']:>11,.2f}  "
            f"K12=${row['k12_central_1b']:>12,.2f}  "
            f"Health=${row['health_central_750m']:>12,.2f}  "
            f"HigherEd=${row['higher_ed_central_400m']:>11,.2f}  "
            f"Total=${row['combined_wftc_k12_health_higher_ed']:>12,.2f}  "
            f"vs equal=${row['difference_from_equal']:>+12,.2f}"
        )

    print()
    print("LARGEST BELOW EQUAL SHARE")
    print("-" * 80)

    for row in sorted(
        combined_rows,
        key=lambda x:
            x["difference_from_equal"],
    )[:10]:

        print(
            f"LD {row['legislative_district']:>2}: "
            f"WFTC=${row['wftc_central_250m']:>11,.2f}  "
            f"K12=${row['k12_central_1b']:>12,.2f}  "
            f"Health=${row['health_central_750m']:>12,.2f}  "
            f"HigherEd=${row['higher_ed_central_400m']:>11,.2f}  "
            f"Total=${row['combined_wftc_k12_health_higher_ed']:>12,.2f}  "
            f"vs equal=${row['difference_from_equal']:>+12,.2f}"
        )

    print()
    print("OUTPUT")
    print("-" * 80)

    print(HIGHER_ED_OUTPUT)
    print(COMBINED_OUTPUT)


if __name__ == "__main__":
    main()