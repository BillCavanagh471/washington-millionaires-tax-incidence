from pathlib import Path
import csv


INPUT = Path(
    "data/raw/census/acs2024_wa_ld_public_k12.csv"
)

OUTPUT_DIR = Path("data/processed/model")
OUTPUT = OUTPUT_DIR / "k12_ld_allocation_v0_1.csv"

LOW_POOL = 750_000_000
CENTRAL_POOL = 1_000_000_000
HIGH_POOL = 1_250_000_000

EXPECTED_LDS = 49
EXPECTED_STATEWIDE_ENROLLMENT = 1_068_720


def money(value):
    return round(value, 2)


def main():

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not INPUT.exists():
        raise FileNotFoundError(
            f"Input not found: {INPUT}"
        )

    with INPUT.open(
        newline="",
        encoding="utf-8",
    ) as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if len(rows) != EXPECTED_LDS:
        raise RuntimeError(
            f"Expected {EXPECTED_LDS} legislative districts; "
            f"found {len(rows)}."
        )

    # ------------------------------------------------------------
    # Read and validate Census enrollment.
    # ------------------------------------------------------------

    clean = []

    for row in rows:

        ld = int(row["legislative_district"])

        enrollment = int(
            row["public_k12_enrollment_estimate"]
        )

        clean.append(
            {
                "legislative_district": ld,
                "census_name": row["census_name"],
                "public_k12_enrollment_estimate": enrollment,
            }
        )

    clean.sort(
        key=lambda x: x["legislative_district"]
    )

    expected_ld_numbers = list(range(1, 50))
    actual_ld_numbers = [
        row["legislative_district"]
        for row in clean
    ]

    if actual_ld_numbers != expected_ld_numbers:
        raise RuntimeError(
            "Legislative districts are not exactly 1 through 49."
        )

    statewide_enrollment = sum(
        row["public_k12_enrollment_estimate"]
        for row in clean
    )

    if statewide_enrollment != EXPECTED_STATEWIDE_ENROLLMENT:
        raise RuntimeError(
            "Statewide enrollment does not match the "
            f"previously validated control. Expected "
            f"{EXPECTED_STATEWIDE_ENROLLMENT:,}; found "
            f"{statewide_enrollment:,}."
        )

    # ------------------------------------------------------------
    # Equal-share benchmark.
    # ------------------------------------------------------------

    equal_share = 1 / EXPECTED_LDS

    equal_low = LOW_POOL / EXPECTED_LDS
    equal_central = CENTRAL_POOL / EXPECTED_LDS
    equal_high = HIGH_POOL / EXPECTED_LDS

    # ------------------------------------------------------------
    # Geographic allocation.
    # ------------------------------------------------------------

    output_rows = []

    for row in clean:

        enrollment = row[
            "public_k12_enrollment_estimate"
        ]

        share = (
            enrollment / statewide_enrollment
        )

        low = LOW_POOL * share
        central = CENTRAL_POOL * share
        high = HIGH_POOL * share

        output_rows.append(
            {
                "legislative_district":
                    row["legislative_district"],

                "census_name":
                    row["census_name"],

                "public_k12_enrollment_estimate":
                    enrollment,

                "public_k12_share":
                    share,

                "equal_share_1_of_49":
                    equal_share,

                "k12_low_750m":
                    money(low),

                "k12_central_1b":
                    money(central),

                "k12_high_1_25b":
                    money(high),

                "equal_low_750m":
                    money(equal_low),

                "equal_central_1b":
                    money(equal_central),

                "equal_high_1_25b":
                    money(equal_high),

                "central_difference_from_equal":
                    money(
                        central - equal_central
                    ),

                "central_ratio_to_equal":
                    (
                        central / equal_central
                        if equal_central
                        else 0
                    ),
            }
        )

    # ------------------------------------------------------------
    # Write output.
    # ------------------------------------------------------------

    fieldnames = list(
        output_rows[0].keys()
    )

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
        writer.writerows(output_rows)

    # ------------------------------------------------------------
    # Validation.
    # ------------------------------------------------------------

    share_sum = sum(
        row["public_k12_share"]
        for row in output_rows
    )

    low_sum = sum(
        row["k12_low_750m"]
        for row in output_rows
    )

    central_sum = sum(
        row["k12_central_1b"]
        for row in output_rows
    )

    high_sum = sum(
        row["k12_high_1_25b"]
        for row in output_rows
    )

    difference_sum = sum(
        row["central_difference_from_equal"]
        for row in output_rows
    )

    print("K-12 LD ALLOCATION v0.1")
    print("=" * 80)

    print()
    print("MODEL")
    print("-" * 80)
    print(
        "Geography : 2024 ACS 5-Year public K-12 "
        "enrollment by WA legislative district"
    )
    print(
        "Method    : proportional allocation by "
        "resident public K-12 enrollment"
    )
    print(
        "Purpose   : illustrative geographic benefit "
        "allocation; not an enacted appropriation"
    )

    print()
    print("CONTROLS")
    print("-" * 80)
    print(
        f"Legislative districts       : "
        f"{len(output_rows)}"
    )
    print(
        f"Statewide ACS enrollment    : "
        f"{statewide_enrollment:,}"
    )
    print(
        f"LD share sum                : "
        f"{share_sum:.12f}"
    )
    print(
        f"Low allocation total        : "
        f"${low_sum:,.2f}"
    )
    print(
        f"Central allocation total    : "
        f"${central_sum:,.2f}"
    )
    print(
        f"High allocation total       : "
        f"${high_sum:,.2f}"
    )
    print(
        f"Central difference sum      : "
        f"${difference_sum:,.2f}"
    )

    print()
    print("CENTRAL CASE — LARGEST ABOVE EQUAL SHARE")
    print("-" * 80)

    for row in sorted(
        output_rows,
        key=lambda x:
            x["central_difference_from_equal"],
        reverse=True,
    )[:10]:

        print(
            f"LD {row['legislative_district']:>2}: "
            f"students={row['public_k12_enrollment_estimate']:>7,}  "
            f"share={row['public_k12_share']:>6.2%}  "
            f"K12=${row['k12_central_1b']:>13,.2f}  "
            f"vs equal="
            f"${row['central_difference_from_equal']:>+13,.2f}"
        )

    print()
    print("CENTRAL CASE — LARGEST BELOW EQUAL SHARE")
    print("-" * 80)

    for row in sorted(
        output_rows,
        key=lambda x:
            x["central_difference_from_equal"],
    )[:10]:

        print(
            f"LD {row['legislative_district']:>2}: "
            f"students={row['public_k12_enrollment_estimate']:>7,}  "
            f"share={row['public_k12_share']:>6.2%}  "
            f"K12=${row['k12_central_1b']:>13,.2f}  "
            f"vs equal="
            f"${row['central_difference_from_equal']:>+13,.2f}"
        )

    print()
    print("OUTPUT")
    print("-" * 80)
    print(OUTPUT)


if __name__ == "__main__":
    main()