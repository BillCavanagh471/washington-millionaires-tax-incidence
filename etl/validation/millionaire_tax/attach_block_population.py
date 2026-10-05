from __future__ import annotations

import hashlib
import sys
import zipfile
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]

PL_ZIP = (
    ROOT
    / "data"
    / "raw"
    / "census"
    / "pl2020"
    / "wa2020.pl.zip"
)

REL_PATH = (
    ROOT
    / "data"
    / "processed"
    / "validation"
    / "irs_cd_ty2022"
    / "wa_zcta_block_relationship.csv"
)

OUT_DIR = (
    ROOT
    / "data"
    / "processed"
    / "validation"
    / "irs_cd_ty2022"
)

OUT_BLOCK_POP = OUT_DIR / "wa_block_population_2020.csv"

OUT_JOINED = (
    OUT_DIR
    / "wa_zcta_block_population_2020.csv"
)


EXPECTED_WA_POP = 7_705_281

GEO_MEMBER = "wageo2020.pl"
SEG1_MEMBER = "wa000012020.pl"


def sha256(path: Path) -> str:
    h = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(
            lambda: f.read(1024 * 1024),
            b"",
        ):
            h.update(chunk)

    return h.hexdigest()


def normalize_logrecno(value: str) -> str:
    return str(value).strip().zfill(7)


def read_geography() -> pd.DataFrame:
    """
    Read the pipe-delimited 2020 PL geographic header.

    Confirmed from the Washington PL package:

      field 0  FILEID
      field 1  STUSAB
      field 2  SUMLEV
      field 7  LOGRECNO
      field 8  GEOID

    For block-level records (SUMLEV 750), GEOID is the
    authoritative Census geographic identifier. We derive
    the 15-digit block GEOID from its trailing 15 digits
    rather than reconstructing it from separately parsed
    geography components.
    """

    print()
    print("=" * 88)
    print("READ PL GEOGRAPHY")
    print("=" * 88)

    with zipfile.ZipFile(PL_ZIP) as zf:
        with zf.open(GEO_MEMBER) as f:
            geo = pd.read_csv(
                f,
                sep="|",
                header=None,
                usecols=[2, 7, 8],
                names=[
                    "sumlev",
                    "logrecno",
                    "geoid",
                ],
                dtype=str,
                low_memory=False,
            )

    for col in geo.columns:
        geo[col] = (
            geo[col]
            .astype("string")
            .str.strip()
        )

    print(f"Geography rows       : {len(geo):,}")
    print(
        "SUMLEV values sample : "
        f"{sorted(geo['sumlev'].dropna().unique())[:30]}"
    )

    blocks = geo.loc[
        geo["sumlev"].eq("750")
    ].copy()

    blocks["logrecno"] = (
        blocks["logrecno"]
        .map(normalize_logrecno)
    )

    print()
    print("Block GEOID examples:")
    print(
        blocks[
            [
                "logrecno",
                "geoid",
            ]
        ]
        .head(20)
        .to_string(index=False)
    )

    # Census PL GEOID values contain the summary-level
    # prefix followed by the underlying geographic code.
    # For SUMLEV 750 the final 15 digits are the complete
    # 2020 Census tabulation-block GEOID:
    #
    #   SS CCC TTTTTT BBBB
    #
    #   state  = 2
    #   county = 3
    #   tract  = 6
    #   block  = 4
    #
    blocks["block_geoid20"] = (
        blocks["geoid"]
        .str.extract(
            r"(\d{15})$",
            expand=False,
        )
    )

    missing_geoid = (
        blocks["block_geoid20"]
        .isna()
        .sum()
    )

    print()
    print(f"Block rows           : {len(blocks):,}")
    print(
        f"Distinct block GEOIDs: "
        f"{blocks['block_geoid20'].nunique():,}"
    )
    print(
        f"Distinct LOGRECNO    : "
        f"{blocks['logrecno'].nunique():,}"
    )
    print(
        f"Unparsed block GEOIDs: "
        f"{missing_geoid:,}"
    )

    if missing_geoid:
        print()
        print("Unparsed GEOID examples:")
        print(
            blocks.loc[
                blocks["block_geoid20"].isna(),
                [
                    "logrecno",
                    "geoid",
                ],
            ]
            .head(20)
            .to_string(index=False)
        )

        raise RuntimeError(
            "Some SUMLEV 750 GEOIDs could not be "
            "parsed as 15-digit Census blocks."
        )

    if blocks["block_geoid20"].duplicated().any():
        dupes = blocks.loc[
            blocks["block_geoid20"].duplicated(
                keep=False
            ),
            [
                "logrecno",
                "geoid",
                "block_geoid20",
            ],
        ].sort_values(
            "block_geoid20"
        )

        print()
        print("Duplicate block GEOID examples:")
        print(
            dupes.head(40).to_string(
                index=False
            )
        )

        raise RuntimeError(
            "Duplicate block GEOIDs in PL geography."
        )

    if blocks["logrecno"].duplicated().any():
        raise RuntimeError(
            "Duplicate block LOGRECNO values."
        )

    return blocks[
        [
            "logrecno",
            "block_geoid20",
        ]
    ]   


def read_p1_total_population() -> pd.DataFrame:
    """
    PL Segment 1 is pipe-delimited.

    Initial fields are:
      FILEID
      STUSAB
      CHARITER
      CIFSN
      LOGRECNO

    P0010001 is total population and is the first
    P1 data field following LOGRECNO.
    """

    print()
    print("=" * 88)
    print("READ PL SEGMENT 1 - P1 TOTAL POPULATION")
    print("=" * 88)

    with zipfile.ZipFile(PL_ZIP) as zf:
        with zf.open(SEG1_MEMBER) as f:
            seg1 = pd.read_csv(
                f,
                sep="|",
                header=None,
                usecols=[4, 5],
                names=[
                    "logrecno",
                    "p0010001",
                ],
                dtype=str,
            )

    seg1["logrecno"] = (
        seg1["logrecno"]
        .map(normalize_logrecno)
    )

    seg1["p0010001"] = pd.to_numeric(
        seg1["p0010001"],
        errors="raise",
    ).astype("int64")

    print(f"Segment 1 rows       : {len(seg1):,}")
    print(
        f"Distinct LOGRECNO    : "
        f"{seg1['logrecno'].nunique():,}"
    )

    if seg1["logrecno"].duplicated().any():
        raise RuntimeError(
            "Duplicate LOGRECNO values in PL Segment 1."
        )

    return seg1


def build_block_population() -> pd.DataFrame:
    geo = read_geography()
    pop = read_p1_total_population()

    blocks = geo.merge(
        pop,
        on="logrecno",
        how="left",
        validate="one_to_one",
        indicator=True,
    )

    print()
    print("=" * 88)
    print("PL GEOGRAPHY + POPULATION JOIN")
    print("=" * 88)

    print(
        blocks["_merge"]
        .value_counts(dropna=False)
        .to_string()
    )

    missing = blocks["p0010001"].isna().sum()

    print(f"Missing population   : {missing:,}")

    if missing:
        raise RuntimeError(
            "Some PL block geography rows have no "
            "P1 population."
        )

    blocks = blocks.drop(columns="_merge")

    total_pop = int(blocks["p0010001"].sum())

    print(f"Block population sum : {total_pop:,}")
    print(f"Expected WA total    : {EXPECTED_WA_POP:,}")
    print(
        f"Difference           : "
        f"{total_pop - EXPECTED_WA_POP:+,}"
    )

    if total_pop != EXPECTED_WA_POP:
        raise RuntimeError(
            "Washington PL block population does not "
            "reconcile to the expected 2020 Census "
            "population."
        )

    OUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    blocks[
        [
            "block_geoid20",
            "p0010001",
        ]
    ].to_csv(
        OUT_BLOCK_POP,
        index=False,
    )

    print()
    print(
        f"Wrote                : "
        f"{OUT_BLOCK_POP.relative_to(ROOT)}"
    )
    print(
        f"SHA-256              : "
        f"{sha256(OUT_BLOCK_POP)}"
    )

    return blocks


def attach_zcta(blocks: pd.DataFrame) -> None:
    print()
    print("=" * 88)
    print("ATTACH ZCTA RELATIONSHIP")
    print("=" * 88)

    rel = pd.read_csv(
        REL_PATH,
        dtype=str,
    )

    print(f"Relationship rows    : {len(rel):,}")
    print(
        f"Relationship blocks  : "
        f"{rel['block_geoid20'].nunique():,}"
    )

    joined = rel.merge(
        blocks[
            [
                "block_geoid20",
                "p0010001",
            ]
        ],
        on="block_geoid20",
        how="left",
        validate="one_to_one",
        indicator=True,
    )

    print()
    print("Join status:")
    print(
        joined["_merge"]
        .value_counts(dropna=False)
        .to_string()
    )

    missing = joined["p0010001"].isna().sum()

    print()
    print(f"Missing POP20        : {missing:,}")

    if missing:
        print()
        print("First missing blocks:")
        print(
            joined.loc[
                joined["p0010001"].isna(),
                [
                    "block_geoid20",
                    "zcta5ce20",
                ],
            ]
            .head(20)
            .to_string(index=False)
        )

        raise RuntimeError(
            "Some relationship blocks failed to join "
            "to PL population."
        )

    joined = joined.drop(columns="_merge")

    joined["p0010001"] = (
        joined["p0010001"]
        .astype("int64")
    )

    total_relationship_pop = int(
        joined["p0010001"].sum()
    )

    unassigned = joined.loc[
        joined["zcta5ce20"].eq("00000")
    ]

    unassigned_blocks = len(unassigned)

    unassigned_pop = int(
        unassigned["p0010001"].sum()
    )

    assigned = joined.loc[
        ~joined["zcta5ce20"].eq("00000")
    ]

    assigned_pop = int(
        assigned["p0010001"].sum()
    )

    print()
    print("=" * 88)
    print("ZCTA POPULATION COVERAGE")
    print("=" * 88)

    print(
        f"All relationship blocks : "
        f"{len(joined):,}"
    )
    print(
        f"All relationship pop    : "
        f"{total_relationship_pop:,}"
    )
    print()
    print(
        f"ZCTA 00000 blocks       : "
        f"{unassigned_blocks:,}"
    )
    print(
        f"ZCTA 00000 population   : "
        f"{unassigned_pop:,}"
    )
    print(
        f"ZCTA 00000 pop share    : "
        f"{unassigned_pop / total_relationship_pop:.8%}"
    )
    print()
    print(
        f"Assigned-ZCTA blocks    : "
        f"{len(assigned):,}"
    )
    print(
        f"Assigned-ZCTA population: "
        f"{assigned_pop:,}"
    )
    print(
        f"Assigned pop share      : "
        f"{assigned_pop / total_relationship_pop:.8%}"
    )

    print()
    print(
        f"WA Census population    : "
        f"{EXPECTED_WA_POP:,}"
    )
    print(
        f"Relationship difference : "
        f"{total_relationship_pop - EXPECTED_WA_POP:+,}"
    )

    print()
    print("Largest ZCTAs by population:")
    print(
        assigned.groupby(
            "zcta5ce20",
            as_index=False,
        )["p0010001"]
        .sum()
        .sort_values(
            "p0010001",
            ascending=False,
        )
        .head(20)
        .to_string(index=False)
    )

    joined[
        [
            "block_geoid20",
            "zcta5ce20",
            "p0010001",
        ]
    ].to_csv(
        OUT_JOINED,
        index=False,
    )

    print()
    print(
        f"Wrote                : "
        f"{OUT_JOINED.relative_to(ROOT)}"
    )
    print(
        f"SHA-256              : "
        f"{sha256(OUT_JOINED)}"
    )


def main() -> int:
    print("=" * 88)
    print(
        "MILLIONAIRE TAX LD MODEL - "
        "CD VALIDATION BLOCK POPULATION"
    )
    print("=" * 88)

    print()
    print("POPULATION ATTACHMENT ONLY")
    print("NO IRS ALLOCATION")
    print("NO MODEL FITTING")
    print("NO LD MILLIONAIRE ESTIMATES")
    print("NO DATABASE WRITES")

    for path in (
        PL_ZIP,
        REL_PATH,
    ):
        if not path.exists():
            raise FileNotFoundError(path)

    print()
    print("SOURCE")
    print("-" * 88)
    print(
        f"PL ZIP    : {PL_ZIP.relative_to(ROOT)}"
    )
    print(
        f"Bytes     : {PL_ZIP.stat().st_size:,}"
    )
    print(
        f"SHA-256   : {sha256(PL_ZIP)}"
    )

    blocks = build_block_population()
    attach_zcta(blocks)

    print()
    print("=" * 88)
    print("BLOCK POPULATION STAGE COMPLETE")
    print("=" * 88)

    return 0


if __name__ == "__main__":
    sys.exit(main())