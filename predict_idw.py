#!/usr/bin/env python3
"""Run the IDW local-shift method for one village bundle."""

from __future__ import annotations

import sys
from pathlib import Path

from bhume import load, score, write_predictions
from bhume.solution import idw_local_shift

DEFAULT_VILLAGE = 'data/34855_vadnerbhairav_chandavad_nashik'


def main(village_dir: str) -> None:
    village = load(village_dir)
    n_truth = 0 if village.example_truths is None else len(village.example_truths)
    print(f'Loaded {village.slug}')
    print(f'  {len(village.plots)} plots - {n_truth} example truths - '
          f'boundaries={"yes" if village.boundaries_path else "none"}')

    preds = idw_local_shift(village)
    out = write_predictions(Path(village_dir) / 'predictions.geojson', preds)
    print(f'  wrote {len(preds)} IDW predictions -> {out}')

    if village.example_truths is not None:
        print()
        print(score(preds, village))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_VILLAGE)
