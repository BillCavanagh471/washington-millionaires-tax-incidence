"""
Build Millionaires Tax legislative-district geographic weights v0.2.

METHOD
------
Model 1 provides the geographic distribution of estimated tax liability
using the underlying district-level millionaire taxpayer/income estimates.

For the 47 districts with disclosed Model 1 inputs:

    geographic_share_d =
        model1_tax_d / sum(model1_tax across observable districts)

That geographic distribution is then applied independently to:

    Model 2 reference scenario : $3.500 billion
    FY2029 control             : $2.698 billion
    FY2030 control             : $3.732 billion

LD14 and LD29 do not have the source inputs required for Model 1.
Their tax incidence is therefore N/A, not zero and not imputed.

The script does NOT overwrite v0.1.

INPUT
-----
data/processed/model/millionaires_tax_ld_weights_v0_1_audit.csv

OUTPUT
------
data/processed/model/millionaires_tax_ld_weights_v0_2.csv
"""

from pathlib import Path
import csv
import math


SOURCE = Path(
    "data/processed/model/"
    "millionaires_tax_ld_weights_v0_1_audit.csv"
)

OUTPUT = Path(
    "data/processed/model/"
    "millionaires_tax_ld_weights_v0_2.csv"
)


EXCLUDED_LDS = {14, 29}

MODEL2_CONTROL = 3_500_000_000.0
FY2029_CONTROL = 2_698_000_000.0
FY2030_CONTROL = 3_732_000_000.0

EXPECTED_MODEL1_TOTAL = 2_804_008_240.60


def parse_optional_float(value):
    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    return float(text)


def money(value):
    if value is None:
        return "N/A"

    return f"${value:,.2f}"


def pct(value):
    if value is None:
        return "N/A"

    return f"{value:.6%}"


# ---------------------------------------------------------------------
# Read source
# ---------------------------------------------------------------------

if not SOURCE.exists():
    raise FileNotFoundError(
        f"Source audit file not found: {SOURCE}"
    )


with SOURCE.open(
    "r",
    newline="",
    encoding="utf-8-sig",
) as handle:
    source_rows = list(
        csv.DictReader(handle)
    )


if len(source_rows) != 49:
    raise ValueError(
        f"Expected 49 source rows; found {len(source_rows)}."
    )


districts = sorted(
    int(row["legislative_district"])
    for row in source_rows
)

if districts != list(range(1, 50)):
    raise ValueError(
        "Source does not contain exactly LD1-LD49."
    )


# ---------------------------------------------------------------------
# Extract Model 1 source values
# ---------------------------------------------------------------------

records = []

for row in source_rows:

    ld = int(
        row["legislative_district"]
    )

    model1_tax = parse_optional_float(
        row["model1_tax_paid"]
    )

    if ld in EXCLUDED_LDS:

        # The audit established that these districts lack
        # the disclosed source inputs required for Model 1.
        status = "SOURCE_INPUTS_UNAVAILABLE"

        # Do not turn unavailable geography into zero.
        model1_tax = None

    else:

        if model1_tax is None:
            raise ValueError(
                f"LD{ld} unexpectedly lacks Model 1 tax."
            )

        if model1_tax < 0:
            raise ValueError(
                f"LD{ld} has negative Model 1 tax."
            )

        status = "OBSERVABLE"

    records.append(
        {
            "legislative_district": ld,
            "tax_incidence_status": status,
            "model1_tax_source": model1_tax,
        }
    )


# ---------------------------------------------------------------------
# Exact 47-district Model 1 control
# ---------------------------------------------------------------------

observable = [
    row
    for row in records
    if row["tax_incidence_status"]
    == "OBSERVABLE"
]


if len(observable) != 47:
    raise ValueError(
        f"Expected 47 observable districts; "
        f"found {len(observable)}."
    )


model1_total = math.fsum(
    row["model1_tax_source"]
    for row in observable
)


if abs(
    model1_total
    - EXPECTED_MODEL1_TOTAL
) >= 0.01:
    raise ValueError(
        "Model 1 source control mismatch: "
        f"calculated={model1_total:,.2f}, "
        f"expected={EXPECTED_MODEL1_TOTAL:,.2f}"
    )


model2_factor = (
    MODEL2_CONTROL
    / model1_total
)

fy2029_factor = (
    FY2029_CONTROL
    / model1_total
)

fy2030_factor = (
    FY2030_CONTROL
    / model1_total
)


# ---------------------------------------------------------------------
# Derive geographic shares and scenario dollars
# ---------------------------------------------------------------------

for row in records:

    if (
        row["tax_incidence_status"]
        != "OBSERVABLE"
    ):

        row[
            "model1_47district_share"
        ] = None

        row[
            "model2_normalized_3_5b"
        ] = None

        row[
            "tax_paid_fy2029_2_698b"
        ] = None

        row[
            "tax_paid_fy2030_3_732b"
        ] = None

        continue

    model1_tax = row[
        "model1_tax_source"
    ]

    share = (
        model1_tax
        / model1_total
    )

    row[
        "model1_47district_share"
    ] = share

    row[
        "model2_normalized_3_5b"
    ] = (
        share
        * MODEL2_CONTROL
    )

    row[
        "tax_paid_fy2029_2_698b"
    ] = (
        share
        * FY2029_CONTROL
    )

    row[
        "tax_paid_fy2030_3_732b"
    ] = (
        share
        * FY2030_CONTROL
    )


# ---------------------------------------------------------------------
# Add provenance/control fields
# ---------------------------------------------------------------------

for row in records:

    row[
        "model1_47district_total"
    ] = model1_total

    row[
        "model2_normalization_factor"
    ] = model2_factor

    row[
        "fy2029_normalization_factor"
    ] = fy2029_factor

    row[
        "fy2030_normalization_factor"
    ] = fy2030_factor

    row[
        "source_method"
    ] = (
        "Model 1 geographic tax incidence; "
        "47 observable LDs; uniform statewide "
        "normalization; LD14/LD29 not imputed"
    )


# ---------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------

share_total = math.fsum(
    row["model1_47district_share"]
    for row in observable
)

model2_total = math.fsum(
    row["model2_normalized_3_5b"]
    for row in observable
)

fy2029_total = math.fsum(
    row["tax_paid_fy2029_2_698b"]
    for row in observable
)

fy2030_total = math.fsum(
    row["tax_paid_fy2030_3_732b"]
    for row in observable
)


def assert_close(
    actual,
    expected,
    tolerance,
    label,
):
    difference = actual - expected

    if abs(difference) >= tolerance:
        raise AssertionError(
            f"{label}: "
            f"actual={actual:.12f}, "
            f"expected={expected:.12f}, "
            f"difference={difference:.12f}"
        )


assert_close(
    share_total,
    1.0,
    1e-12,
    "47-district geographic share",
)

assert_close(
    model2_total,
    MODEL2_CONTROL,
    0.01,
    "Model 2 $3.5B control",
)

assert_close(
    fy2029_total,
    FY2029_CONTROL,
    0.01,
    "FY2029 control",
)

assert_close(
    fy2030_total,
    FY2030_CONTROL,
    0.01,
    "FY2030 control",
)


for ld in EXCLUDED_LDS:

    row = next(
        r
        for r in records
        if r["legislative_district"] == ld
    )

    fields_that_must_be_na = [
        "model1_tax_source",
        "model1_47district_share",
        "model2_normalized_3_5b",
        "tax_paid_fy2029_2_698b",
        "tax_paid_fy2030_3_732b",
    ]

    for field in fields_that_must_be_na:

        if row[field] is not None:
            raise AssertionError(
                f"LD{ld} {field} must be N/A."
            )


# ---------------------------------------------------------------------
# Write v0.2
# ---------------------------------------------------------------------

OUTPUT.parent.mkdir(
    parents=True,
    exist_ok=True,
)


fieldnames = [
    "legislative_district",
    "tax_incidence_status",
    "model1_tax_source",
    "model1_47district_share",
    "model2_normalized_3_5b",
    "tax_paid_fy2029_2_698b",
    "tax_paid_fy2030_3_732b",
    "model1_47district_total",
    "model2_normalization_factor",
    "fy2029_normalization_factor",
    "fy2030_normalization_factor",
    "source_method",
]


with OUTPUT.open(
    "w",
    newline="",
    encoding="utf-8",
) as handle:

    writer = csv.DictWriter(
        handle,
        fieldnames=fieldnames,
    )

    writer.writeheader()

    for row in sorted(
        records,
        key=lambda x:
            x["legislative_district"],
    ):

        output_row = dict(row)

        # CSV blanks deliberately represent N/A numeric values.
        for field in [
            "model1_tax_source",
            "model1_47district_share",
            "model2_normalized_3_5b",
            "tax_paid_fy2029_2_698b",
            "tax_paid_fy2030_3_732b",
        ]:
            if output_row[field] is None:
                output_row[field] = ""

        writer.writerow(
            output_row
        )


# ---------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------

print()
print(
    "MILLIONAIRES TAX LD WEIGHTS v0.2"
)
print("=" * 92)

print()
print("METHODOLOGY")
print("-" * 92)

print(
    "Model 1 supplies geographic tax incidence."
)

print(
    "A single uniform factor changes statewide "
    "magnitude without changing the 47-LD distribution."
)

print(
    "LD14 and LD29 remain N/A; "
    "no tax incidence is imputed."
)


print()
print("SOURCE CONTROL")
print("-" * 92)

print(
    f"Observable districts       : "
    f"{len(observable)}"
)

print(
    "Unavailable districts      : "
    "LD14, LD29"
)

print(
    f"Model 1 source total       : "
    f"{money(model1_total)}"
)

print(
    f"47-LD geographic shares    : "
    f"{share_total:.12f}"
)


print()
print("NORMALIZATION CONTROLS")
print("-" * 92)

print(
    f"Model 2 $3.5B factor       : "
    f"{model2_factor:.12f}"
)

print(
    f"FY2029 $2.698B factor      : "
    f"{fy2029_factor:.12f}"
)

print(
    f"FY2030 $3.732B factor      : "
    f"{fy2030_factor:.12f}"
)


print()
print("RECONCILIATION")
print("-" * 92)

print(
    f"Model 2                    : "
    f"{money(model2_total)}"
)

print(
    f"FY2029                     : "
    f"{money(fy2029_total)}"
)

print(
    f"FY2030                     : "
    f"{money(fy2030_total)}"
)


print()
print("TOP 15 GEOGRAPHIC TAX SHARES")
print("-" * 92)

ranked = sorted(
    observable,
    key=lambda x:
        x["model1_47district_share"],
    reverse=True,
)

cumulative = 0.0

for rank, row in enumerate(
    ranked[:15],
    start=1,
):

    cumulative += row[
        "model1_47district_share"
    ]

    print(
        f"{rank:>2}. "
        f"LD {row['legislative_district']:>2}  "
        f"share={pct(row['model1_47district_share']):>10}  "
        f"FY2029="
        f"{money(row['tax_paid_fy2029_2_698b']):>18}  "
        f"FY2030="
        f"{money(row['tax_paid_fy2030_3_732b']):>18}"
    )


print()
print("UNAVAILABLE TAX INCIDENCE")
print("-" * 92)

print(
    "LD14  tax=N/A  net incidence must also be N/A"
)

print(
    "LD29  tax=N/A  net incidence must also be N/A"
)


print()
print("VALIDATION")
print("-" * 92)

print(
    "49 LD records                    : PASS"
)

print(
    "47 observable tax districts      : PASS"
)

print(
    "LD14/LD29 numeric tax fields N/A : PASS"
)

print(
    "47-LD geographic shares = 1      : PASS"
)

print(
    "$3.500B control                  : PASS"
)

print(
    "$2.698B FY2029 control           : PASS"
)

print(
    "$3.732B FY2030 control           : PASS"
)


print()
print("OUTPUT")
print("-" * 92)

print(OUTPUT)