"""
Stage 8 - Map Millionaire Geography v0.2.

Creates an analytical choropleth of modeled TY2022 Washington
legislative-district returns with AGI >= $1 million.

Inputs
------
1. Frozen Stage 7B millionaire geography.
2. Official Census TIGER2020PL Washington SLDL geometry.

Outputs
-------
1. PNG analytical map.
2. CSV geometry/model join audit.

IMPORTANT
---------
- These are modeled estimates, not observed IRS LD counts.
- Fractional expected counts are preserved.
- No integerization.
- No model fitting.
- No historical LD millionaire estimates.
- No database writes.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
import matplotlib as mpl
import numpy as np
import pandas as pd
import shapefile
from matplotlib.patches import Polygon
from matplotlib.collections import PatchCollection


# =============================================================================
# PATHS
# =============================================================================

ROOT = Path(__file__).resolve().parents[3]

MODEL_PATH = (
    ROOT
    / "data"
    / "processed"
    / "validation"
    / "millionaire_count_v0_2"
    / "millionaire_geography_v0_2_ty2022.csv"
)

SHAPEFILE_DIR = (
    ROOT
    / "data"
    / "raw"
    / "census"
    / "legislative_district_geometry"
    / "tl_2020_53_sldl20"
)

SHAPEFILE_PATH = (
    SHAPEFILE_DIR
    / "tl_2020_53_sldl20.shp"
)

SHAPEFILE_ZIP = (
    ROOT
    / "data"
    / "raw"
    / "census"
    / "legislative_district_geometry"
    / "tl_2020_53_sldl20.zip"
)

OUTPUT_DIR = (
    ROOT
    / "data"
    / "processed"
    / "validation"
    / "millionaire_count_v0_2"
    / "stage8_map"
)

MAP_OUTPUT = (
    OUTPUT_DIR
    / "millionaire_geography_v0_2_ty2022_map.png"
)

AUDIT_OUTPUT = (
    OUTPUT_DIR
    / "millionaire_geography_v0_2_ty2022_map_join_audit.csv"
)


# =============================================================================
# FROZEN HASHES
# =============================================================================

EXPECTED_MODEL_SHA256 = (
    "6eb3fc8a02eef8dc73b9a752f6532664ec92cab98d3851c9a574ad004390047a"
)

EXPECTED_GEOMETRY_ZIP_SHA256 = (
    "7dd41cd8f15cc104ceab1c717ecc46692c9e5e31bbb3cbdfbec0bff54de0b030"
)


# =============================================================================
# CONTROLS
# =============================================================================

EXPECTED_LD_COUNT = 49
STATEWIDE_MILLIONAIRE_RETURNS = 21_530


# =============================================================================
# HELPERS
# =============================================================================

def banner(title: str) -> None:
    print()
    print("=" * 100)
    print(title)
    print("=" * 100)
    print()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)

    return h.hexdigest()


def normalize_ld(value: object) -> str:
    text = str(value).strip()

    if text.endswith(".0"):
        text = text[:-2]

    if text.isdigit():
        return text.zfill(3)

    return text


# =============================================================================
# PROVENANCE
# =============================================================================

def validate_sources() -> None:
    banner("STAGE 8 FROZEN SOURCE PROVENANCE")

    require(
        MODEL_PATH.exists(),
        f"Missing Stage 7B model artifact: {MODEL_PATH}",
    )

    require(
        SHAPEFILE_PATH.exists(),
        f"Missing Census shapefile: {SHAPEFILE_PATH}",
    )

    require(
        SHAPEFILE_ZIP.exists(),
        f"Missing Census source ZIP: {SHAPEFILE_ZIP}",
    )

    model_hash = sha256_file(MODEL_PATH)
    geometry_hash = sha256_file(SHAPEFILE_ZIP)

    print(f"Stage 7B model artifact         : {MODEL_PATH.relative_to(ROOT)}")
    print(f"SHA-256                         : {model_hash}")
    print()
    print(f"Census geometry source ZIP      : {SHAPEFILE_ZIP.relative_to(ROOT)}")
    print(f"SHA-256                         : {geometry_hash}")
    print()

    require(
        model_hash.lower() == EXPECTED_MODEL_SHA256.lower(),
        "Stage 7B model artifact hash mismatch.",
    )

    require(
        geometry_hash.lower() == EXPECTED_GEOMETRY_ZIP_SHA256.lower(),
        "Census geometry ZIP hash mismatch.",
    )

    print("Frozen source validation        : PASS")


# =============================================================================
# MODEL DATA
# =============================================================================

def read_model() -> pd.DataFrame:
    banner("READ FROZEN MILLIONAIRE GEOGRAPHY v0.2")

    df = pd.read_csv(
        MODEL_PATH,
        dtype={"ld": str},
    )

    df["ld"] = df["ld"].map(normalize_ld)

    required = [
        "ld",
        "millionaire_share_v0_2",
        "estimated_millionaire_returns_v0_2",
    ]

    for col in required:
        require(
            col in df.columns,
            f"Missing Stage 7B column: {col}",
        )

    require(
        len(df) == EXPECTED_LD_COUNT,
        f"Expected 49 LD rows; found {len(df)}.",
    )

    require(
        df["ld"].nunique() == EXPECTED_LD_COUNT,
        "Stage 7B LD identifiers are not unique.",
    )

    expected_lds = {
        f"{i:03d}"
        for i in range(1, 50)
    }

    require(
        set(df["ld"]) == expected_lds,
        "Stage 7B model universe is not exactly LD001-LD049.",
    )

    estimated_total = float(
        df["estimated_millionaire_returns_v0_2"].sum()
    )

    share_total = float(
        df["millionaire_share_v0_2"].sum()
    )

    require(
        abs(
            estimated_total
            - STATEWIDE_MILLIONAIRE_RETURNS
        ) <= 1e-8,
        "Stage 7B millionaire count does not reconcile to 21,530.",
    )

    require(
        abs(share_total - 1.0) <= 1e-12,
        "Stage 7B millionaire shares do not sum to 1.",
    )

    print(f"LD rows                         : {len(df):,}")
    print(f"Millionaire share total         : {share_total:.15f}")
    print(f"Estimated return total          : {estimated_total:,.12f}")
    print()
    print("Frozen model validation         : PASS")

    return df


# =============================================================================
# CENSUS GEOMETRY
# =============================================================================

def read_geometry():
    banner("READ CENSUS SLDL GEOMETRY")

    reader = shapefile.Reader(
        str(SHAPEFILE_PATH)
    )

    field_names = [
        field[0]
        for field in reader.fields[1:]
    ]

    print(
        "Shapefile fields                : "
        + ", ".join(field_names)
    )

    records = []

    for shape_record in reader.iterShapeRecords():
        attrs = dict(
            zip(
                field_names,
                shape_record.record,
            )
        )

        records.append(
            (
                attrs,
                shape_record.shape,
            )
        )

    print(f"Geometry records                : {len(records):,}")

    require(
        len(records) == EXPECTED_LD_COUNT,
        (
            "Expected 49 SLDL geometry records; "
            f"found {len(records)}."
        ),
    )

    #
    # TIGER/Line legislative district shapefiles normally contain
    # SLDLST20. We inspect and assert rather than silently assuming.
    #
    district_field = None

    for candidate in [
        "SLDLST20",
        "SLDLST",
        "SLDL",
    ]:
        if candidate in field_names:
            district_field = candidate
            break

    require(
        district_field is not None,
        (
            "Could not identify legislative-district code field. "
            f"Fields present: {field_names}"
        ),
    )

    print(f"District-code field             : {district_field}")

    geometry_lds = {
        normalize_ld(attrs[district_field])
        for attrs, _ in records
    }

    expected_lds = {
        f"{i:03d}"
        for i in range(1, 50)
    }

    require(
        geometry_lds == expected_lds,
        (
            "Census geometry district universe is not "
            "exactly LD001-LD049."
        ),
    )

    print("Geometry LD universe            : PASS")

    return records, district_field


# =============================================================================
# POLYGON HELPERS
# =============================================================================

def shape_parts(shape):
    """
    Yield each polygon part from a pyshp shape.
    """

    points = np.asarray(
        shape.points,
        dtype=float,
    )

    part_starts = list(shape.parts)
    part_starts.append(len(points))

    for start, end in zip(
        part_starts[:-1],
        part_starts[1:],
    ):
        part = points[start:end]

        if len(part) >= 3:
            yield part


def polygon_centroid_approx(shape):
    """
    Approximate label point using the mean of all polygon vertices.

    This is deliberately only a display-label location and has no
    analytical role.
    """

    points = np.asarray(
        shape.points,
        dtype=float,
    )

    return (
        float(points[:, 0].mean()),
        float(points[:, 1].mean()),
    )


# =============================================================================
# JOIN AUDIT
# =============================================================================

def build_join_audit(
    model: pd.DataFrame,
    records,
    district_field: str,
) -> pd.DataFrame:
    banner("JOIN MODEL TO CENSUS GEOMETRY")

    model_lookup = (
        model
        .set_index("ld")
        .to_dict(orient="index")
    )

    rows = []

    for attrs, shape in records:
        ld = normalize_ld(
            attrs[district_field]
        )

        require(
            ld in model_lookup,
            f"Geometry LD{ld} has no Stage 7B model row.",
        )

        model_row = model_lookup[ld]

        label_x, label_y = polygon_centroid_approx(
            shape
        )

        rows.append(
            {
                "ld": ld,
                "geometry_found": True,
                "millionaire_share_v0_2":
                    model_row["millionaire_share_v0_2"],
                "estimated_millionaire_returns_v0_2":
                    model_row[
                        "estimated_millionaire_returns_v0_2"
                    ],
                "label_x": label_x,
                "label_y": label_y,
            }
        )

    audit = pd.DataFrame(rows)

    require(
        len(audit) == EXPECTED_LD_COUNT,
        "Joined map audit does not contain 49 LDs.",
    )

    require(
        audit["ld"].nunique() == EXPECTED_LD_COUNT,
        "Joined map audit contains duplicate LDs.",
    )

    require(
        audit["geometry_found"].all(),
        "One or more model LDs lack geometry.",
    )

    require(
        abs(
            float(
                audit[
                    "estimated_millionaire_returns_v0_2"
                ].sum()
            )
            - STATEWIDE_MILLIONAIRE_RETURNS
        ) <= 1e-8,
        "Map join changed the statewide millionaire total.",
    )

    print(f"Joined LD rows                  : {len(audit):,}")
    print(f"Missing model rows              : 0")
    print(f"Missing geometry rows           : 0")
    print(
        "Joined millionaire total       : "
        f"{audit['estimated_millionaire_returns_v0_2'].sum():,.12f}"
    )
    print()
    print("One-to-one map join             : PASS")

    return audit


# =============================================================================
# MAP
# =============================================================================

def create_map(
    model: pd.DataFrame,
    records,
    district_field: str,
) -> None:
    banner("RENDER ANALYTICAL CHOROPLETH")

    model_lookup = (
        model
        .set_index("ld")
        .to_dict(orient="index")
    )

    patches = []
    values = []

    all_x = []
    all_y = []

    for attrs, shape in records:
        ld = normalize_ld(
            attrs[district_field]
        )

        value = float(
            model_lookup[ld][
                "estimated_millionaire_returns_v0_2"
            ]
        )

        for part in shape_parts(shape):
            patches.append(
                Polygon(
                    part,
                    closed=True,
                )
            )

            values.append(value)

            all_x.extend(part[:, 0])
            all_y.extend(part[:, 1])

    values_array = np.asarray(
        values,
        dtype=float,
    )

    #
    # Linear scale is deliberate for the first analytical map.
    # We do not quantile-bin the data because we want the visual
    # differences to preserve magnitude.
    #
    norm = mpl.colors.Normalize(
        vmin=float(model[
            "estimated_millionaire_returns_v0_2"
        ].min()),
        vmax=float(model[
            "estimated_millionaire_returns_v0_2"
        ].max()),
    )

    cmap = plt.get_cmap("viridis")

    fig, ax = plt.subplots(
        figsize=(12, 10),
    )

    collection = PatchCollection(
        patches,
        cmap=cmap,
        norm=norm,
        edgecolor="white",
        linewidth=0.65,
    )

    collection.set_array(
        values_array
    )

    ax.add_collection(collection)

    #
    # Label every LD.
    #
    for attrs, shape in records:
        ld = normalize_ld(
            attrs[district_field]
        )

        x, y = polygon_centroid_approx(
            shape
        )

        value = float(
            model_lookup[ld][
                "estimated_millionaire_returns_v0_2"
            ]
        )

        label = (
            f"{int(ld)}\n"
            f"{value:,.0f}"
        )

        text = ax.text(
            x,
            y,
            label,
            ha="center",
            va="center",
            fontsize=6.3,
            fontweight="bold",
        )

        text.set_path_effects(
            [
                pe.withStroke(
                    linewidth=2.0,
                    foreground="white",
                )
            ]
        )

    min_x = min(all_x)
    max_x = max(all_x)
    min_y = min(all_y)
    max_y = max(all_y)

    x_pad = (max_x - min_x) * 0.02
    y_pad = (max_y - min_y) * 0.02

    ax.set_xlim(
        min_x - x_pad,
        max_x + x_pad,
    )

    ax.set_ylim(
        min_y - y_pad,
        max_y + y_pad,
    )

    ax.set_aspect(
        "equal",
        adjustable="box",
    )

    ax.axis("off")

    ax.set_title(
        "Washington Legislative Districts\n"
        "Estimated TY2022 Returns with AGI >= $1 Million",
        fontsize=17,
        fontweight="bold",
        pad=18,
    )

    ax.text(
        0.5,
        1.01,
        (
            "Millionaire Geography v0.2 | "
            "Modeled estimates reconciled to IRS statewide control of 21,530 returns"
        ),
        transform=ax.transAxes,
        ha="center",
        va="bottom",
        fontsize=9.5,
    )

    colorbar = fig.colorbar(
        collection,
        ax=ax,
        orientation="vertical",
        fraction=0.032,
        pad=0.02,
    )

    colorbar.set_label(
        "Modeled TY2022 $1M+ returns",
        fontsize=9,
    )

    ax.text(
        0.0,
        -0.025,
        (
            "Labels show legislative district number and fractional-model estimate rounded "
            "for display only. Underlying estimates remain fractional."
        ),
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=8,
    )

    ax.text(
        0.0,
        -0.055,
        (
            "Model: Stage 7A winner M5 (IRS $200K+ AGI share + dividend-income share); "
            "validated against independent WA DOR TY2022 capital-gains taxpayer geography."
        ),
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=8,
    )

    ax.text(
        0.0,
        -0.085,
        (
            "These are modeled legislative-district estimates, not observed IRS district counts."
        ),
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=8,
        fontweight="bold",
    )

    plt.tight_layout()

    fig.savefig(
        MAP_OUTPUT,
        dpi=240,
        bbox_inches="tight",
    )

    plt.close(fig)

    print(
        f"Map output                      : "
        f"{MAP_OUTPUT.relative_to(ROOT)}"
    )
    print(
        f"Map SHA-256                     : "
        f"{sha256_file(MAP_OUTPUT)}"
    )


# =============================================================================
# OUTPUT
# =============================================================================

def write_audit(
    audit: pd.DataFrame,
) -> None:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    audit = audit.sort_values(
        "ld"
    ).reset_index(drop=True)

    audit.to_csv(
        AUDIT_OUTPUT,
        index=False,
    )

    print(
        f"Join audit                      : "
        f"{AUDIT_OUTPUT.relative_to(ROOT)}"
    )
    print(
        f"Audit SHA-256                   : "
        f"{sha256_file(AUDIT_OUTPUT)}"
    )


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:
    banner(
        "MILLIONAIRE GEOGRAPHY v0.2 - STAGE 8 ANALYTICAL MAP"
    )

    print("NO MODEL FITTING")
    print("NO INTEGERIZATION")
    print("NO DATABASE WRITES")
    print("NO HISTORICAL LD MILLIONAIRE INPUTS")
    print()

    validate_sources()

    model = read_model()

    records, district_field = read_geometry()

    audit = build_join_audit(
        model=model,
        records=records,
        district_field=district_field,
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    write_audit(
        audit=audit,
    )

    create_map(
        model=model,
        records=records,
        district_field=district_field,
    )

    banner("STAGE 8 COMPLETE")

    print(
        "The map is a visualization of the frozen Stage 7B "
        "49-LD fractional expected-count distribution."
    )
    print()
    print(
        "No statistical estimation, model selection, calibration, "
        "or integerization occurred during Stage 8."
    )


if __name__ == "__main__":
    main()