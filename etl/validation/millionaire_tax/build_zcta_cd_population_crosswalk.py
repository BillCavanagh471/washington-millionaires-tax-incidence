from __future__ import annotations

import hashlib
import sys
import zipfile
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]

PROCESSED_DIR = (
    ROOT
    / "data"
    / "processed"
    / "validation"
    / "irs_cd_ty2022"
)

ZCTA_BLOCK_POP = (
    PROCESSED_DIR
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

BAF_MEMBER = "BlockAssign_ST53_WA_CD.txt"

OUT_BLOCK = (
    PROCESSED_DIR
    / "wa_zcta_block_population_cd116.csv"
)

OUT_CROSSWALK = (
    PROCESSED_DIR
    / "wa_zcta_cd116_population_weights.csv"
)

EXPECTED_BLOCKS = 158_093
EXPECTED_WA_POP = 7_705_281
EXPECTED_UNASSIGNED_ZCTA_POP = 90
EXPECTED_DISTRICTS = {
    f"{i:02d}" for i in range(1, 11)
}


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
    print("=" * 88)
    print("READ ZCTA + BLOCK + POPULATION")
    print("=" * 88)

    df = pd.read_csv(
        ZCTA_BLOCK_POP,
        dtype={
            "block_geoid20": str,
            "zcta5ce20": str,
            "p0010001": "int64",
        },
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


def read_cd_assignment() -> pd.DataFrame:
    print()
    print("=" * 88)
    print("READ CENSUS CD BLOCK ASSIGNMENT")
    print("=" * 88)

    with zipfile.ZipFile(BAF_ZIP) as zf:
        with zf.open(BAF_MEMBER) as f:
            cd = pd.read_csv(
                f,
                sep="|",
                dtype=str,
            )

    cd = cd.rename(
        columns={
            "BLOCKID": "block_geoid20",
            "DISTRICT": "cd116",
        }
    )

    cd["block_geoid20"] = (
        cd["block_geoid20"]
        .str.strip()
        .str.zfill(15)
    )

    cd["cd116"] = (
        cd["cd116"]
        .str.strip()
        .str.zfill(2)
    )

    print(f"Rows                 : {len(cd):,}")
    print(
        f"Distinct blocks      : "
        f"{cd['block_geoid20'].nunique():,}"
    )
    print(
        f"Duplicate blocks     : "
        f"{cd['block_geoid20'].duplicated().sum():,}"
    )
    print(
        f"Missing district     : "
        f"{cd['cd116'].isna().sum():,}"
    )
    print(
        "Districts            : "
        f"{sorted(cd['cd116'].dropna().unique())}"
    )

    if len(cd) != EXPECTED_BLOCKS:
        raise RuntimeError(
            "Unexpected CD assignment row count."
        )

    if cd["block_geoid20"].nunique() != EXPECTED_BLOCKS:
        raise RuntimeError(
            "Unexpected distinct CD block count."
        )

    if cd["block_geoid20"].duplicated().any():
        raise RuntimeError(
            "Duplicate blocks in CD assignment."
        )

    observed_districts = set(
        cd["cd116"].dropna().unique()
    )

    if observed_districts != EXPECTED_DISTRICTS:
        raise RuntimeError(
            "Unexpected Congressional District set: "
            f"{sorted(observed_districts)}"
        )

    return cd[
        [
            "block_geoid20",
            "cd116",
        ]
    ]


def join_blocks(
    zcta: pd.DataFrame,
    cd: pd.DataFrame,
) -> pd.DataFrame:
    print()
    print("=" * 88)
    print("JOIN BLOCKS TO CONGRESSIONAL DISTRICTS")
    print("=" * 88)

    joined = zcta.merge(
        cd,
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

    missing_cd = joined["cd116"].isna().sum()

    print()
    print(f"Missing CD assignment: {missing_cd:,}")

    if missing_cd:
        raise RuntimeError(
            "Some blocks lack a Congressional District."
        )

    joined = joined.drop(columns="_merge")

    total_pop = int(
        joined["p0010001"].sum()
    )

    print(
        f"Joined population    : "
        f"{total_pop:,}"
    )

    if total_pop != EXPECTED_WA_POP:
        raise RuntimeError(
            "Joined population does not reconcile."
        )

    joined.to_csv(
        OUT_BLOCK,
        index=False,
    )

    print()
    print(
        f"Wrote                : "
        f"{OUT_BLOCK.relative_to(ROOT)}"
    )
    print(
        f"SHA-256              : "
        f"{sha256(OUT_BLOCK)}"
    )

    return joined


def build_crosswalk(
    joined: pd.DataFrame,
) -> pd.DataFrame:
    print()
    print("=" * 88)
    print("BUILD ZCTA x CD116 POPULATION WEIGHTS")
    print("=" * 88)

    unassigned = joined.loc[
        joined["zcta5ce20"].eq("00000")
    ].copy()

    unassigned_pop = int(
        unassigned["p0010001"].sum()
    )

    print(
        f"ZCTA 00000 blocks    : "
        f"{len(unassigned):,}"
    )
    print(
        f"ZCTA 00000 population: "
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
        f"Weight-universe pop  : "
        f"{assigned_pop:,}"
    )

    grouped = (
        assigned.groupby(
            [
                "zcta5ce20",
                "cd116",
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

    zero_pop_zctas = (
        grouped.loc[
            grouped["zcta_population"].eq(0),
            "zcta5ce20",
        ]
        .drop_duplicates()
        .sort_values()
    )

    print()
    print(
        f"Zero-population ZCTAs: "
        f"{len(zero_pop_zctas):,}"
    )

    if len(zero_pop_zctas):
        print(
            "Zero-population codes : "
        + ", ".join(
            zero_pop_zctas.tolist()
            )
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
        f"Positive-pop ZCTAs   : "
        f"{weight_check.size:,}"
    )
    print(
        f"Max weight-sum error : "
        f"{max_weight_error:.15f}"
    )

    if max_weight_error > 1e-12:
        raise RuntimeError(
            "Positive-population ZCTA weights "
            "do not sum to 1."
        )

    print()
    print(
        f"Distinct ZCTAs       : "
        f"{grouped['zcta5ce20'].nunique():,}"
    )
    print(
        f"ZCTA x CD rows       : "
        f"{len(grouped):,}"
    )
    print(
        f"Max weight-sum error : "
        f"{max_weight_error:.15f}"
    )

    if max_weight_error > 1e-12:
        raise RuntimeError(
            "ZCTA population weights do not sum to 1."
        )

    cd_summary = (
        assigned.groupby(
            "cd116",
            as_index=False,
        )
        .agg(
            population=("p0010001", "sum"),
            block_count=("block_geoid20", "size"),
        )
    )

    cd_summary["population_share"] = (
        cd_summary["population"]
        / assigned_pop
    )

    print()
    print("Congressional District population:")
    print(
        cd_summary.to_string(
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
    print("ZCTA district-split profile:")
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
        f"ZCTAs crossing CDs   : "
        f"{split_zctas:,}"
    )

    grouped = grouped.sort_values(
        [
            "zcta5ce20",
            "cd116",
        ]
    ).reset_index(drop=True)

    grouped.to_csv(
        OUT_CROSSWALK,
        index=False,
    )

    print()
    print(
        f"Wrote                : "
        f"{OUT_CROSSWALK.relative_to(ROOT)}"
    )
    print(
        f"SHA-256              : "
        f"{sha256(OUT_CROSSWALK)}"
    )

    return grouped


def main() -> int:
    print("=" * 88)
    print(
        "MILLIONAIRE TAX LD MODEL - "
        "ZCTA TO CD116 POPULATION CROSSWALK"
    )
    print("=" * 88)

    print()
    print("GEOGRAPHIC CROSSWALK ONLY")
    print("NO IRS ALLOCATION")
    print("NO MODEL FITTING")
    print("NO LD MILLIONAIRE ESTIMATES")
    print("NO DATABASE WRITES")

    for path in (
        ZCTA_BLOCK_POP,
        BAF_ZIP,
    ):
        if not path.exists():
            raise FileNotFoundError(path)

    print()
    print("SOURCES")
    print("-" * 88)

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
        f"BAF member     : "
        f"{BAF_MEMBER}"
    )

    zcta = read_zcta_block_population()
    cd = read_cd_assignment()

    joined = join_blocks(
        zcta,
        cd,
    )

    build_crosswalk(joined)

    print()
    print("=" * 88)
    print("ZCTA TO CD116 CROSSWALK COMPLETE")
    print("=" * 88)

    return 0


if __name__ == "__main__":
    sys.exit(main())