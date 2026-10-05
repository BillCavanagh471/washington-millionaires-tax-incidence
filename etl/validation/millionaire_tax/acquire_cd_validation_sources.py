from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[3]

RAW_IRS = ROOT / "data" / "raw" / "irs" / "congressional_district" / "ty2022"
RAW_CENSUS = ROOT / "data" / "raw" / "census" / "congressional_district_validation"

SOURCES = [
    {
        "name": "IRS TY2022 Congressional District national CSV",
        "url": "https://www.irs.gov/pub/irs-soi/22incd.csv",
        "path": RAW_IRS / "22incd.csv",
    },
    {
        "name": "IRS TY2022 Washington Congressional District workbook",
        "url": "https://www.irs.gov/pub/irs-soi/22incdwa.xlsx",
        "path": RAW_IRS / "22incdwa.xlsx",
    },
    {
        "name": "Census 2021 congressional districts — CD116",
        "url": (
            "https://www2.census.gov/geo/tiger/TIGER2021/CD/"
            "tl_2021_us_cd116.zip"
        ),
        "path": RAW_CENSUS / "tl_2021_us_cd116.zip",
    },
]


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

    request = Request(
        url,
        headers={
            "User-Agent": (
                "washington-county-federal-fiscal-balance/"
                "cd-validation-source-acquisition"
            )
        },
    )

    with urlopen(request, timeout=120) as response:
        with path.open("wb") as f:
            while True:
                chunk = response.read(1024 * 1024)

                if not chunk:
                    break

                f.write(chunk)

    print(f"SAVED       {path}")


def main() -> int:
    print("=" * 88)
    print("MILLIONAIRE TAX LD MODEL — CONGRESSIONAL DISTRICT VALIDATION SOURCE ACQUISITION")
    print("=" * 88)
    print()
    print("ACQUISITION ONLY")
    print("No model fitting.")
    print("No LD millionaire estimates used.")
    print("No database writes.")
    print()

    for source in SOURCES:
        download(source["url"], source["path"])

    print()
    print("=" * 88)
    print("SOURCE INVENTORY")
    print("=" * 88)

    for source in SOURCES:
        path = source["path"]

        if not path.exists():
            print(f"FAIL  {source['name']}")
            continue

        print()
        print(source["name"])
        print("-" * 88)
        print(f"Path    : {path.relative_to(ROOT)}")
        print(f"Bytes   : {path.stat().st_size:,}")
        print(f"SHA-256 : {sha256(path)}")

    print()
    print("=" * 88)
    print("BASIC IRS CSV PROFILE")
    print("=" * 88)

    csv_path = RAW_IRS / "22incd.csv"

    if csv_path.exists():
        import pandas as pd

        df = pd.read_csv(
            csv_path,
            dtype={
                "STATE": "string",
                "CONGRESSIONAL_DISTRICT": "string",
            },
            low_memory=False,
        )

        print(f"Rows                 : {len(df):,}")
        print(f"Columns              : {len(df.columns):,}")
        print(f"Column names         : {list(df.columns)}")

        if "STATE" in df.columns:
            wa = df.loc[df["STATE"].eq("WA")].copy()

            print()
            print("WASHINGTON")
            print("-" * 88)
            print(f"Rows                 : {len(wa):,}")

            for candidate in (
                "CONGRESSIONAL_DISTRICT",
                "CONGRESSIONALDISTRICT",
                "CD",
            ):
                if candidate in wa.columns:
                    values = sorted(
                        wa[candidate]
                        .dropna()
                        .astype(str)
                        .unique()
                        .tolist()
                    )
                    print(f"{candidate:<21}: {values}")

            if "AGI_STUB" in wa.columns:
                print(
                    f"AGI_STUB values      : "
                    f"{sorted(wa['AGI_STUB'].dropna().unique().tolist())}"
                )

            inspect = [
                c
                for c in (
                    "STATE",
                    "CONGRESSIONAL_DISTRICT",
                    "CONGRESSIONALDISTRICT",
                    "CD",
                    "AGI_STUB",
                    "N1",
                    "A00100",
                    "N00600",
                    "A00600",
                    "N01000",
                    "A01000",
                    "N26270",
                    "A26270",
                )
                if c in wa.columns
            ]

            print()
            print("First Washington rows:")
            print(wa[inspect].head(20).to_string(index=False))

    print()
    print("=" * 88)
    print("ACQUISITION COMPLETE")
    print("=" * 88)

    return 0


if __name__ == "__main__":
    sys.exit(main())