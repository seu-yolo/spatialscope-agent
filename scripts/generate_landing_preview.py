from __future__ import annotations

from spatialscope.ui.landing_preview import generate_landing_preview


if __name__ == "__main__":
    paths = generate_landing_preview("data/demo_embryo.h5ad")
    print(f"wrote {paths['png']}")
    if paths["webp"].exists():
        print(f"wrote {paths['webp']}")
