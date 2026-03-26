# Map Georeferencing Skill

Extract geospatial vector data from color-coded map images. Converts map images (PDF, PNG, TIFF, GeoTIFF) into analysis-ready GeoJSON and shapefiles.

## What It Does

This skill guides Claude through an 8-step pipeline:

1. **Image acquisition** — Render PDFs at high DPI, load raster images, or read GeoTIFFs
2. **Line removal** — Detect and remove boundary lines using HSV thresholds + local contrast
3. **ROI masking** — Isolate the map area from margins, legends, and title blocks
4. **Color segmentation** — Classify colored zones via HSV thresholding or K-means clustering
5. **Polygonization** — Convert raster labels to vector polygons (rasterio + shapely)
6. **Georeferencing** — Map pixel coordinates to geographic coordinates via GCPs or known projections
7. **Validation** — RMSE analysis, area checks, visual overlay comparison
8. **Export** — GeoJSON (EPSG:4326) + shapefiles in user-specified CRS

## Use Cases

- Utility service territory maps
- Wetlands and land use maps
- Zoning district maps
- Geological and soil survey maps
- Vegetation classification maps
- Any map where colored regions represent categorical zones

## Georeferencing Options

The skill supports four georeferencing paths depending on what's available:

| Input | Method |
|-------|--------|
| GeoTIFF with embedded CRS | Skip — transform is embedded |
| Map with coordinate grid/ticks | Affine transform from 3+ grid points |
| PDF with place-name text labels | Match text to gazetteer, fit 2nd-order polynomial |
| Nothing — just the image | User provides manual GCP pairs |

## Dependencies

The skill generates code that uses these Python libraries:

- `numpy`, `scipy` — numerical operations, distance transforms
- `opencv-python` (cv2) — image processing, HSV conversion, morphology
- `geopandas` — vector data handling, CRS management
- `shapely` — geometry operations
- `rasterio` — raster-to-vector conversion
- `matplotlib` — static preview maps
- `plotly` (optional) — interactive preview maps
- `PyMuPDF` (fitz, optional) — PDF rendering and text extraction
- `scikit-learn` (optional) — K-means color clustering

## Files

| File | Purpose |
|------|---------|
| `skill.md` | Main workflow with 3 decision gates, quality checklist, and pitfalls |
| `georeferencing-methods.md` | Code templates for affine, polynomial, and GCP-based transforms |
| `color-segmentation.md` | Code templates for color classification, line removal, and cleanup |

## Installation

```bash
cp -r map-georeferencing/ /path/to/your/project/.claude/skills/
```
