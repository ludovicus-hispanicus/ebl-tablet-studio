# eBL Tablet Studio

Unified desktop application for cuneiform tablet image processing. Successor to [tablet-image-renamer](https://github.com/ludovicus-hispanicus/tablet-image-renamer) and [ebl-photo-stitcher](https://github.com/ludovicus-hispanicus/ebl-photo-stitcher) — combines their workflows into a single Electron app with a bundled Python backend.

**Status:** Early setup. Initial import in progress. See [docs/merge-plan.md](docs/merge-plan.md) for the full migration plan.

## What it does (target)

- **Image renaming** — rename raw photos by tablet view code (obverse, reverse, top, bottom, left, right, etc.) with project-aware metadata.
- **Interactive segmentation** — SAM-based tablet extraction, with both automatic (center-point prompt) and manual (click-to-refine) modes.
- **Automated stitching** — multi-view compositing, ruler detection, scale-based digital ruler overlay, EXIF/XMP metadata embedding.
- **Zero-config install** — single installer per OS, no system Python required.

## Development

Not yet runnable. Work in progress — see [docs/merge-plan.md](docs/merge-plan.md).

## License

MIT. See [LICENSE](LICENSE).
