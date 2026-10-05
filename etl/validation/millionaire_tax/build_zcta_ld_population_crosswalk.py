from __future__ import annotations

import hashlib
import sys
import zipfile
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]

CD_PROCESSED_DIR = (
    ROOT
    / "data"
    / "processed"
    / "validation"
    / "irs_cd_ty2022"
)

LD_PROCESSED_DIR = (
    ROOT
    / "data"
    / "processed"
    / "validation"
    / "irs_ld_ty2022"
)

ZCTA_BLOCK_POP = (
    CD_PROCESSED_DIR
    / "wa_zcta_block_population_2020.csv"
)

BAF_ZIP = (
    ROOT
    / "data"
    / "raw"
    / "census"
    / "congressional_district_validation"
    / "BlockAssign_ST53_WA.zip"
)

BAF_SLDL_MEMBER = "BlockAssign_ST53_WA_SLDL.txt"
BAF_SLDU_MEMBER = "BlockAssign_ST53_WA_SLDU.txt"

OUT_BLOCK = (
    LD_PROCESSED_DIR
    / "wa_zcta_block_population_ld.csv"
)

OUT_CROSSWALK = (
    LD_PROCESSED_DIR
    / "wa_zcta_ld_population_weights.csv"
)


EXPECTED_BLOCKS = 158_093
EXPECTED_WA_POP = 7_705_281
EXPECTED_UNASSIGNED_ZCTA_POP = 90
EXPECTED_WEIGHT_UNIVERSE_POP = 7_705_191

EXPECTED_DISTRICTS = {
    f"{i:03d}" for i in range(1, 50)
}

EXPECTED_ZERO_POP_ZCTAS = {
    "98154",
    "98158",
    "98174",
    "98430",
}

EXPECTED_POSITIVE_POP_ZCTAS = 602


def sha256(path: Path) -> str:
    h = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(
            lambda: f.read(1024 * 1024),
            b"",
        ):
            h.update(chunk)

    return h.hexdigest()


def read_zcta_block_population() -> pd.DataFrame:
    print()
    print("=" * 92)
    print("READ ZCTA + BLOCK + POPULATION")
    print("=" * 92)

    df = pd.read_csv(
        ZCTA_BLOCK_POP,
        dtype={
            "block_geoid20": str,
            "zcta5ce20": str,
            "p0010001": "int64",
        },
    )

    df["block_geoid20"] = (
        df["block_geoid20"]
        .str.strip()
        .str.zfill(15)
    )

    df["zcta5ce20"] = (
        df["zcta5ce20"]
        .str.strip()
        .str.zfill(5)
    )

    print(f"Rows                 : {len(df):,}")
    print(
        f"Distinct blocks      : "
        f"{df['block_geoid20'].nunique():,}"
    )
    print(
        f"Population           : "
        f"{df['p0010001'].sum():,}"
    )

    if len(df) != EXPECTED_BLOCKS:
        raise RuntimeError(
            "Unexpected ZCTA/block row count."
        )

    if df["block_geoid20"].nunique() != EXPECTED_BLOCKS:
        raise RuntimeError(
            "Unexpected distinct block count."
        )

    if df["block_geoid20"].duplicated().any():
        raise RuntimeError(
            "Duplicate block GEOIDs in ZCTA population file."
        )

    if int(df["p0010001"].sum()) != EXPECTED_WA_POP:
        raise RuntimeError(
            "ZCTA/block population does not reconcile "
            "to Washington population."
        )

    return df


def read_baf_assignment(
    member: str,
    district_column: str,
    label: str,
) -> pd.DataFrame:
    print()
    print("=" * 92)
    print(f"READ CENSUS {label} BLOCK ASSIGNMENT")
    print("=" * 92)

    with zipfile.ZipFile(BAF_ZIP) as zf:
        with zf.open(member) as f:
            df = pd.read_csv(
                f,
                sep="|",
                dtype=str,
            )

    expected_columns = {"BLOCKID", "DISTRICT"}

    if not expected_columns.issubset(df.columns):
        raise RuntimeError(
            f"{label} BAF member does not contain "
            f"expected columns {sorted(expected_columns)}."
        )

    df = df.rename(
        columns={
            "BLOCKID": "block_geoid20",
            "DISTRICT": district_column,
        }
    )

    df["block_geoid20"] = (
        df["block_geoid20"]
        .str.strip()
        .str.zfill(15)
    )

    df[district_column] = (
        df[district_column]
        .str.strip()
        .str.zfill(3)
    )

    print(f"Rows                 : {len(df):,}")
    print(
        f"Distinct blocks      : "
        f"{df['block_geoid20'].nunique():,}"
    )
    print(
        f"Duplicate blocks     : "
        f"{df['block_geoid20'].duplicated().sum():,}"
    )
    print(
        f"Missing district     : "
        f"{df[district_column].isna().sum():,}"
    )

    observed_districts = set(
        df[district_column]
        .dropna()
        .unique()
    )

    print(
        f"Distinct districts   : "
        f"{len(observed_districts):,}"
    )
    print(
        "District range       : "
        f"{min(observed_districts)} - "
        f"{max(observed_districts)}"
    )

    if len(df) != EXPECTED_BLOCKS:
        raise RuntimeError(
            f"Unexpected {label} assignment row count."
        )

    if df["block_geoid20"].nunique() != EXPECTED_BLOCKS:
        raise RuntimeError(
            f"Unexpected distinct {label} block count."
        )

    if df["block_geoid20"].duplicated().any():
        raise RuntimeError(
            f"Duplicate blocks in {label} assignment."
        )

    if df[district_column].isna().any():
        raise RuntimeError(
            f"Missing district values in {label} assignment."
        )

    if observed_districts != EXPECTED_DISTRICTS:
        raise RuntimeError(
            f"Unexpected {label} district set: "
            f"{sorted(observed_districts)}"
        )

    return df[
        [
            "block_geoid20",
            district_column,
        ]
    ]


def validate_sldl_sldu(
    sldl: pd.DataFrame,
    sldu: pd.DataFrame,
) -> None:
    print()
    print("=" * 92)
    print("VALIDATE SLDL AGAINST SLDU")
    print("=" * 92)

    comparison = sldl.merge(
        sldu,
        on="block_geoid20",
        how="outer",
        validate="one_to_one",
        indicator=True,
    )

    left_only = int(
        comparison["_merge"].eq("left_only").sum()
    )

    right_only = int(
        comparison["_merge"].eq("right_only").sum()
    )

    both = comparison["_merge"].eq("both")

    mismatch = int(
        (
            comparison.loc[both, "sldl"]
            != comparison.loc[both, "sldu"]
        ).sum()
    )

    print(
        f"SLDL rows             : "
        f"{len(sldl):,}"
    )
    print(
        f"SLDU rows             : "
        f"{len(sldu):,}"
    )
    print(
        f"SLDL-only blocks      : "
        f"{left_only:,}"
    )
    print(
        f"SLDU-only blocks      : "
        f"{right_only:,}"
    )
    print(
        f"District mismatches   : "
        f"{mismatch:,}"
    )

    if left_only != 0:
        raise RuntimeError(
            "Some SLDL blocks are absent from SLDU."
        )

    if right_only != 0:
        raise RuntimeError(
            "Some SLDU blocks are absent from SLDL."
        )

    if mismatch != 0:
        raise RuntimeError(
            "SLDL and SLDU district assignments differ."
        )

    print()
    print("SLDL / SLDU identity  : PASS")


def join_blocks(
    zcta: pd.DataFrame,
    sldl: pd.DataFrame,
) -> pd.DataFrame:
    print()
    print("=" * 92)
    print("JOIN BLOCKS TO WASHINGTON LEGISLATIVE DISTRICTS")
    print("=" * 92)

    joined = zcta.merge(
        sldl,
        on="block_geoid20",
        how="left",
        validate="one_to_one",
        indicator=True,
    )

    print("Join status:")
    print(
        joined["_merge"]
        .value_counts(dropna=False)
        .to_string()
    )

    missing_ld = int(
        joined["sldl"].isna().sum()
    )

    print()
    print(
        f"Missing LD assignment : "
        f"{missing_ld:,}"
    )

    if missing_ld:
        raise RuntimeError(
            "Some blocks lack a legislative district."
        )

    joined = joined.drop(columns="_merge")

    total_pop = int(
        joined["p0010001"].sum()
    )

    print(
        f"Joined population     : "
        f"{total_pop:,}"
    )

    if total_pop != EXPECTED_WA_POP:
        raise RuntimeError(
            "Joined population does not reconcile."
        )

    LD_PROCESSED_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    joined.to_csv(
        OUT_BLOCK,
        index=False,
    )

    print()
    print(
        f"Wrote                 : "
        f"{OUT_BLOCK.relative_to(ROOT)}"
    )
    print(
        f"SHA-256               : "
        f"{sha256(OUT_BLOCK)}"
    )

    return joined


def build_crosswalk(
    joined: pd.DataFrame,
) -> pd.DataFrame:
    print()
    print("=" * 92)
    print("BUILD ZCTA x LEGISLATIVE DISTRICT POPULATION WEIGHTS")
    print("=" * 92)

    unassigned = joined.loc[
        joined["zcta5ce20"].eq("00000")
    ].copy()

    unassigned_pop = int(
        unassigned["p0010001"].sum()
    )

    print(
        f"ZCTA 00000 blocks     : "
        f"{len(unassigned):,}"
    )
    print(
        f"ZCTA 00000 population : "
        f"{unassigned_pop:,}"
    )

    if unassigned_pop != EXPECTED_UNASSIGNED_ZCTA_POP:
        raise RuntimeError(
            "Unexpected ZCTA 00000 population."
        )

    # ZCTA 00000 is retained in the block-level provenance
    # file but excluded from ZIP/ZCTA allocation weights.
    assigned = joined.loc[
        ~joined["zcta5ce20"].eq("00000")
    ].copy()

    assigned_pop = int(
        assigned["p0010001"].sum()
    )

    print(
        f"Weight-universe pop   : "
        f"{assigned_pop:,}"
    )

    if assigned_pop != EXPECTED_WEIGHT_UNIVERSE_POP:
        raise RuntimeError(
            "Unexpected ZCTA weight-universe population."
        )

    grouped = (
        assigned.groupby(
            [
                "zcta5ce20",
                "sldl",
            ],
            as_index=False,
        )
        .agg(
            population=("p0010001", "sum"),
            block_count=("block_geoid20", "size"),
        )
    )

    zcta_totals = (
        grouped.groupby(
            "zcta5ce20"
        )["population"]
        .transform("sum")
    )

    grouped["zcta_population"] = zcta_totals

    zero_pop_zctas = set(
        grouped.loc[
            grouped["zcta_population"].eq(0),
            "zcta5ce20",
        ]
        .drop_duplicates()
        .tolist()
    )

    print()
    print(
        f"Zero-population ZCTAs : "
        f"{len(zero_pop_zctas):,}"
    )

    if zero_pop_zctas:
        print(
            "Zero-population codes : "
            + ", ".join(
                sorted(zero_pop_zctas)
            )
        )

    if zero_pop_zctas != EXPECTED_ZERO_POP_ZCTAS:
        raise RuntimeError(
            "Unexpected zero-population ZCTA set: "
            f"{sorted(zero_pop_zctas)}"
        )

    positive_pop = grouped[
        "zcta_population"
    ].gt(0)

    grouped["population_weight"] = pd.NA

    grouped.loc[
        positive_pop,
        "population_weight",
    ] = (
        grouped.loc[
            positive_pop,
            "population",
        ]
        / grouped.loc[
            positive_pop,
            "zcta_population",
        ]
    )

    grouped["population_weight"] = pd.to_numeric(
        grouped["population_weight"],
        errors="coerce",
    )

    weight_check = (
        grouped.loc[positive_pop]
        .groupby("zcta5ce20")[
            "population_weight"
        ]
        .sum()
    )

    max_weight_error = float(
        (weight_check - 1.0)
        .abs()
        .max()
    )

    print(
        f"Positive-pop ZCTAs    : "
        f"{weight_check.size:,}"
    )
    print(
        f"Max weight-sum error  : "
        f"{max_weight_error:.15f}"
    )

    if weight_check.size != EXPECTED_POSITIVE_POP_ZCTAS:
        raise RuntimeError(
            "Unexpected positive-population ZCTA count."
        )

    if max_weight_error > 1e-12:
        raise RuntimeError(
            "Positive-population ZCTA weights "
            "do not sum to 1."
        )

    print()
    print(
        f"Distinct ZCTAs        : "
        f"{grouped['zcta5ce20'].nunique():,}"
    )
    print(
        f"ZCTA x LD rows        : "
        f"{len(grouped):,}"
    )

    observed_lds = set(
        grouped["sldl"]
        .dropna()
        .unique()
    )

    if observed_lds != EXPECTED_DISTRICTS:
        raise RuntimeError(
            "Crosswalk does not contain exactly LD001-LD049."
        )

    ld_summary = (
        assigned.groupby(
            "sldl",
            as_index=False,
        )
        .agg(
            population=("p0010001", "sum"),
            block_count=("block_geoid20", "size"),
        )
    )

    ld_summary["population_share"] = (
        ld_summary["population"]
        / assigned_pop
    )

    print()
    print("Legislative District population:")
    print(
        ld_summary.to_string(
            index=False,
            formatters={
                "population_share":
                    lambda x: f"{x:.6%}"
            },
        )
    )

    split_counts = (
        grouped.groupby("zcta5ce20")
        .size()
    )

    print()
    print("ZCTA legislative-district split profile:")
    print(
        split_counts
        .value_counts()
        .sort_index()
        .rename_axis("district_count")
        .to_frame("zcta_count")
        .to_string()
    )

    split_zctas = int(
        (split_counts > 1).sum()
    )

    print()
    print(
        f"ZCTAs crossing LDs    : "
        f"{split_zctas:,}"
    )

    grouped = grouped.sort_values(
        [
            "zcta5ce20",
            "sldl",
        ]
    ).reset_index(drop=True)

    grouped.to_csv(
        OUT_CROSSWALK,
        index=False,
    )

    print()
    print(
        f"Wrote                 : "
        f"{OUT_CROSSWALK.relative_to(ROOT)}"
    )
    print(
        f"SHA-256               : "
        f"{sha256(OUT_CROSSWALK)}"
    )

    return grouped


def main() -> int:
    print("=" * 92)
    print(
        "MILLIONAIRE TAX LD MODEL - "
        "ZCTA TO LEGISLATIVE DISTRICT POPULATION CROSSWALK"
    )
    print("=" * 92)

    print()
    print("STAGE 6A - GEOGRAPHIC CROSSWALK ONLY")
    print("NO IRS ALLOCATION")
    print("NO MODEL FITTING")
    print("NO LD MILLIONAIRE ESTIMATES")
    print("NO HISTORICAL MILLIONAIRE INPUTS")
    print("NO DATABASE WRITES")

    for path in (
        ZCTA_BLOCK_POP,
        BAF_ZIP,
    ):
        if not path.exists():
            raise FileNotFoundError(path)

    print()
    print("SOURCES")
    print("-" * 92)

    print(
        f"ZCTA/block/pop : "
        f"{ZCTA_BLOCK_POP.relative_to(ROOT)}"
    )
    print(
        f"SHA-256        : "
        f"{sha256(ZCTA_BLOCK_POP)}"
    )

    print()
    print(
        f"BAF ZIP        : "
        f"{BAF_ZIP.relative_to(ROOT)}"
    )
    print(
        f"Bytes          : "
        f"{BAF_ZIP.stat().st_size:,}"
    )
    print(
        f"SHA-256        : "
        f"{sha256(BAF_ZIP)}"
    )
    print(
        f"SLDL member    : "
        f"{BAF_SLDL_MEMBER}"
    )
    print(
        f"SLDU member    : "
        f"{BAF_SLDU_MEMBER}"
    )

    zcta = read_zcta_block_population()

    sldl = read_baf_assignment(
        BAF_SLDL_MEMBER,
        "sldl",
        "SLDL",
    )

    sldu = read_baf_assignment(
        BAF_SLDU_MEMBER,
        "sldu",
        "SLDU",
    )

    validate_sldl_sldu(
        sldl,
        sldu,
    )

    joined = join_blocks(
        zcta,
        sldl,
    )

    build_crosswalk(
        joined,
    )

    print()
    print("=" * 92)
    print("STAGE 6A ZCTA TO LD CROSSWALK COMPLETE")
    print("=" * 92)

    print()
    print("VALIDATION")
    print("-" * 92)
    print("158,093 ZCTA/population blocks       : PASS")
    print("158,093 SLDL assignment blocks       : PASS")
    print("158,093 SLDU assignment blocks       : PASS")
    print("SLDL/SLDU block sets identical       : PASS")
    print("SLDL/SLDU assignments identical      : PASS")
    print("49 legislative districts             : PASS")
    print("Washington population = 7,705,281    : PASS")
    print("ZCTA 00000 population = 90           : PASS")
    print("Weight-universe population 7,705,191 : PASS")
    print("602 positive-population ZCTAs         : PASS")
    print("4 zero-population ZCTAs explicit      : PASS")
    print("Positive-ZCTA weights sum to 1        : PASS")

    return 0


if __name__ == "__main__":
    sys.exit(main())