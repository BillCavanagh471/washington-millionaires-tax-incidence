from pathlib import Path
import csv


WFTC_INPUT = Path(
    "data/processed/model/wftc_ld_allocation_v0_2.csv"
)

K12_INPUT = Path(
    "data/processed/model/k12_ld_allocation_v0_1.csv"
)

OUTPUT_DIR = Path("data/processed/model")
OUTPUT = OUTPUT_DIR / "illustrative_benefit_components_v0_1.csv"

EXPECTED_LDS = 49

WFTC_POOL = 250_000_000
K12_POOL = 1_000_000_000
COMBINED_POOL = WFTC_POOL + K12_POOL

WFTC_CONTROL = 278_574


def money(value):
    return round(value, 2)


def detect_column(fieldnames, candidates, description):
    """
    Find a column using a short list of acceptable names.

    This makes the join tolerant of minor naming differences in the
    already-generated WFTC v0.2 file.
    """
    for candidate in candidates:
        if candidate in fieldnames:
            return candidate

    raise RuntimeError(
        f"Could not identify {description} column.\n"
        f"Expected one of: {candidates}\n"
        f"Available columns: {fieldnames}"
    )


def load_csv(path):
    if not path.exists():
        raise FileNotFoundError(f"Input not found: {path}")

    with path.open(
        newline="",
        encoding="utf-8",
    ) as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames

    return rows, fieldnames


def main():

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------
    # Load source models.
    # ------------------------------------------------------------

    wftc_rows, wftc_fields = load_csv(WFTC_INPUT)
    k12_rows, k12_fields = load_csv(K12_INPUT)

    if len(wftc_rows) != EXPECTED_LDS:
        raise RuntimeError(
            f"WFTC input expected {EXPECTED_LDS} rows; "
            f"found {len(wftc_rows)}."
        )

    if len(k12_rows) != EXPECTED_LDS:
        raise RuntimeError(
            f"K-12 input expected {EXPECTED_LDS} rows; "
            f"found {len(k12_rows)}."
        )

    # ------------------------------------------------------------
    # Detect required WFTC columns.
    # ------------------------------------------------------------

    wftc_ld_col = detect_column(
        wftc_fields,
        [
            "legislative_district",
            "ld",
            "district",
        ],
        "WFTC legislative district",
    )

    wftc_approval_col = detect_column(
        wftc_fields,
        [
            "estimated_wftc_approvals_v02",
            "estimated_wftc_approvals",
            "estimated_approvals_v02",
            "estimated_approvals",
            "wftc_v02",
        ],
        "WFTC v0.2 approvals",
    )

    # ------------------------------------------------------------
    # Detect required K-12 columns.
    # ------------------------------------------------------------

    k12_ld_col = detect_column(
        k12_fields,
        [
            "legislative_district",
            "ld",
            "district",
        ],
        "K-12 legislative district",
    )

    k12_enrollment_col = detect_column(
        k12_fields,
        [
            "public_k12_enrollment_estimate",
            "public_k12_enrollment",
        ],
        "K-12 enrollment",
    )

    k12_share_col = detect_column(
        k12_fields,
        [
            "public_k12_share",
            "k12_share",
        ],
        "K-12 share",
    )

    k12_central_col = detect_column(
        k12_fields,
        [
            "k12_central_1b",
            "k12_central",
        ],
        "K-12 central allocation",
    )

    # ------------------------------------------------------------
    # Build dictionaries keyed by LD.
    # ------------------------------------------------------------

    wftc_by_ld = {}

    for row in wftc_rows:

        ld = int(float(row[wftc_ld_col]))

        approvals = float(
            row[wftc_approval_col]
        )

        if ld in wftc_by_ld:
            raise RuntimeError(
                f"Duplicate WFTC LD {ld}."
            )

        wftc_by_ld[ld] = approvals

    k12_by_ld = {}

    for row in k12_rows:

        ld = int(float(row[k12_ld_col]))

        if ld in k12_by_ld:
            raise RuntimeError(
                f"Duplicate K-12 LD {ld}."
            )

        k12_by_ld[ld] = {
            "enrollment": int(
                float(row[k12_enrollment_col])
            ),
            "share": float(
                row[k12_share_col]
            ),
            "central": float(
                row[k12_central_col]
            ),
        }

    expected_lds = set(range(1, 50))

    if set(wftc_by_ld) != expected_lds:
        raise RuntimeError(
            "WFTC districts are not exactly 1-49."
        )

    if set(k12_by_ld) != expected_lds:
        raise RuntimeError(
            "K-12 districts are not exactly 1-49."
        )

    # ------------------------------------------------------------
    # Build combined model.
    # ------------------------------------------------------------

    equal_share = 1 / EXPECTED_LDS
    equal_combined = COMBINED_POOL / EXPECTED_LDS

    output_rows = []

    for ld in range(1, 50):

        approvals = wftc_by_ld[ld]

        wftc_share = approvals / WFTC_CONTROL
        wftc_dollars = WFTC_POOL * wftc_share

        k12 = k12_by_ld[ld]

        combined = (
            wftc_dollars
            + k12["central"]
        )

        combined_share = (
            combined / COMBINED_POOL
        )

        difference = (
            combined - equal_combined
        )

        output_rows.append(
            {
                "legislative_district": ld,

                "wftc_estimated_approvals_v02":
                    approvals,

                "wftc_share":
                    wftc_share,

                "wftc_central_250m":
                    money(wftc_dollars),

                "k12_public_enrollment":
                    k12["enrollment"],

                "k12_share":
                    k12["share"],

                "k12_central_1b":
                    money(k12["central"]),

                "combined_wftc_k12":
                    money(combined),

                "combined_share":
                    combined_share,

                "equal_share_1_of_49":
                    equal_share,

                "equal_combined_1_25b":
                    money(equal_combined),

                "difference_from_equal":
                    money(difference),

                "ratio_to_equal":
                    combined / equal_combined,
            }
        )

    # ------------------------------------------------------------
    # Write CSV.
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

    approval_total = sum(
        row["wftc_estimated_approvals_v02"]
        for row in output_rows
    )

    wftc_total = sum(
        row["wftc_central_250m"]
        for row in output_rows
    )

    k12_total = sum(
        row["k12_central_1b"]
        for row in output_rows
    )

    combined_total = sum(
        row["combined_wftc_k12"]
        for row in output_rows
    )

    combined_share_sum = sum(
        row["combined_share"]
        for row in output_rows
    )

    difference_total = sum(
        row["difference_from_equal"]
        for row in output_rows
    )

    print("ILLUSTRATIVE BENEFIT COMPONENTS v0.1")
    print("=" * 80)

    print()
    print("MODEL")
    print("-" * 80)
    print(
        "WFTC central illustrative pool : "
        "$250,000,000"
    )
    print(
        "K-12 central illustrative pool : "
        "$1,000,000,000"
    )
    print(
        "Combined modeled benefit pool  : "
        "$1,250,000,000"
    )
    print(
        "Purpose : intermediate illustrative geographic "
        "benefit-incidence model"
    )
    print(
        "Status  : not an enacted appropriation or forecast"
    )

    print()
    print("CONTROLS")
    print("-" * 80)
    print(
        f"Legislative districts        : "
        f"{len(output_rows)}"
    )
    print(
        f"WFTC approvals control       : "
        f"{approval_total:,.6f}"
    )
    print(
        f"WFTC allocation total        : "
        f"${wftc_total:,.2f}"
    )
    print(
        f"K-12 allocation total        : "
        f"${k12_total:,.2f}"
    )
    print(
        f"Combined allocation total    : "
        f"${combined_total:,.2f}"
    )
    print(
        f"Combined share sum           : "
        f"{combined_share_sum:.12f}"
    )
    print(
        f"Difference-from-equal sum    : "
        f"${difference_total:,.2f}"
    )

    print()
    print("LARGEST ABOVE EQUAL SHARE")
    print("-" * 80)

    for row in sorted(
        output_rows,
        key=lambda x: x["difference_from_equal"],
        reverse=True,
    )[:10]:

        print(
            f"LD {row['legislative_district']:>2}: "
            f"WFTC=${row['wftc_central_250m']:>12,.2f}  "
            f"K12=${row['k12_central_1b']:>13,.2f}  "
            f"combined=${row['combined_wftc_k12']:>13,.2f}  "
            f"vs equal=${row['difference_from_equal']:>+13,.2f}"
        )

    print()
    print("LARGEST BELOW EQUAL SHARE")
    print("-" * 80)

    for row in sorted(
        output_rows,
        key=lambda x: x["difference_from_equal"],
    )[:10]:

        print(
            f"LD {row['legislative_district']:>2}: "
            f"WFTC=${row['wftc_central_250m']:>12,.2f}  "
            f"K12=${row['k12_central_1b']:>13,.2f}  "
            f"combined=${row['combined_wftc_k12']:>13,.2f}  "
            f"vs equal=${row['difference_from_equal']:>+13,.2f}"
        )

    print()
    print("OUTPUT")
    print("-" * 80)
    print(OUTPUT)


if __name__ == "__main__":
    main()