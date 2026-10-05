from __future__ import annotations

import csv
import hashlib
import sys
import zipfile
from collections import defaultdict
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]

RAW_CENSUS = ROOT / "data" / "raw" / "census"

ZCTA_BLOCK_REL = (
    RAW_CENSUS / "tab20_zcta520_tabblock20_natl.txt"
)

CD_ZIP = (
    RAW_CENSUS
    / "congressional_district_validation"
    / "tl_2021_us_cd116.zip"
)

WA_BLOCK_ZIP = (
    RAW_CENSUS
    / "congressional_district_validation"
    / "tl_2020_53_tabblock20.zip"
)

OUT_DIR = (
    ROOT
    / "data"
    / "processed"
    / "validation"
    / "irs_cd_ty2022"
)

OUT_REL = OUT_DIR / "wa_zcta_block_relationship.csv"


WA_BLOCK_URL = (
    "https://www2.census.gov/geo/tiger/TIGER2020PL/STATE/53_WASHINGTON/"
    "53/tl_2020_53_tabblock20.zip"
)


def sha256(path: Path) -> str:
    h = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)

    return h.hexdigest()


def download(url: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists() and path.stat().st_size > 0:
        print(f"EXISTS      {path}")
        return

    print(f"DOWNLOADING {url}")

    req = Request(
        url,
        headers={
            "User-Agent": (
                "washington-millionaires-tax-incidence/"
                "cd-validation"
            )
        },
    )

    with urlopen(req, timeout=180) as response:
        with path.open("wb") as f:
            while True:
                chunk = response.read(1024 * 1024)

                if not chunk:
                    break

                f.write(chunk)

    print(f"SAVED       {path}")


def inspect_zip(path: Path) -> None:
    print()
    print(f"ZIP: {path.relative_to(ROOT)}")
    print("-" * 88)

    with zipfile.ZipFile(path) as zf:
        for info in zf.infolist():
            print(f"{info.file_size:>12,}  {info.filename}")


def inspect_relationship_file(path: Path) -> tuple[list[str], str]:
    print()
    print("=" * 88)
    print("ZCTA-BLOCK RELATIONSHIP FILE")
    print("=" * 88)

    print(f"Path    : {path.relative_to(ROOT)}")
    print(f"Bytes   : {path.stat().st_size:,}")
    print(f"SHA-256 : {sha256(path)}")

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
        errors="replace",
    ) as f:
        first_line = f.readline()

    delimiter = "|" if first_line.count("|") > first_line.count(",") else ","

    reader = csv.reader([first_line], delimiter=delimiter)
    header = next(reader)

    header = [x.strip().strip('"') for x in header]

    print(f"Delimiter: {repr(delimiter)}")
    print(f"Columns  : {header}")

    return header, delimiter


def candidate_column(
    columns: list[str],
    candidates: list[str],
) -> str | None:
    lookup = {c.upper(): c for c in columns}

    for candidate in candidates:
        if candidate.upper() in lookup:
            return lookup[candidate.upper()]

    return None


def extract_wa_relationship(
    path: Path,
    header: list[str],
    delimiter: str,
) -> None:
    """
    Stream the ~1 GB national relationship file and retain only
    Washington blocks (state FIPS 53).

    No geographic allocation is performed here.
    """

    state_col = candidate_column(
        header,
        [
            "STATEFP20",
            "STATEFP",
        ],
    )

    block_col = candidate_column(
        header,
        [
            "GEOID_TABBLOCK_20",
            "GEOID20",
            "BLOCK_GEOID20",
            "TABBLK20",
        ],
    )

    zcta_col = candidate_column(
        header,
        [
            "GEOID_ZCTA5_20",
            "ZCTA5CE20",
            "ZCTA5",
            "ZCTA5CE",
        ],
    )

    # Some Census relationship files store block geography in
    # component fields rather than a complete GEOID.
    county_col = candidate_column(
        header,
        [
            "COUNTYFP20",
            "COUNTYFP",
        ],
    )

    tract_col = candidate_column(
        header,
        [
            "TRACTCE20",
            "TRACTCE",
        ],
    )

    block_component_col = candidate_column(
        header,
        [
            "BLOCKCE20",
            "BLOCKCE",
        ],
    )

    print()
    print("Detected fields")
    print("-" * 88)
    print(f"State             : {state_col}")
    print(f"Full block GEOID  : {block_col}")
    print(f"County            : {county_col}")
    print(f"Tract             : {tract_col}")
    print(f"Block component   : {block_component_col}")
    print(f"ZCTA              : {zcta_col}")

    if zcta_col is None:
        raise RuntimeError(
            "Could not identify the ZCTA field."
        )

    if block_col is None:
        required = [
            state_col,
            county_col,
            tract_col,
            block_component_col,
        ]

        if any(x is None for x in required):
            raise RuntimeError(
                "Could not identify either a full block GEOID "
                "or all component geography fields."
            )

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    rows_read = 0
    rows_wa = 0

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
        errors="replace",
    ) as src, OUT_REL.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as dst:

        reader = csv.DictReader(
            src,
            delimiter=delimiter,
        )

        writer = csv.DictWriter(
            dst,
            fieldnames=[
                "block_geoid20",
                "zcta5ce20",
            ],
        )

        writer.writeheader()

        for row in reader:
            rows_read += 1

            if block_col is not None:
                block_geoid = str(row[block_col]).strip()

                # A Census block GEOID starts with its two-digit
                # state FIPS.
                is_wa = block_geoid.startswith("53")

            else:
                state = str(row[state_col]).strip().zfill(2)
                is_wa = state == "53"

                if is_wa:
                    county = str(row[county_col]).strip().zfill(3)
                    tract = str(row[tract_col]).strip().zfill(6)
                    block = (
                        str(row[block_component_col])
                        .strip()
                        .zfill(4)
                    )

                    block_geoid = (
                        state
                        + county
                        + tract
                        + block
                    )

            if not is_wa:
                continue

            zcta = str(row[zcta_col]).strip().zfill(5)

            writer.writerow(
                {
                    "block_geoid20": block_geoid,
                    "zcta5ce20": zcta,
                }
            )

            rows_wa += 1

            if rows_wa % 100_000 == 0:
                print(
                    f"Washington rows retained: "
                    f"{rows_wa:,}"
                )

    print()
    print("Relationship extraction")
    print("-" * 88)
    print(f"National rows read : {rows_read:,}")
    print(f"WA rows retained   : {rows_wa:,}")
    print(f"Output             : {OUT_REL.relative_to(ROOT)}")
    print(f"Output bytes       : {OUT_REL.stat().st_size:,}")
    print(f"Output SHA-256     : {sha256(OUT_REL)}")


def profile_output() -> None:
    df = pd.read_csv(
        OUT_REL,
        dtype=str,
    )

    print()
    print("=" * 88)
    print("WASHINGTON RELATIONSHIP PROFILE")
    print("=" * 88)

    print(f"Rows                   : {len(df):,}")
    print(
        f"Distinct blocks        : "
        f"{df['block_geoid20'].nunique():,}"
    )
    print(
        f"Distinct ZCTAs         : "
        f"{df['zcta5ce20'].nunique():,}"
    )

    duplicate_blocks = (
        df.groupby("block_geoid20")
        .size()
        .gt(1)
        .sum()
    )

    print(
        f"Blocks with >1 ZCTA row: "
        f"{duplicate_blocks:,}"
    )

    print()
    print("First 20 rows:")
    print(df.head(20).to_string(index=False))


def main() -> int:
    print("=" * 88)
    print(
        "MILLIONAIRE TAX LD MODEL — "
        "CD VALIDATION GEOGRAPHY STAGE 1"
    )
    print("=" * 88)

    print()
    print("PURPOSE")
    print("-" * 88)
    print(
        "Acquire Washington 2020 Census block geometry and "
        "reduce the national ZCTA-block relationship file "
        "to Washington."
    )
    print()
    print("NO IRS ALLOCATION")
    print("NO MODEL FITTING")
    print("NO LD MILLIONAIRE ESTIMATES")
    print("NO DATABASE WRITES")

    if not ZCTA_BLOCK_REL.exists():
        raise FileNotFoundError(
            f"Missing relationship file: {ZCTA_BLOCK_REL}"
        )

    if not CD_ZIP.exists():
        raise FileNotFoundError(
            f"Missing congressional district ZIP: {CD_ZIP}"
        )

    download(
        WA_BLOCK_URL,
        WA_BLOCK_ZIP,
    )

    print()
    print("=" * 88)
    print("SOURCE INVENTORY")
    print("=" * 88)

    for path in (
        ZCTA_BLOCK_REL,
        CD_ZIP,
        WA_BLOCK_ZIP,
    ):
        print()
        print(path.relative_to(ROOT))
        print(f"Bytes   : {path.stat().st_size:,}")
        print(f"SHA-256 : {sha256(path)}")

    inspect_zip(CD_ZIP)
    inspect_zip(WA_BLOCK_ZIP)

    header, delimiter = inspect_relationship_file(
        ZCTA_BLOCK_REL
    )

    extract_wa_relationship(
        ZCTA_BLOCK_REL,
        header,
        delimiter,
    )

    profile_output()

    print()
    print("=" * 88)
    print("STAGE 1 COMPLETE")
    print("=" * 88)
    print()
    print(
        "Next stage will attach POP20 and congressional "
        "district geography, then construct population-"
        "weighted ZCTA-to-CD weights."
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())