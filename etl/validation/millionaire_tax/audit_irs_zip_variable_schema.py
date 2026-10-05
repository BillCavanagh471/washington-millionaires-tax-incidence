from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pandas as pd


# =============================================================================
# PATHS
# =============================================================================

ROOT = Path(__file__).resolve().parents[3]

IRS_ZIP_XLSX = (
    ROOT
    / "data"
    / "raw"
    / "irs"
    / "zip"
    / "ty2022"
    / "22zp48wa.xlsx"
)

EXPECTED_SHA256 = (
    "cadcf9dd5b197a084dccb62268c1fc18"
    "be039a17722b15eb05e674fdc855dfa5"
)


# =============================================================================
# HELPERS
# =============================================================================

def sha256(path: Path) -> str:
    h = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)

    return h.hexdigest()


def clean(value) -> str:
    if pd.isna(value):
        return ""

    return " ".join(
        str(value)
        .replace("\n", " ")
        .replace("\r", " ")
        .split()
    )


# =============================================================================
# MAIN
# =============================================================================

def main() -> int:
    print("=" * 110)
    print("IRS TY2022 WASHINGTON ZIP SOI VARIABLE SCHEMA AUDIT")
    print("=" * 110)

    print()
    print("STAGE 5C - SCHEMA AUDIT ONLY")
    print()
    print("READ ONLY")
    print("NO DATABASE WRITES")
    print("NO GEOGRAPHIC ALLOCATION")
    print("NO MODEL FITTING")
    print("NO LD MILLIONAIRE ESTIMATES")
    print("NO USE OF HISTORICAL LD MILLIONAIRE DATA")

    if not IRS_ZIP_XLSX.exists():
        raise FileNotFoundError(
            f"Required workbook not found: {IRS_ZIP_XLSX}"
        )

    digest = sha256(IRS_ZIP_XLSX)

    print()
    print("=" * 110)
    print("SOURCE PROVENANCE")
    print("=" * 110)

    print(f"Source                           : {IRS_ZIP_XLSX.relative_to(ROOT)}")
    print(f"Bytes                            : {IRS_ZIP_XLSX.stat().st_size:,}")
    print(f"SHA-256                          : {digest}")

    if digest != EXPECTED_SHA256:
        raise RuntimeError(
            "IRS ZIP workbook differs from the frozen TY2022 source."
        )

    print("Frozen source hash validation    : PASS")

    raw = pd.read_excel(
        IRS_ZIP_XLSX,
        sheet_name="Sheet1",
        header=None,
    )

    print()
    print(f"Workbook rows                    : {len(raw):,}")
    print(f"Workbook columns                 : {raw.shape[1]:,}")

    # -------------------------------------------------------------------------
    # The IRS workbook uses several header rows. Rather than assuming variable
    # semantics from remembered IRS codes, print the workbook's own header
    # material alongside the zero-based pandas column position.
    # -------------------------------------------------------------------------

    print()
    print("=" * 110)
    print("COMPLETE COLUMN HEADER MAP")
    print("=" * 110)

    print()
    print(
        "Columns below are ZERO-BASED pandas positions. "
        "Header text is reproduced from the frozen IRS workbook."
    )
    print()

    for col in range(raw.shape[1]):
        header_parts = []

        # Rows 3, 4, and 5 contain the principal IRS header material observed
        # during prior profiling. Include row 2 as additional context where
        # populated.
        for row in (2, 3, 4, 5):
            if row >= len(raw):
                continue

            value = clean(raw.iat[row, col])

            if value:
                header_parts.append(
                    f"row{row}={value}"
                )

        joined = " | ".join(header_parts)

        print(
            f"COL {col:03d} : {joined}"
        )

    # -------------------------------------------------------------------------
    # Focused neighborhood around the currently used variables.
    # -------------------------------------------------------------------------

    print()
    print("=" * 110)
    print("FOCUSED HEADER NEIGHBORHOOD: COLUMNS 14 THROUGH 60")
    print("=" * 110)

    for col in range(14, min(61, raw.shape[1])):
        parts = []

        for row in (2, 3, 4, 5):
            value = clean(raw.iat[row, col])

            if value:
                parts.append(
                    f"r{row}:{value}"
                )

        print(
            f"{col:03d} | "
            + " | ".join(parts)
        )

    # -------------------------------------------------------------------------
    # Inspect a known $200K+ ZIP row so that column semantics can be checked
    # against actual values rather than headers alone.
    # -------------------------------------------------------------------------

    print()
    print("=" * 110)
    print("KNOWN $200K+ ZIP OBSERVATION")
    print("=" * 110)

    zip_col = raw.iloc[:, 0].astype(str).str.strip()
    agi_col = raw.iloc[:, 1].astype(str).str.strip()

    mask = (
        zip_col.str.replace(".0", "", regex=False).eq("98001")
        & agi_col.eq("$200,000 or more")
    )

    matches = raw.loc[mask]

    print(f"ZIP 98001 $200K+ rows            : {len(matches):,}")

    if len(matches) != 1:
        raise RuntimeError(
            "Could not uniquely identify ZIP 98001 $200K+ row."
        )

    row = matches.iloc[0]

    print()
    print("Column values 14 through 60:")
    print()

    for col in range(14, min(61, raw.shape[1])):
        value = row.iloc[col]

        if pd.isna(value):
            display = ""
        else:
            display = str(value)

        print(
            f"COL {col:03d} : {display}"
        )

    # -------------------------------------------------------------------------
    # Statewide $200K+ row: useful for detecting obviously incorrect mappings.
    # -------------------------------------------------------------------------

    print()
    print("=" * 110)
    print("STATEWIDE $200K+ OBSERVATION")
    print("=" * 110)

    normalized_zip = (
        raw.iloc[:, 0]
        .astype(str)
        .str.strip()
        .str.replace(".0", "", regex=False)
    )

    state_mask = (
        normalized_zip.eq("0")
        & agi_col.eq("$200,000 or more")
    )

    state_matches = raw.loc[state_mask]

    print(f"Statewide $200K+ rows            : {len(state_matches):,}")

    if len(state_matches) != 1:
        raise RuntimeError(
            "Could not uniquely identify statewide $200K+ row."
        )

    state_row = state_matches.iloc[0]

    print()
    print("Column values 14 through 60:")
    print()

    for col in range(14, min(61, raw.shape[1])):
        value = state_row.iloc[col]

        if pd.isna(value):
            display = ""
        else:
            display = str(value)

        print(
            f"COL {col:03d} : {display}"
        )

    # -------------------------------------------------------------------------
    # Search header text for the concepts that matter to Stage 5B.
    # -------------------------------------------------------------------------

    print()
    print("=" * 110)
    print("HEADER TERM SEARCH")
    print("=" * 110)

    terms = [
        "adjusted gross income",
        "interest",
        "dividend",
        "capital gain",
        "business",
        "profession",
        "rental",
        "royalty",
        "partnership",
        "s corporation",
        "pension",
        "annuit",
    ]

    for term in terms:
        print()
        print(f"TERM: {term}")
        print("-" * 110)

        hits = 0

        for col in range(raw.shape[1]):
            header_text = " | ".join(
                clean(raw.iat[row, col])
                for row in (2, 3, 4, 5)
                if row < len(raw)
            )

            if term.lower() in header_text.lower():
                print(
                    f"COL {col:03d} : {header_text}"
                )
                hits += 1

        if hits == 0:
            print("NO MATCH")

    print()
    print("=" * 110)
    print("STAGE 5C SCHEMA AUDIT COMPLETE")
    print("=" * 110)

    print()
    print(
        "No schema corrections have been made by this script."
    )
    print(
        "Use this output to establish the exact IRS workbook column "
        "positions before modifying Stage 5B."
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())