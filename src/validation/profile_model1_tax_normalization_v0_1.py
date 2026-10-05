"""
Profile Model 1 -> Model 2 tax normalization.

READ ONLY.

Uses the audit CSV produced from the source workbook.
LD14 and LD29 are excluded because the source does not
disclose the inputs required to calculate Model 1 tax.

No model files are modified.
"""

from pathlib import Path
import csv


SOURCE = Path(
    "data/processed/model/"
    "millionaires_tax_ld_weights_v0_1_audit.csv"
)

EXCLUDED_LDS = {14, 29}

TARGETS = {
    "MODEL2_3_5B": 3_500_000_000.0,
    "FY2029_2_698B": 2_698_000_000.0,
    "FY2030_3_732B": 3_732_000_000.0,
}


def money(x):
    return f"${x:,.2f}"


with SOURCE.open(
    "r",
    newline="",
    encoding="utf-8-sig",
) as handle:
    rows = list(csv.DictReader(handle))


included = []
excluded = []

for row in rows:

    ld = int(row["legislative_district"])

    raw = row["model1_tax_paid"].strip()

    model1_tax = (
        float(raw)
        if raw
        else None
    )

    if ld in EXCLUDED_LDS:
        excluded.append((ld, model1_tax))
        continue

    if model1_tax is None:
        raise ValueError(
            f"LD{ld} unexpectedly has no Model 1 tax."
        )

    included.append(
        (ld, model1_tax)
    )


model1_total = sum(
    tax for _, tax in included
)


print()
print(
    "MODEL 1 TAX NORMALIZATION PROFILE v0.1"
)
print("=" * 88)

print()
print("SOURCE CONTROL")
print("-" * 88)

print(
    f"Included districts          : "
    f"{len(included)}"
)

print(
    f"Excluded districts          : "
    f"{', '.join('LD'+str(x[0]) for x in excluded)}"
)

print(
    f"47-district Model 1 total   : "
    f"{money(model1_total)}"
)


print()
print("NORMALIZATION FACTORS")
print("-" * 88)

for name, target in TARGETS.items():

    factor = target / model1_total

    print(
        f"{name:<20} "
        f"target={money(target):>20}  "
        f"factor={factor:.12f}"
    )


print()
print("MODEL 2 — $3.5B NORMALIZATION")
print("-" * 88)

factor_35 = (
    TARGETS["MODEL2_3_5B"]
    / model1_total
)

normalized = []

for ld, model1_tax in included:

    model2_tax = (
        model1_tax * factor_35
    )

    normalized.append(
        (ld, model1_tax, model2_tax)
    )


for ld, m1, m2 in sorted(
    normalized,
    key=lambda x: x[2],
    reverse=True,
):

    print(
        f"LD {ld:>2}  "
        f"Model1={money(m1):>18}  "
        f"Model2={money(m2):>18}"
    )


normalized_total = sum(
    x[2] for x in normalized
)


print()
print("RECONCILIATION")
print("-" * 88)

print(
    f"Model 1 source total        : "
    f"{money(model1_total)}"
)

print(
    f"Normalized Model 2 total    : "
    f"{money(normalized_total)}"
)

print(
    f"Target                      : "
    f"{money(TARGETS['MODEL2_3_5B'])}"
)

print(
    f"Difference                  : "
    f"{money(normalized_total - TARGETS['MODEL2_3_5B'])}"
)

print()
print(
    "LD14 tax incidence         : N/A"
)

print(
    "LD29 tax incidence         : N/A"
)

print()
print(
    "READ-ONLY PROFILE COMPLETE."
)