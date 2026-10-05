"""
Audit Millionaires Tax legislative-district geographic weights v0.1.

READ-ONLY DIAGNOSTIC.

This script does not modify the source workbook or any accepted model file.

Questions:
1. Are all 49 legislative districts present?
2. What are the original Model 2 Tax Paid values?
3. Which values repeat across districts?
4. How concentrated is modeled tax incidence?
5. What do the source workbook fields show for suspicious districts?
6. Are LD14 and LD29 based on missing/blank source inputs?
7. Can Model 2 Tax Paid be related arithmetically to other workbook fields?

Source workbook:
    Washington State Millionaires Tax by Legislative
    District_currency_cleaned NEWEST.xlsx

Accepted tax-weight file:
    data/processed/model/millionaires_tax_ld_weights_v0_1.csv
"""

from pathlib import Path
from collections import defaultdict
import csv
import math

from openpyxl import load_workbook


WORKBOOK = Path(
    "Washington State Millionaires Tax by Legislative "
    "District_currency_cleaned NEWEST.xlsx"
)

WEIGHTS_FILE = Path(
    "data/processed/model/"
    "millionaires_tax_ld_weights_v0_1.csv"
)

OUTPUT_FILE = Path(
    "data/processed/model/"
    "millionaires_tax_ld_weights_v0_1_audit.csv"
)


EXPECTED_LDS = list(range(1, 50))


def clean(value):
    if value is None:
        return ""
    return str(value).strip()


def numeric(value):
    if value is None:
        return None

    if isinstance(value, (int, float)):
        if isinstance(value, float) and math.isnan(value):
            return None
        return float(value)

    text = str(value).strip()

    if not text:
        return None

    text = (
        text
        .replace("$", "")
        .replace(",", "")
        .replace("%", "")
        .replace("(", "-")
        .replace(")", "")
    )

    try:
        return float(text)
    except ValueError:
        return None


def district_number(value):
    if value is None:
        return None

    if isinstance(value, (int, float)):
        d = int(value)
        return d if 1 <= d <= 49 else None

    text = str(value).lower().strip()

    for token in [
        "legislative district",
        "district",
        "ld",
    ]:
        text = text.replace(token, "")

    text = text.strip()

    try:
        d = int(float(text))
    except ValueError:
        return None

    return d if 1 <= d <= 49 else None


def money(value):
    if value is None:
        return "BLANK"
    return f"${value:,.2f}"


def value_text(value):
    if value is None:
        return "BLANK"

    if isinstance(value, float):
        return f"{value:,.6f}"

    return str(value)


# ---------------------------------------------------------------------
# Workbook
# ---------------------------------------------------------------------

def load_workbook_source():

    if not WORKBOOK.exists():
        raise FileNotFoundError(WORKBOOK)

    # Load twice:
    #
    # data_only=True  -> cached calculated values
    # data_only=False -> formulas, if present

    wb_values = load_workbook(
        WORKBOOK,
        data_only=True,
        read_only=True,
    )

    wb_formulas = load_workbook(
        WORKBOOK,
        data_only=False,
        read_only=True,
    )

    matches = []

    for ws in wb_values.worksheets:

        for row_num in range(
            1,
            min(ws.max_row, 25) + 1,
        ):

            headers = {
                clean(
                    ws.cell(row_num, col).value
                ): col
                for col in range(
                    1,
                    ws.max_column + 1,
                )
                if ws.cell(
                    row_num,
                    col,
                ).value is not None
            }

            if (
                "Legislative District" in headers
                and "Tax Paid" in headers
            ):
                matches.append(
                    (
                        ws.title,
                        row_num,
                        headers,
                    )
                )
                break

    if not matches:
        raise ValueError(
            "Could not locate workbook source table."
        )

    sheet_name, header_row, headers = matches[0]

    return (
        wb_values[sheet_name],
        wb_formulas[sheet_name],
        header_row,
        headers,
    )


def extract_workbook_rows():

    (
        ws_values,
        ws_formulas,
        header_row,
        headers,
    ) = load_workbook_source()

    records = {}

    for row_num in range(
        header_row + 1,
        ws_values.max_row + 1,
    ):

        district = district_number(
            ws_values.cell(
                row_num,
                headers["Legislative District"],
            ).value
        )

        if district is None:
            continue

        record = {
            "legislative_district": district,
            "source_row": row_num,
        }

        # Preserve every workbook column.
        for col in range(
            1,
            ws_values.max_column + 1,
        ):

            header = clean(
                ws_values.cell(
                    header_row,
                    col,
                ).value
            )

            if not header:
                header = f"UNNAMED_COL_{col}"

            value = ws_values.cell(
                row_num,
                col,
            ).value

            formula = ws_formulas.cell(
                row_num,
                col,
            ).value

            record[
                f"value__{header}"
            ] = value

            if (
                isinstance(formula, str)
                and formula.startswith("=")
            ):
                record[
                    f"formula__{header}"
                ] = formula
            else:
                record[
                    f"formula__{header}"
                ] = ""

        records[district] = record

    if sorted(records) != EXPECTED_LDS:
        raise ValueError(
            "Workbook does not contain exactly LD1-LD49."
        )

    return records, headers


# ---------------------------------------------------------------------
# Accepted weights
# ---------------------------------------------------------------------

def load_weights():

    with WEIGHTS_FILE.open(
        "r",
        newline="",
        encoding="utf-8-sig",
    ) as handle:
        rows = list(csv.DictReader(handle))

    result = {}

    for row in rows:

        d = int(
            row["legislative_district"]
        )

        result[d] = {
            "original_model2_tax_paid":
                float(
                    row[
                        "original_model2_tax_paid"
                    ]
                ),

            "tax_incidence_share":
                float(
                    row[
                        "tax_incidence_share"
                    ]
                ),

            "fy2029_tax":
                float(
                    row[
                        "tax_paid_fy2029_2_698b"
                    ]
                ),

            "fy2030_tax":
                float(
                    row[
                        "tax_paid_fy2030_3_732b"
                    ]
                ),
        }

    if sorted(result) != EXPECTED_LDS:
        raise ValueError(
            "Weight file does not contain LD1-LD49."
        )

    return result


# ---------------------------------------------------------------------
# Repeated-value analysis
# ---------------------------------------------------------------------

def repeated_values(weights):

    groups = defaultdict(list)

    for d, row in weights.items():

        # Round to cents only for grouping.
        key = round(
            row["original_model2_tax_paid"],
            2,
        )

        groups[key].append(d)

    return {
        value: districts
        for value, districts in groups.items()
        if len(districts) > 1
    }


# ---------------------------------------------------------------------
# Source-input diagnostics
# ---------------------------------------------------------------------

def source_input_status(record):

    fields = {
        "millionaire_count":
            numeric(
                record.get(
                    "value__Estimated Number of "
                    "Millionaires Tax Payers"
                )
            ),

        "average_income":
            numeric(
                record.get(
                    "value__Estimated Average Annual "
                    "Income per Millionaires Tax Payer"
                )
            ),

        "minus_1m_times_point1":
            numeric(
                record.get(
                    "value__Minus 1M * 0.1"
                )
            ),

        "model1_tax":
            numeric(
                record.get(
                    "value__Tax Paid (ColG*ColE) per Dist"
                )
            ),

        "model2_tax":
            numeric(
                record.get(
                    "value__Tax Paid"
                )
            ),

        "model2_reinvested":
            numeric(
                record.get(
                    "value__Reinvested"
                )
            ),

        "model2_net":
            numeric(
                record.get(
                    "value__Net Model 2"
                )
            ),
    }

    missing = [
        name
        for name, value in fields.items()
        if value is None
    ]

    return fields, missing


# ---------------------------------------------------------------------
# Audit table
# ---------------------------------------------------------------------

def build_audit_rows(workbook_rows, weights):

    repeats = repeated_values(weights)

    repeat_lookup = {}

    for value, districts in repeats.items():
        for d in districts:
            repeat_lookup[d] = (
                value,
                districts,
            )

    audit = []

    for d in EXPECTED_LDS:

        source = workbook_rows[d]
        weight = weights[d]

        fields, missing = (
            source_input_status(source)
        )

        repeat_value = None
        repeat_districts = []

        if d in repeat_lookup:
            (
                repeat_value,
                repeat_districts,
            ) = repeat_lookup[d]

        workbook_tax = fields["model2_tax"]

        accepted_tax = (
            weight["original_model2_tax_paid"]
        )

        if workbook_tax is None:
            difference = None
        else:
            difference = (
                accepted_tax
                - workbook_tax
            )

        flags = []

        if missing:
            flags.append(
                "MISSING_SOURCE_FIELDS"
            )

        if repeat_districts:
            flags.append(
                "REPEATED_MODEL2_TAX_VALUE"
            )

        if accepted_tax == 0:
            flags.append(
                "ZERO_MODEL2_TAX"
            )

        if fields["millionaire_count"] is None:
            flags.append(
                "MISSING_MILLIONAIRE_COUNT"
            )

        if fields["average_income"] is None:
            flags.append(
                "MISSING_AVERAGE_INCOME"
            )

        if (
            difference is not None
            and abs(difference) >= 0.01
        ):
            flags.append(
                "WEIGHT_FILE_SOURCE_MISMATCH"
            )

        audit.append(
            {
                "legislative_district":
                    d,

                "source_row":
                    source["source_row"],

                "millionaire_count":
                    fields["millionaire_count"],

                "average_income":
                    fields["average_income"],

                "minus_1m_times_point1":
                    fields[
                        "minus_1m_times_point1"
                    ],

                "model1_tax_paid":
                    fields["model1_tax"],

                "model2_tax_paid":
                    fields["model2_tax"],

                "model2_reinvested":
                    fields["model2_reinvested"],

                "model2_net":
                    fields["model2_net"],

                "accepted_original_model2_tax":
                    accepted_tax,

                "accepted_tax_share":
                    weight["tax_incidence_share"],

                "accepted_fy2029_tax":
                    weight["fy2029_tax"],

                "accepted_fy2030_tax":
                    weight["fy2030_tax"],

                "repeated_tax_value":
                    repeat_value,

                "repeated_with_lds":
                    ",".join(
                        str(x)
                        for x in repeat_districts
                    ),

                "missing_fields":
                    ",".join(missing),

                "audit_flags":
                    ",".join(flags),
            }
        )

    return audit


# ---------------------------------------------------------------------
# Write audit CSV
# ---------------------------------------------------------------------

def write_audit(rows):

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
            fieldnames=list(
                rows[0].keys()
            ),
        )

        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------

def print_repeated_groups(weights):

    repeats = repeated_values(weights)

    print()
    print("REPEATED ORIGINAL MODEL 2 TAX VALUES")
    print("-" * 100)

    if not repeats:
        print("None.")
        return

    ranked = sorted(
        repeats.items(),
        key=lambda x: (
            -len(x[1]),
            -x[0],
        ),
    )

    for value, districts in ranked:

        district_text = ", ".join(
            f"LD{d}"
            for d in districts
        )

        print(
            f"{money(value):>18}  "
            f"count={len(districts):>2}  "
            f"{district_text}"
        )


def print_flagged_rows(audit):

    flagged = [
        row
        for row in audit
        if row["audit_flags"]
    ]

    print()
    print("FLAGGED DISTRICTS")
    print("-" * 100)

    if not flagged:
        print("None.")
        return

    for row in flagged:

        print(
            f"LD {row['legislative_district']:>2}  "
            f"Model2={money(row['model2_tax_paid']):>18}  "
            f"count={value_text(row['millionaire_count']):>12}  "
            f"avg_income={money(row['average_income']):>18}"
        )

        print(
            f"      repeated_with="
            f"{row['repeated_with_lds'] or '-'}"
        )

        print(
            f"      missing="
            f"{row['missing_fields'] or '-'}"
        )

        print(
            f"      flags="
            f"{row['audit_flags']}"
        )


def print_specific_districts(
    workbook_rows,
    weights,
):

    targets = [
        14,
        29,
        9,
        7,
        19,
        48,
        41,
        45,
        43,
        36,
    ]

    print()
    print("TARGET-DISTRICT SOURCE DETAIL")
    print("-" * 100)

    for d in targets:

        source = workbook_rows[d]
        fields, missing = (
            source_input_status(source)
        )

        print()
        print(f"LD {d}")

        print(
            f"  source row             : "
            f"{source['source_row']}"
        )

        print(
            f"  millionaire count      : "
            f"{value_text(fields['millionaire_count'])}"
        )

        print(
            f"  average income         : "
            f"{money(fields['average_income'])}"
        )

        print(
            f"  Minus 1M * 0.1         : "
            f"{money(fields['minus_1m_times_point1'])}"
        )

        print(
            f"  Model 1 tax            : "
            f"{money(fields['model1_tax'])}"
        )

        print(
            f"  Model 2 tax            : "
            f"{money(fields['model2_tax'])}"
        )

        print(
            f"  Model 2 reinvested     : "
            f"{money(fields['model2_reinvested'])}"
        )

        print(
            f"  Model 2 net            : "
            f"{money(fields['model2_net'])}"
        )

        print(
            f"  accepted tax share     : "
            f"{weights[d]['tax_incidence_share']:.6%}"
        )

        print(
            f"  missing source fields  : "
            f"{', '.join(missing) if missing else 'NONE'}"
        )


def print_concentration(weights):

    ranked = sorted(
        weights.items(),
        key=lambda x:
            x[1]["tax_incidence_share"],
        reverse=True,
    )

    print()
    print("TAX-INCIDENCE CONCENTRATION")
    print("-" * 100)

    running = 0.0

    for rank, (d, row) in enumerate(
        ranked,
        start=1,
    ):

        running += row[
            "tax_incidence_share"
        ]

        if rank <= 15:
            print(
                f"{rank:>2}. "
                f"LD {d:>2}  "
                f"original="
                f"{money(row['original_model2_tax_paid']):>18}  "
                f"share="
                f"{row['tax_incidence_share']:>8.3%}  "
                f"cumulative="
                f"{running:>8.3%}"
            )

    top5 = sum(
        row["tax_incidence_share"]
        for _, row in ranked[:5]
    )

    top10 = sum(
        row["tax_incidence_share"]
        for _, row in ranked[:10]
    )

    print()
    print(
        f"Top 5 LD share  : {top5:.3%}"
    )

    print(
        f"Top 10 LD share : {top10:.3%}"
    )


def print_formula_inventory(
    workbook_rows,
):

    print()
    print("MODEL 2 TAX FORMULA INVENTORY")
    print("-" * 100)

    formula_counts = defaultdict(
        list
    )

    for d in EXPECTED_LDS:

        formula = workbook_rows[d].get(
            "formula__Tax Paid",
            "",
        )

        formula_counts[
            formula or "<NO FORMULA>"
        ].append(d)

    for formula, districts in formula_counts.items():

        district_text = ", ".join(
            str(d)
            for d in districts
        )

        print()
        print(
            f"Districts: {district_text}"
        )

        print(
            f"Formula  : {formula}"
        )


def main():

    workbook_rows, headers = (
        extract_workbook_rows()
    )

    weights = load_weights()

    audit = build_audit_rows(
        workbook_rows,
        weights,
    )

    write_audit(
        audit
    )

    print()
    print(
        "MILLIONAIRES TAX LD WEIGHTS AUDIT v0.1"
    )
    print("=" * 100)

    print()
    print("SOURCE")
    print("-" * 100)

    print(
        f"Workbook : {WORKBOOK}"
    )

    print(
        f"Weight file: {WEIGHTS_FILE}"
    )

    print(
        f"Districts audited: {len(audit)}"
    )

    print_repeated_groups(
        weights
    )

    print_flagged_rows(
        audit
    )

    print_specific_districts(
        workbook_rows,
        weights,
    )

    print_concentration(
        weights
    )

    print_formula_inventory(
        workbook_rows
    )

    print()
    print("OUTPUT")
    print("-" * 100)

    print(OUTPUT_FILE)

    print()
    print(
        "READ-ONLY AUDIT COMPLETE. "
        "No model inputs were modified."
    )


if __name__ == "__main__":
    main()