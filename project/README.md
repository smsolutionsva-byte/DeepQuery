# Satellite Image Intelligence System

This project provides a modular local Python pipeline for:

- Semantic image/text retrieval with OpenCLIP + FAISS
- BLIP caption-based explanation
- BIT-CD based change detection (with local repo integration)
- Reverse image search via PicImageSearch
- Timeline graph visualization for vegetation/urban trends

## Quick Start

1. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Optional setup bootstrap:

   ```bash
   python setup.py init_project
   ```

3. Run:

   ```bash
   python main.py
   ```

## Dataset Drop-in Folder

Place your dataset under either:

- `./dataset/` (preferred)
- `./INSERT_DATASET/` (legacy, still supported)

The loader scans recursively under the chosen root and picks image files with:
`.jpg`, `.jpeg`, `.png`, `.tif`, `.tiff`.

Paired change-detection folders are still supported:

- `paired_images/A/`
- `paired_images/B/`
