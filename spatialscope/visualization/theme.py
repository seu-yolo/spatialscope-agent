from __future__ import annotations

from pathlib import Path
from typing import Any

CLUSTER_PALETTE = [
    "#0f766e",
    "#6f4e8f",
    "#c75f4a",
    "#4c78a8",
    "#b7791f",
    "#5f6f52",
    "#8b5e34",
    "#5b6472",
    "#9a4d8e",
    "#2f855a",
    "#7b8794",
    "#b64342",
]

EXPRESSION_CMAP = "spatialscope_expression"
SIGNAL_TEAL = "#0f766e"
SIGNAL_PLUM = "#6f4e8f"
SIGNAL_CORAL = "#c75f4a"
NEUTRAL_INK = "#172026"
NEUTRAL_MUTED = "#66737f"
NEUTRAL_LINE = "#d8e0e7"
NEUTRAL_PALE = "#f5f7f8"


def apply_matplotlib_theme() -> None:
    import matplotlib as mpl
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap

    if EXPRESSION_CMAP not in plt.colormaps():
        cmap = LinearSegmentedColormap.from_list(
            EXPRESSION_CMAP,
            ["#f7faf9", "#dcefed", "#9fcfca", "#3d9a91", "#075a54"],
        )
        mpl.colormaps.register(cmap, name=EXPRESSION_CMAP, force=True)

    plt.rcParams.update(
        {
            "figure.dpi": 120,
            "savefig.dpi": 300,
            "savefig.facecolor": "white",
            "savefig.edgecolor": "white",
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
            "font.size": 9.2,
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": False,
            "axes.linewidth": 0.8,
            "axes.titleweight": "bold",
            "axes.titlesize": 11,
            "axes.labelsize": 9.2,
            "axes.labelcolor": NEUTRAL_INK,
            "xtick.color": NEUTRAL_MUTED,
            "ytick.color": NEUTRAL_MUTED,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "legend.frameon": False,
            "legend.fontsize": 8,
            "legend.title_fontsize": 8,
        }
    )


def save_figure_bundle(fig: Any, path: str | Path, *, dpi: int = 320) -> dict[str, str]:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, bbox_inches="tight", dpi=dpi, facecolor="white")
    svg_path = output_path.with_suffix(".svg")
    fig.savefig(svg_path, bbox_inches="tight", facecolor="white")
    return {"path": str(output_path), "svg_path": str(svg_path)}


def polish_axis(ax: Any, *, title: str | None = None, subtitle: str | None = None) -> None:
    if title:
        ax.set_title(title, loc="left", pad=18 if subtitle else 8)
    if subtitle:
        ax.text(
            0,
            1.02,
            subtitle,
            transform=ax.transAxes,
            ha="left",
            va="bottom",
            fontsize=8,
            color=NEUTRAL_MUTED,
        )
    for spine in ["left", "bottom"]:
        ax.spines[spine].set_color(NEUTRAL_LINE)
    ax.tick_params(length=3, width=0.7)


def add_panel_label(ax: Any, label: str) -> None:
    ax.text(
        -0.04,
        1.06,
        label,
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=9,
        fontweight="bold",
        color=NEUTRAL_INK,
    )


def numeric_sort_key(value: Any) -> tuple[int, Any]:
    text = str(value)
    try:
        return (0, int(text))
    except ValueError:
        return (1, text)
