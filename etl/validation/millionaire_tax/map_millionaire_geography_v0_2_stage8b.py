"""
Millionaire Geography v0.2 - Stage 8B publication map.

Cartographic refinement only.

Creates:
1. Statewide Washington legislative-district choropleth.
2. Enlarged Puget Sound inset.
3. Join-audit CSV.

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
    / "millionaire_geography_v0_2_ty2022_map_stage8b.png"
)

AUDIT_OUTPUT = (
    OUTPUT_DIR
    / "millionaire_geography_v0_2_ty2022_map_stage8b_join_audit.csv"
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
    points = np.asarray(shape.points, dtype=float)

    starts = list(shape.parts)
    starts.append(len(points))

    for start, end in zip(starts[:-1], starts[1:]):
        part = points[start:end]

        if len(part) >= 3:
            yield part


def approximate_label_point(shape):
    """
    Display-only label location.

    Uses the center of the feature bounding box rather than the mean
    of all vertices. No analytical role.
    """
    min_x, min_y, max_x, max_y = shape.bbox

    return (
        (min_x + max_x) / 2.0,
        (min_y + max_y) / 2.0,
    )


# =============================================================================
# SOURCE VALIDATION
# =============================================================================

def validate_sources() -> None:
    banner("STAGE 8B FROZEN SOURCE PROVENANCE")

    require(MODEL_PATH.exists(), f"Missing model: {MODEL_PATH}")
    require(SHAPEFILE_PATH.exists(), f"Missing shapefile: {SHAPEFILE_PATH}")
    require(SHAPEFILE_ZIP.exists(), f"Missing source ZIP: {SHAPEFILE_ZIP}")

    model_hash = sha256_file(MODEL_PATH)
    geometry_hash = sha256_file(SHAPEFILE_ZIP)

    print(f"Stage 7B model SHA-256          : {model_hash}")
    print(f"Census geometry ZIP SHA-256     : {geometry_hash}")

    require(
        model_hash.lower() == EXPECTED_MODEL_SHA256.lower(),
        "Stage 7B model hash mismatch.",
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

    df = pd.read_csv(MODEL_PATH, dtype={"ld": str})
    df["ld"] = df["ld"].map(normalize_ld)

    required = [
        "ld",
        "millionaire_share_v0_2",
        "estimated_millionaire_returns_v0_2",
    ]

    for col in required:
        require(col in df.columns, f"Missing model column: {col}")

    require(len(df) == 49, f"Expected 49 rows; found {len(df)}.")
    require(df["ld"].nunique() == 49, "LD identifiers are not unique.")

    expected = {f"{i:03d}" for i in range(1, 50)}

    require(
        set(df["ld"]) == expected,
        "Model LD universe is not exactly 001-049.",
    )

    total = float(df["estimated_millionaire_returns_v0_2"].sum())
    share = float(df["millionaire_share_v0_2"].sum())

    require(
        abs(total - STATEWIDE_MILLIONAIRE_RETURNS) <= 1e-8,
        "Model does not reconcile to 21,530.",
    )

    require(
        abs(share - 1.0) <= 1e-12,
        "Model shares do not sum to 1.",
    )

    print(f"LD rows                         : {len(df):,}")
    print(f"Share total                     : {share:.15f}")
    print(f"Estimated return total          : {total:,.12f}")
    print("Frozen model validation         : PASS")

    return df


# =============================================================================
# READ GEOMETRY
# =============================================================================

def read_geometry():
    banner("READ CENSUS SLDL GEOMETRY")

    reader = shapefile.Reader(str(SHAPEFILE_PATH))

    field_names = [
        field[0]
        for field in reader.fields[1:]
    ]

    records = []

    for sr in reader.iterShapeRecords():
        attrs = dict(zip(field_names, sr.record))
        records.append((attrs, sr.shape))

    require(
        len(records) == EXPECTED_LD_COUNT,
        f"Expected 49 geometry records; found {len(records)}.",
    )

    district_field = None

    for candidate in ["SLDLST20", "SLDLST", "SLDL"]:
        if candidate in field_names:
            district_field = candidate
            break

    require(
        district_field is not None,
        f"Could not identify district field. Fields: {field_names}",
    )

    expected = {f"{i:03d}" for i in range(1, 50)}

    geometry_lds = {
        normalize_ld(attrs[district_field])
        for attrs, _ in records
    }

    require(
        geometry_lds == expected,
        "Geometry universe is not exactly 001-049.",
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

    lookup = model.set_index("ld").to_dict(orient="index")

    rows = []

    for attrs, shape in records:
        ld = normalize_ld(attrs[district_field])

        require(ld in lookup, f"Geometry LD{ld} has no model row.")

        x, y = approximate_label_point(shape)

        rows.append(
            {
                "ld": ld,
                "geometry_found": True,
                "millionaire_share_v0_2":
                    lookup[ld]["millionaire_share_v0_2"],
                "estimated_millionaire_returns_v0_2":
                    lookup[ld]["estimated_millionaire_returns_v0_2"],
                "label_x": x,
                "label_y": y,
            }
        )

    audit = pd.DataFrame(rows).sort_values("ld").reset_index(drop=True)

    require(len(audit) == 49, "Join does not contain 49 rows.")
    require(audit["ld"].nunique() == 49, "Duplicate joined LDs.")

    joined_total = float(
        audit["estimated_millionaire_returns_v0_2"].sum()
    )

    require(
        abs(joined_total - STATEWIDE_MILLIONAIRE_RETURNS) <= 1e-8,
        "Join changed statewide total.",
    )

    print(f"Joined LD rows                  : {len(audit):,}")
    print("Missing model rows              : 0")
    print("Missing geometry rows           : 0")
    print(f"Joined millionaire total        : {joined_total:,.12f}")
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
        ld = normalize_ld(attrs[district_field])

        value = float(
            model_lookup[ld]["estimated_millionaire_returns_v0_2"]
        )

        for part in shape_parts(shape):
            patches.append(Polygon(part, closed=True))
            values.append(value)

    collection = PatchCollection(
        patches,
        cmap=cmap,
        norm=norm,
        edgecolor=edgecolor,
        linewidth=linewidth,
    )

    collection.set_array(np.asarray(values, dtype=float))

    return collection


def get_state_bounds(records):
    xs = []
    ys = []

    for _, shape in records:
        for part in shape_parts(shape):
            xs.extend(part[:, 0])
            ys.extend(part[:, 1])

    return min(xs), min(ys), max(xs), max(ys)


# =============================================================================
# MAP
# =============================================================================

def create_map(
    model: pd.DataFrame,
    records,
    district_field: str,
) -> None:

    banner("RENDER STAGE 8B PUBLICATION MAP")

    lookup = model.set_index("ld").to_dict(orient="index")

    values = model["estimated_millionaire_returns_v0_2"].astype(float)

    vmin = float(values.min())
    vmax = float(values.max())

    #
    # DISPLAY ONLY:
    #
    # PowerNorm gamma=0.5 is a square-root color transformation.
    # It changes no underlying data and no district ordering.
    #
    norm = mpl.colors.PowerNorm(
        gamma=0.5,
        vmin=vmin,
        vmax=vmax,
    )

    cmap = plt.get_cmap("viridis")

    fig = plt.figure(
        figsize=(16, 10),
    )

    #
    # Main statewide panel.
    #
    ax = fig.add_axes(
        [0.035, 0.17, 0.69, 0.70]
    )

    main_collection = build_patch_collection(
        records,
        district_field,
        lookup,
        cmap,
        norm,
        edgecolor="white",
        linewidth=0.7,
    )

    ax.add_collection(main_collection)

    min_x, min_y, max_x, max_y = get_state_bounds(records)

    xpad = (max_x - min_x) * 0.015
    ypad = (max_y - min_y) * 0.025

    ax.set_xlim(min_x - xpad, max_x + xpad)
    ax.set_ylim(min_y - ypad, max_y + ypad)
    ax.set_aspect("equal")
    ax.axis("off")

    #
    # Statewide labels: district number ONLY.
    #
    for attrs, shape in records:
        ld = normalize_ld(attrs[district_field])
        x, y = approximate_label_point(shape)

        txt = ax.text(
            x,
            y,
            str(int(ld)),
            ha="center",
            va="center",
            fontsize=6.4,
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
    # Puget Sound inset bounds.
    #
    # These are display coordinates only, chosen to encompass the
    # Seattle/Bellevue/Everett/Tacoma concentration.
    #
    inset_xlim = (-122.65, -121.85)
    inset_ylim = (47.05, 48.20)

    #
    # Show inset extent on statewide map.
    #
    inset_box = Rectangle(
        (inset_xlim[0], inset_ylim[0]),
        inset_xlim[1] - inset_xlim[0],
        inset_ylim[1] - inset_ylim[0],
        fill=False,
        linewidth=1.4,
        linestyle="--",
        edgecolor="black",
        zorder=10,
    )

    ax.add_patch(inset_box)

    #
    # Puget Sound inset.
    #
    ax_inset = fig.add_axes(
        [0.735, 0.28, 0.245, 0.50]
    )

    inset_collection = build_patch_collection(
        records,
        district_field,
        lookup,
        cmap,
        norm,
        edgecolor="white",
        linewidth=0.9,
    )

    ax_inset.add_collection(inset_collection)

    ax_inset.set_xlim(*inset_xlim)
    ax_inset.set_ylim(*inset_ylim)
    ax_inset.set_aspect("equal")
    ax_inset.set_xticks([])
    ax_inset.set_yticks([])

    for spine in ax_inset.spines.values():
        spine.set_linewidth(1.2)

    ax_inset.set_title(
        "Puget Sound detail",
        fontsize=11,
        fontweight="bold",
        pad=8,
    )

    #
    # Inset labels.
    #
    # Only label districts whose display point falls within the inset.
    #
    for attrs, shape in records:
        ld = normalize_ld(attrs[district_field])

        x, y = approximate_label_point(shape)

        if (
            inset_xlim[0] <= x <= inset_xlim[1]
            and inset_ylim[0] <= y <= inset_ylim[1]
        ):
            value = float(
                lookup[ld]["estimated_millionaire_returns_v0_2"]
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

    #
    # Title.
    #
    fig.suptitle(
        "Washington Legislative Districts\n"
        "Estimated TY2022 Returns with AGI \u2265 $1 Million",
        fontsize=20,
        fontweight="bold",
        y=0.965,
    )

    fig.text(
        0.5,
        0.895,
        (
            "Millionaire Geography v0.2 | "
            "Modeled estimates reconciled to IRS statewide control "
            "of 21,530 returns"
        ),
        ha="center",
        fontsize=10.5,
    )

    #
    # Colorbar.
    #
    cax = fig.add_axes(
        [0.745, 0.16, 0.225, 0.025]
    )

    sm = mpl.cm.ScalarMappable(
        norm=norm,
        cmap=cmap,
    )

    sm.set_array([])

    colorbar = fig.colorbar(
        sm,
        cax=cax,
        orientation="horizontal",
    )

    colorbar.set_label(
        "Modeled TY2022 $1M+ returns",
        fontsize=9,
    )

    #
    # Use interpretable raw-data ticks even though their display
    # spacing follows the square-root normalization.
    #
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
        t
        for t in candidate_ticks
        if vmin <= t <= vmax
    ]

    colorbar.set_ticks(ticks)

    colorbar.ax.set_xticklabels(
        [f"{t:,}" for t in ticks]
    )

    #
    # Footer.
    #
    fig.text(
        0.04,
        0.105,
        (
            "Statewide panel labels show legislative district number. "
            "Puget Sound inset labels show LD and modeled return estimate."
        ),
        ha="left",
        fontsize=8.5,
    )

    fig.text(
        0.04,
        0.080,
        (
            "Color uses a square-root display normalization to reveal variation "
            "across lower-valued districts; underlying estimates and district "
            "rankings are unchanged."
        ),
        ha="left",
        fontsize=8.5,
    )

    fig.text(
        0.04,
        0.055,
        (
            "Model: Stage 7A winner M5 (IRS $200K+ AGI share + "
            "dividend-income share), validated against independent WA DOR "
            "TY2022 capital-gains taxpayer geography."
        ),
        ha="left",
        fontsize=8.5,
    )

    fig.text(
        0.04,
        0.030,
        (
            "These are modeled legislative-district estimates, "
            "not observed IRS district counts."
        ),
        ha="left",
        fontsize=9,
        fontweight="bold",
    )

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

    print(f"Map output                      : {MAP_OUTPUT.relative_to(ROOT)}")
    print(f"Map SHA-256                     : {sha256_file(MAP_OUTPUT)}")
    print("Color normalization             : PowerNorm gamma=0.5")
    print("Color transformation role       : DISPLAY ONLY")


# =============================================================================
# OUTPUT
# =============================================================================

def write_audit(audit: pd.DataFrame) -> None:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    audit.to_csv(
        AUDIT_OUTPUT,
        index=False,
    )

    print(f"Join audit                      : {AUDIT_OUTPUT.relative_to(ROOT)}")
    print(f"Audit SHA-256                   : {sha256_file(AUDIT_OUTPUT)}")


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:
    banner(
        "MILLIONAIRE GEOGRAPHY v0.2 - STAGE 8B PUBLICATION MAP"
    )

    print("CARTOGRAPHIC REFINEMENT ONLY")
    print("NO MODEL FITTING")
    print("NO CALIBRATION")
    print("NO INTEGERIZATION")
    print("NO DATABASE WRITES")
    print("NO HISTORICAL LD MILLIONAIRE INPUTS")

    validate_sources()

    model = read_model()

    records, district_field = read_geometry()

    audit = build_join_audit(
        model=model,
        records=records,
        district_field=district_field,
    )

    write_audit(audit)

    create_map(
        model=model,
        records=records,
        district_field=district_field,
    )

    banner("STAGE 8B COMPLETE")

    print(
        "Stage 8B changed cartographic presentation only. "
        "The frozen Stage 7B model values were not modified."
    )


if __name__ == "__main__":
    main()