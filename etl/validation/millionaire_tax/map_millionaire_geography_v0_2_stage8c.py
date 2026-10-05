"""
Millionaire Geography v0.2 - Stage 8C FINAL MAP.

Final cartographic refinement only.

Creates:
1. Final statewide Washington legislative-district choropleth.
2. Enlarged Puget Sound inset.
3. Final model-to-geometry join audit.

IMPORTANT
---------
- Frozen Stage 7B model values are unchanged.
- No model fitting.
- No calibration.
- No integerization.
- No historical LD millionaire inputs.
- No database writes.
- Square-root normalization affects COLOR DISPLAY ONLY.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
import numpy as np
import pandas as pd
import shapefile

from matplotlib.collections import PatchCollection
from matplotlib.patches import Polygon, Rectangle


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

SHAPEFILE_PATH = SHAPEFILE_DIR / "tl_2020_53_sldl20.shp"

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
    / "millionaire_geography_v0_2_ty2022_map_final.png"
)

AUDIT_OUTPUT = (
    OUTPUT_DIR
    / "millionaire_geography_v0_2_ty2022_map_final_join_audit.csv"
)


# =============================================================================
# FROZEN HASHES / CONTROLS
# =============================================================================

EXPECTED_MODEL_SHA256 = (
    "6eb3fc8a02eef8dc73b9a752f6532664ec92cab98d3851c9a574ad004390047a"
)

EXPECTED_GEOMETRY_ZIP_SHA256 = (
    "7dd41cd8f15cc104ceab1c717ecc46692c9e5e31bbb3cbdfbec0bff54de0b030"
)

EXPECTED_LD_COUNT = 49
STATEWIDE_MILLIONAIRE_RETURNS = 21_530


# =============================================================================
# DISPLAY PARAMETERS
# =============================================================================

#
# Puget Sound inset.
#
# These coordinates affect display only.
#
INSET_XLIM = (-122.65, -121.85)
INSET_YLIM = (47.05, 48.20)


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


def shape_parts(shape):
    """
    Yield polygon parts from a pyshp shape.
    """
    points = np.asarray(shape.points, dtype=float)

    starts = list(shape.parts)
    starts.append(len(points))

    for start, end in zip(starts[:-1], starts[1:]):
        part = points[start:end]

        if len(part) >= 3:
            yield part


def approximate_label_point(shape):
    """
    Display-only label point based on feature bounding-box center.

    This has no analytical role.
    """
    min_x, min_y, max_x, max_y = shape.bbox

    return (
        (min_x + max_x) / 2.0,
        (min_y + max_y) / 2.0,
    )


def point_inside_inset(x: float, y: float) -> bool:
    return (
        INSET_XLIM[0] <= x <= INSET_XLIM[1]
        and INSET_YLIM[0] <= y <= INSET_YLIM[1]
    )


# =============================================================================
# SOURCE VALIDATION
# =============================================================================

def validate_sources() -> None:
    banner("STAGE 8C FROZEN SOURCE PROVENANCE")

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
    print(f"Stage 7B model SHA-256          : {model_hash}")
    print()
    print(f"Census geometry source ZIP      : {SHAPEFILE_ZIP.relative_to(ROOT)}")
    print(f"Census geometry ZIP SHA-256     : {geometry_hash}")
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
# READ MODEL
# =============================================================================

def read_model() -> pd.DataFrame:
    banner("READ FROZEN MILLIONAIRE GEOGRAPHY v0.2")

    df = pd.read_csv(
        MODEL_PATH,
        dtype={"ld": str},
    )

    df["ld"] = df["ld"].map(normalize_ld)

    required_columns = [
        "ld",
        "millionaire_share_v0_2",
        "estimated_millionaire_returns_v0_2",
    ]

    for column in required_columns:
        require(
            column in df.columns,
            f"Missing Stage 7B model column: {column}",
        )

    require(
        len(df) == EXPECTED_LD_COUNT,
        f"Expected 49 model rows; found {len(df)}.",
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
        "Stage 7B model does not reconcile to 21,530.",
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
# READ GEOMETRY
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

    require(
        len(records) == EXPECTED_LD_COUNT,
        (
            "Expected 49 Census SLDL geometry records; "
            f"found {len(records)}."
        ),
    )

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
            "Could not identify legislative-district field. "
            f"Fields present: {field_names}"
        ),
    )

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
            "Census geometry universe is not "
            "exactly LD001-LD049."
        ),
    )

    print(f"Geometry records                : {len(records):,}")
    print(f"District field                  : {district_field}")
    print("Geometry LD universe            : PASS")

    return records, district_field


# =============================================================================
# JOIN AUDIT
# =============================================================================

def build_join_audit(
    model: pd.DataFrame,
    records,
    district_field: str,
) -> pd.DataFrame:

    banner("AUDIT MODEL-TO-GEOMETRY JOIN")

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

        x, y = approximate_label_point(shape)

        rows.append(
            {
                "ld": ld,
                "geometry_found": True,
                "millionaire_share_v0_2":
                    model_lookup[ld][
                        "millionaire_share_v0_2"
                    ],
                "estimated_millionaire_returns_v0_2":
                    model_lookup[ld][
                        "estimated_millionaire_returns_v0_2"
                    ],
                "label_x": x,
                "label_y": y,
                "label_suppressed_on_statewide_panel":
                    point_inside_inset(x, y),
            }
        )

    audit = (
        pd.DataFrame(rows)
        .sort_values("ld")
        .reset_index(drop=True)
    )

    require(
        len(audit) == EXPECTED_LD_COUNT,
        "Final map join does not contain 49 LDs.",
    )

    require(
        audit["ld"].nunique() == EXPECTED_LD_COUNT,
        "Final map join contains duplicate LDs.",
    )

    require(
        audit["geometry_found"].all(),
        "One or more model LDs lack geometry.",
    )

    joined_total = float(
        audit[
            "estimated_millionaire_returns_v0_2"
        ].sum()
    )

    require(
        abs(
            joined_total
            - STATEWIDE_MILLIONAIRE_RETURNS
        ) <= 1e-8,
        "Final map join changed the statewide millionaire total.",
    )

    print(f"Joined LD rows                  : {len(audit):,}")
    print("Missing model rows              : 0")
    print("Missing geometry rows           : 0")
    print(f"Joined millionaire total        : {joined_total:,.12f}")
    print(
        "Statewide labels suppressed     : "
        f"{int(audit['label_suppressed_on_statewide_panel'].sum()):,}"
    )
    print()
    print("One-to-one map join             : PASS")

    return audit


# =============================================================================
# DRAWING HELPERS
# =============================================================================

def build_patch_collection(
    records,
    district_field,
    model_lookup,
    cmap,
    norm,
    edgecolor="white",
    linewidth=0.65,
):
    patches = []
    values = []

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

    collection = PatchCollection(
        patches,
        cmap=cmap,
        norm=norm,
        edgecolor=edgecolor,
        linewidth=linewidth,
    )

    collection.set_array(
        np.asarray(
            values,
            dtype=float,
        )
    )

    return collection


def get_state_bounds(records):
    xs = []
    ys = []

    for _, shape in records:
        for part in shape_parts(shape):
            xs.extend(part[:, 0])
            ys.extend(part[:, 1])

    return (
        min(xs),
        min(ys),
        max(xs),
        max(ys),
    )


# =============================================================================
# FINAL MAP
# =============================================================================

def create_map(
    model: pd.DataFrame,
    records,
    district_field: str,
) -> None:

    banner("RENDER STAGE 8C FINAL MAP")

    model_lookup = (
        model
        .set_index("ld")
        .to_dict(orient="index")
    )

    values = (
        model[
            "estimated_millionaire_returns_v0_2"
        ]
        .astype(float)
    )

    vmin = float(values.min())
    vmax = float(values.max())

    #
    # DISPLAY ONLY.
    #
    # Square-root normalization reveals differences among
    # lower-valued districts while preserving the underlying
    # values and district ordering.
    #
    norm = mpl.colors.PowerNorm(
        gamma=0.5,
        vmin=vmin,
        vmax=vmax,
    )

    cmap = plt.get_cmap("viridis")

    fig = plt.figure(
        figsize=(16, 10),
        facecolor="white",
    )

    # -------------------------------------------------------------------------
    # STATEWIDE PANEL
    # -------------------------------------------------------------------------

    ax = fig.add_axes(
        [0.025, 0.18, 0.70, 0.74]
    )

    main_collection = build_patch_collection(
        records=records,
        district_field=district_field,
        model_lookup=model_lookup,
        cmap=cmap,
        norm=norm,
        edgecolor="white",
        linewidth=0.70,
    )

    ax.add_collection(
        main_collection
    )

    min_x, min_y, max_x, max_y = get_state_bounds(
        records
    )

    x_pad = (max_x - min_x) * 0.015
    y_pad = (max_y - min_y) * 0.025

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

    #
    # Statewide labels.
    #
    # Labels whose display point falls inside the Puget Sound
    # detail box are deliberately omitted here because those
    # districts are labeled at larger scale in the inset.
    #
    for attrs, shape in records:
        ld = normalize_ld(
            attrs[district_field]
        )

        x, y = approximate_label_point(
            shape
        )

        if point_inside_inset(x, y):
            continue

        txt = ax.text(
            x,
            y,
            str(int(ld)),
            ha="center",
            va="center",
            fontsize=6.6,
            fontweight="bold",
        )

        txt.set_path_effects(
            [
                pe.withStroke(
                    linewidth=2.0,
                    foreground="white",
                )
            ]
        )

    #
    # Subtle locator rectangle.
    #
    inset_box = Rectangle(
        (
            INSET_XLIM[0],
            INSET_YLIM[0],
        ),
        INSET_XLIM[1] - INSET_XLIM[0],
        INSET_YLIM[1] - INSET_YLIM[0],
        fill=False,
        linewidth=1.0,
        linestyle="--",
        edgecolor="0.30",
        zorder=10,
    )

    ax.add_patch(
        inset_box
    )

    # -------------------------------------------------------------------------
    # PUGET SOUND INSET
    # -------------------------------------------------------------------------

    ax_inset = fig.add_axes(
        [0.745, 0.285, 0.235, 0.535]
    )

    inset_collection = build_patch_collection(
        records=records,
        district_field=district_field,
        model_lookup=model_lookup,
        cmap=cmap,
        norm=norm,
        edgecolor="white",
        linewidth=0.90,
    )

    ax_inset.add_collection(
        inset_collection
    )

    ax_inset.set_xlim(
        *INSET_XLIM
    )

    ax_inset.set_ylim(
        *INSET_YLIM
    )

    ax_inset.set_aspect(
        "equal",
        adjustable="box",
    )

    ax_inset.set_xticks([])
    ax_inset.set_yticks([])

    for spine in ax_inset.spines.values():
        spine.set_linewidth(1.1)

    ax_inset.set_title(
        "Puget Sound detail",
        fontsize=11.5,
        fontweight="bold",
        pad=8,
    )

    #
    # Inset labels: LD number + rounded display estimate.
    #
    for attrs, shape in records:
        ld = normalize_ld(
            attrs[district_field]
        )

        x, y = approximate_label_point(
            shape
        )

        if not point_inside_inset(x, y):
            continue

        value = float(
            model_lookup[ld][
                "estimated_millionaire_returns_v0_2"
            ]
        )

        label = (
            f"LD {int(ld)}\n"
            f"{value:,.0f}"
        )

        txt = ax_inset.text(
            x,
            y,
            label,
            ha="center",
            va="center",
            fontsize=6.5,
            fontweight="bold",
        )

        txt.set_path_effects(
            [
                pe.withStroke(
                    linewidth=2.2,
                    foreground="white",
                )
            ]
        )

    # -------------------------------------------------------------------------
    # TITLE
    # -------------------------------------------------------------------------

    fig.suptitle(
        "Washington Legislative Districts\n"
        r"Estimated TY2022 Returns with AGI $\geq$ \$1 Million",
        fontsize=20,
        fontweight="bold",
        y=0.970,
    )

    fig.text(
        0.5,
        0.895,
        (
            "Millionaire Geography v0.2 | "
            "Modeled estimates reconciled to IRS statewide "
            "control of 21,530 returns"
        ),
        ha="center",
        fontsize=10.5,
    )

    # -------------------------------------------------------------------------
    # COLORBAR
    # -------------------------------------------------------------------------

    cax = fig.add_axes(
        [0.755, 0.205, 0.215, 0.024]
    )

    scalar_mappable = mpl.cm.ScalarMappable(
        norm=norm,
        cmap=cmap,
    )

    scalar_mappable.set_array([])

    colorbar = fig.colorbar(
        scalar_mappable,
        cax=cax,
        orientation="horizontal",
    )

    colorbar.set_label(
        "Modeled TY2022 $1M+ returns",
        fontsize=9,
    )

    candidate_ticks = [
        50,
        100,
        250,
        500,
        1000,
        1500,
        2000,
        2500,
    ]

    ticks = [
        tick
        for tick in candidate_ticks
        if vmin <= tick <= vmax
    ]

    colorbar.set_ticks(
        ticks
    )

    colorbar.ax.set_xticklabels(
        [
            f"{tick:,}"
            for tick in ticks
        ]
    )

    # -------------------------------------------------------------------------
    # FOOTER
    # -------------------------------------------------------------------------

    fig.text(
        0.035,
        0.105,
        (
            "Statewide panel labels show legislative district number; "
            "districts within the Puget Sound detail area are labeled "
            "in the inset instead."
        ),
        ha="left",
        fontsize=8.5,
    )

    fig.text(
        0.035,
        0.080,
        (
            "Puget Sound inset labels show LD and modeled return estimate. "
            "Displayed counts are rounded for readability; underlying "
            "fractional estimates are unchanged."
        ),
        ha="left",
        fontsize=8.5,
    )

    fig.text(
        0.035,
        0.055,
        (
            "Color uses square-root display normalization to reveal variation "
            "across lower-valued districts; underlying estimates and district "
            "rankings are unchanged."
        ),
        ha="left",
        fontsize=8.5,
    )

    fig.text(
        0.035,
        0.030,
        (
            "Model: Stage 7A winner M5 (IRS $200K+ AGI share + "
            "dividend-income share), validated against independent WA DOR "
            "TY2022 capital-gains taxpayer geography."
        ),
        ha="left",
        fontsize=8.5,
    )

    fig.text(
        0.035,
        0.008,
        (
            "These are modeled legislative-district estimates, "
            "not observed IRS district counts."
        ),
        ha="left",
        fontsize=9,
        fontweight="bold",
    )

    # -------------------------------------------------------------------------
    # WRITE
    # -------------------------------------------------------------------------

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    fig.savefig(
        MAP_OUTPUT,
        dpi=300,
        bbox_inches="tight",
        facecolor="white",
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

    print("Color normalization             : PowerNorm gamma=0.5")
    print("Color transformation role       : DISPLAY ONLY")


# =============================================================================
# WRITE AUDIT
# =============================================================================

def write_audit(
    audit: pd.DataFrame,
) -> None:

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

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
        "MILLIONAIRE GEOGRAPHY v0.2 - STAGE 8C FINAL MAP"
    )

    print("FINAL CARTOGRAPHIC REFINEMENT ONLY")
    print("NO MODEL FITTING")
    print("NO CALIBRATION")
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

    write_audit(
        audit=audit,
    )

    create_map(
        model=model,
        records=records,
        district_field=district_field,
    )

    banner("STAGE 8C COMPLETE")

    print(
        "Stage 8C is the final cartographic rendering of the "
        "frozen Stage 7B millionaire-count geography."
    )

    print()

    print(
        "No model values, coefficients, calibration, district shares, "
        "or estimated counts were modified."
    )


if __name__ == "__main__":
    main()