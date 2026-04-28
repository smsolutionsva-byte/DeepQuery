INSERT_DATASET placeholder

Copy your local satellite datasets into this folder without changing code.

Supported structure:

INSERT_DATASET/
  images/                # single-image corpus for CLIP + FAISS semantic search
  paired_images/
    A/                   # time A images for change detection pairs
    B/                   # time B images for change detection pairs
  temperature.csv        # optional CSV with date + temperature columns for correlation graphs

Notes:
- The loader recursively scans the entire dataset root (including nested subfolders).
- Supported extensions: .jpg, .jpeg, .png, .tif, .tiff
- If no supported images are found, the app now raises a dataset error with diagnostics.
