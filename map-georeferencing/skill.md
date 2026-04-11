---
name: map-georeferencing
description: >
  Use for extracting geospatial vector data from color-coded map images (PDF, PNG, TIFF, GeoTIFF).
  Covers the full pipeline: image preprocessing, boundary/line removal, color segmentation into
  labeled zones, polygonization, georeferencing via GCPs or known projections, and export to
  GeoJSON/shapefile. Applies to utility maps, zoning maps, land use maps, wetlands maps,
  geological maps, vegetation maps, or any map where colored regions represent categorical zones.
  Trigger when user has a map image they want to convert to vector geospatial data.
---

# Map Georeferencing

Extract vector geospatial data from color-coded map images. This skill handles the full pipeline: image acquisition, preprocessing, color segmentation, polygonization, georeferencing, and export.

## When to Use

- User has a map image (PDF, PNG, TIFF) with colored zones they want as vector data
- User has a GeoTIFF and wants to extract colored regions as polygons
- User wants to digitize a scanned map into GIS-ready shapefiles or GeoJSON
- User mentions georeferencing, ground control points (GCPs), or map-to-coordinate transforms

## When NOT to Use

- User has vector data already (shapefiles, GeoJSON) and wants to reproject or transform it — just use geopandas directly
- User wants to geocode addresses — use the geocoding tools in ds-augmenter
- User wants satellite/aerial image classification — this skill is for thematic/categorical color-coded maps

## Workflow Overview

The pipeline has 8 steps organized around 3 decision gates where you must consult the user.

```
Step 0: Intake & Triage .............. DECISION GATE 1
Step 1: Image Acquisition
Step 2: Preprocessing / Line Removal
Step 3: Region-of-Interest Mask
Step 4: Color Segmentation .......... DECISION GATE 2
Step 5: Polygonize
Step 6: Georeference ................ DECISION GATE 3
Step 7: Apply Transform & Validate
Step 8: Export
```

### Debug output

Build the pipeline script with a `--debug` flag that saves intermediate images at each step: raw render, lines removed, ROI mask overlay, classified zones (color-coded), and GCP positions plotted on the image. When something goes wrong (and it will), these intermediates are the fastest way to diagnose whether the issue is in line removal, ROI masking, color classification, or georeferencing.

---

## Step 0: Intake & Triage (DECISION GATE 1)

Before writing any code, ask the user these questions. Their answers determine which pipeline path to follow.

**Questions to ask:**

1. **Input format?** PDF, PNG, TIFF, or GeoTIFF?
2. **What do the colored zones represent?** Utility service areas, wetlands, land use, zoning districts, soil types, vegetation, geology, etc.
3. **Can you name the colors and what each represents?** Or should we auto-detect color clusters and have you label them?
4. **Is the map already georeferenced?** (GeoTIFF with embedded CRS → skip to Step 4)
5. **Does the map have text labels?** Town names, place names, feature labels that could serve as GCPs?
6. **Does the map have point markers** (triangles, dots, icons) at labeled locations? If yes, use marker centroids — not text centroids — as GCP pixel positions. Text labels are offset for readability and introduce systematic error.
7. **Does the map show coordinate ticks, grid lines, or state a projection?** If yes, we can use a simpler affine transform.
8. **Do you have a reference shapefile/GeoJSON for the same area?** (e.g., Census boundaries, NHD wetlands, USGS geology) This helps both with GCP creation and validation.
9. **What geographic area does the map cover?** (state, county, watershed, etc.)
10. **What output CRS and format do you need?** Default: GeoJSON in EPSG:4326 + shapefile in a local projection.

**Routing table — choose the georeferencing path based on answers:**

| Scenario | Georef Path | Min GCPs |
|----------|-------------|----------|
| GeoTIFF with embedded CRS | Skip georef — CRS is embedded | 0 |
| Map has coordinate ticks/grid/stated projection | **6A**: Affine from grid coords | 3+ |
| PDF with text labels matchable to known places | **6B**: GCP-from-text pipeline | 10+ recommended |
| User has a reference shapefile for the area | **6D**: Align features to reference | 6+ |
| None of the above | **6C**: User provides manual GCPs | 3+ (affine), 6+ (polynomial) |

---

## Step 1: Image Acquisition

Render the map at high DPI and extract text/marker positions. See @georeferencing-methods.md for full code templates.

- **PDF**: Render at 600 DPI via PyMuPDF. Extract text spans with `page.get_text("dict")` for GCP matching. If text overlays colored zones, use PyMuPDF redactions with `fill=False` (never `fill=True` — it paints white rectangles over the map).
- **PNG / TIFF**: Load with OpenCV (`cv2.imread`).
- **GeoTIFF**: Load with rasterio. If it has an embedded CRS, skip to Step 4 — georeferencing is already done.

---

## Step 2: Preprocessing / Line Removal (Conditional)

**Ask the user:** Does the map have boundary lines between zones that need removal? Show them a crop of the map and ask.

If **no visible boundary lines** → skip to Step 3.

If **boundary lines present**, use the three-detector approach. See @color-segmentation.md for full code templates.

**Three detectors (combine with OR):**

1. **Absolute HSV threshold** — catches black and grey lines
2. **Local contrast** — catches faint lines darker than their neighborhood
3. **Text remnant cleanup** — catches residual text fragments in known text span bounding boxes

**Color propagation** — replace removed pixels with nearest non-masked color using distance transform. This splits zone borders at the centerline — each side gets the color from its respective zone.

**Two-pass strategy** — Pass 1 removes major lines; Pass 2 catches anti-aliased residuals near Pass 1 detections.

Key parameters to tune with the user:
- `dark_threshold`: V channel cutoff for "black" lines (default: 80)
- `grey_threshold`: V channel cutoff for "grey" lines (default: 140)
- `contrast_radius`: neighborhood radius for local contrast (default: 8)
- `contrast_threshold`: minimum V difference to flag (default: 30)

---

## Step 3: Region-of-Interest Mask

Build a binary mask of the mappable area (exclude margins, legends, title blocks, scale bars).

**Approach A — Colored region detection** (best for maps with colored fills):
```python
hsv = cv2.cvtColor(img_clean, cv2.COLOR_BGR2HSV)
colored = hsv[:, :, 1] > saturation_floor  # e.g., 25

# Largest connected component = the map area
from scipy.ndimage import label as scipy_label
labeled, n = scipy_label(colored.astype(np.uint8))
sizes = {i: (labeled == i).sum() for i in range(1, n + 1)}
largest = max(sizes, key=sizes.get)
map_mask = (labeled == largest)

# Convex hull to fill gaps
from scipy.ndimage import binary_fill_holes
map_mask = binary_fill_holes(map_mask)

# Morphological close to bridge thin gaps
kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
map_mask = cv2.morphologyEx(map_mask.astype(np.uint8), cv2.MORPH_CLOSE, kernel).astype(bool)
```

**Warning: unsaturated zones will be missed.** White, grey, or very light zones (e.g., "Other", "Unclassified") have low saturation and won't be captured by the colored-region approach. These zones are typically at the map edges, outside the main study area. If they matter, expand the ROI using the convex hull of the detected colored region, or accept they won't be included.

**Approach B — User-defined crop:**
If the user can specify the map boundaries, just crop to a bounding box.

---

## Step 4: Color Segmentation (DECISION GATE 2)

This is where zones are classified. **Before choosing an approach, run a color diagnostic** on the ROI pixels to understand what you're working with.

### Diagnostic: Check for discrete colors (vector PDF fast path)

Vector PDFs rendered from GIS software often use flat fills with exact RGB values. Check:

```python
hsv = cv2.cvtColor(img_clean, cv2.COLOR_BGR2HSV)
pixels = hsv[roi_mask]
# Check if S and V are nearly constant
unique_s = np.unique(pixels[:, 1])
unique_v = np.unique(pixels[:, 2])
# Check how many distinct hue values dominate
dominant = pixels[(pixels[:, 1] == np.median(pixels[:, 1])) & 
                  (pixels[:, 2] == np.median(pixels[:, 2]))]
unique_h, counts = np.unique(dominant[:, 0], return_counts=True)
```

If there are fewer than ~20 dominant (H, S, V) combinations, the map uses flat fills. **Use exact hue matching** with tight windows (±2) instead of fuzzy HSV ranges. This eliminates all overlap risk and makes classification trivially accurate. This is common for GIS-exported PDFs and is worth checking before investing time in elaborate color profiling.

If the colors are continuous or varied, proceed with Approach A or B below.

### Approach A: HSV Thresholding (distinct but continuous colors)

Show the user an HSV scatter plot (H vs S) from the `explore_colors()` diagnostic. See @color-segmentation.md for the full classification framework.

**Important HSV notes:**
- OpenCV HSV: H is 0-180 (not 0-360), S and V are 0-255
- Red wraps around: H < 10 OR H > 170
- Classify more-specific colors first (e.g., light blue before dark blue — separate by saturation)

### Approach B: K-Means Clustering (colors not pre-specified)

Use when colors are unknown or there are many similar shades. See @color-segmentation.md for code. Show cluster centers to the user and ask them to label each cluster.

### Post-classification cleanup

Morphological close (bridge line-removal gaps), remove specks < threshold, then iterative nearest-neighbor dilation to assign unclassified interior pixels to their nearest zone. See @color-segmentation.md for cleanup code.

**Validation:** Show the classified overlay to the user. Report pixel counts per zone. Check mutual exclusivity.

---

## Step 5: Polygonize

Convert the raster label array to vector polygons in **pixel coordinates** using `rasterio.features.shapes()` with an identity transform. Simplify with `preserve_topology=True`, repair invalid geometries with `buffer(0)`. See @color-segmentation.md for the full code template.

Output: GeoDataFrame with columns `geometry`, `zone`, `label_id`, `area_px`. No CRS yet — that comes from the georeferencing step. Save as intermediate GeoJSON.

---

## Step 6: Georeference (DECISION GATE 3)

Choose the transform path based on Step 0 triage. See @georeferencing-methods.md for full code templates.

**But first — read the GCP data quality foundation below. It applies to every path.**

### GCP Data Quality Foundation

> **GCP coordinate accuracy is the foundation of georeferencing. Everything else — transform order, number of GCPs, pixel detection, outlier removal — is secondary. No amount of algorithmic sophistication can compensate for inaccurate coordinates.**

This is not a best practice — it is a hard prerequisite. In a real-world exercise georeferencing a county-level school zone map with 17 GCPs:
- Memory-estimated coordinates (1-3 km off) → RMSE stuck at **648m** regardless of transform tuning
- Web-verified coordinates from a single source → RMSE dropped to **97m**
- Cross-verified against Google Maps URLs → RMSE dropped to **44m** and known geographic boundaries finally aligned

A 170m error in just 2 of 17 GCPs produced a visible systematic boundary shift in the output. The transform math was correct the entire time — only the coordinates were wrong.

**Requirements for every GCP coordinate (all paths):**

1. **Never estimate or guess coordinates.** Not "approximately," not "from memory," not from an LLM's training data. Every coordinate must come from a verifiable source.

2. **Verify against an authoritative source.** In priority order:
   - Google Maps URL coordinates (embedded in the URL as `@lat,lon`)
   - Official facility databases (school districts, government GIS portals, USGS)
   - OpenStreetMap (search by name, inspect coordinates)
   - Geocoding APIs (Nominatim, Google Geocoding) using the feature's street address

3. **Cross-reference GCPs near critical boundaries.** If the map has a well-known geographic boundary (state border, coastline, river), the 2-3 GCPs nearest that boundary dominate its alignment. Verify those against a second source. A single-source coordinate can be 100-200m off — invisible in RMSE but visible as boundary misalignment.

4. **Check spatial distribution.** GCPs clustered in one region leave other regions poorly constrained. Ensure coverage across all edges of the map, especially near boundaries the user will visually compare against a basemap.

5. **Prefer the feature's physical structure over its name.** A school's coordinates should be the building, not the town center or attendance zone centroid. Search by street address, not just the name.

---

### Path 6A: Known Projection (Affine Transform)

Use when the map has coordinate ticks, grid lines, or a stated projection.

- User picks 3+ pixel positions that correspond to known coordinates (grid intersections, labeled tick marks)
- Fit affine transform (6 parameters): handles translation, rotation, scale, skew
- RMSE should be near-zero for clean grid coordinates

### Path 6B: Text-Label GCPs

Use when the map is a PDF with readable place names that can be matched to geographic features.

1. Extract text spans from PDF (Step 1 output)
2. Filter to place-name text (by font size, content — exclude numbers, legend text)
3. **Detect point markers if present.** If the map has triangles, dots, or icons at labeled locations, use marker centroids instead of text centroids. Markers indicate the precise feature location; text labels are offset 50-200px for readability. PDF markers are often encoded as characters in a symbol font (e.g., `#` or `●` at a specific font size) — look for repeated non-alphanumeric glyphs.
4. **Handle PDF text fragmentation.** PyMuPDF often splits words due to character-level positioning (e.g., "Win sto n" instead of "Winston", or "Bl" + "ai" + "r HS" as separate spans). Group nearby text spans before matching. Also filter out legend text (which duplicates map labels) by checking whether the text falls inside the ROI mask.
5. Match place names to geographic coordinates using gazetteers:
   - **US places:** Census Bureau Gazetteer files (state-specific town/place centroids)
   - **International:** GeoNames database
   - **Features:** GNIS (Geographic Names Information System) for natural features
6. **Verify all coordinates per the GCP Data Quality Foundation above.** This is not optional.
7. Build GCP pairs: `(pixel_x, pixel_y) → (lat, lon)`
8. Optionally add boundary GCPs from known geographic features (state/county borders, coastlines, survey lines) visible in the map.
9. Fit transform with iterative outlier removal (see Transform Selection Guide).

### Path 6C: User-Provided GCPs

- User provides a list of `(pixel_x, pixel_y, lat, lon)` tuples
- Minimum 3 for affine, 6 for 2nd-order polynomial, 10 for 3rd-order
- **Recommendation:** Use affine if < 6 GCPs, polynomial if 6+
- **Still verify:** Even user-provided coordinates should be sanity-checked. Ask where the coordinates came from.

### Path 6D: Reference Shapefile Alignment

- User provides a shapefile/GeoJSON of known boundaries for the same area
- Show both the map image and the reference boundaries
- Help the user identify corresponding features (corners, intersections, distinctive shapes)
- Build GCP pairs from the correspondences
- Fit transform as in Path 6C

### Transform Selection Guide

| GCPs Available | Transform | Parameters | Best For |
|---------------|-----------|------------|----------|
| 3-5 | Affine | 6 | Maps with known projection, minimal distortion |
| 6-20 | Affine or 2nd-order polynomial | 6 or 12 | Affine for vector-rendered maps; polynomial for scanned maps with non-linear distortion |
| 20+ | 2nd-order polynomial | 12 | High accuracy with outlier removal |
| 3+ (uniform grid) | Affine | 6 | Coordinate-gridded maps |

**Prefer affine (order=1) for digitally-rendered maps** (vector PDFs, GIS exports). These maps have no scanning distortion, so the polynomial's extra degrees of freedom just overfit to coordinate noise. Reserve polynomial (order=2) for scanned/photographed maps with genuine non-linear warping.

**Do not use 3rd-order polynomials** unless you have 30+ well-distributed GCPs. Overfitting with high-order polynomials causes severe extrapolation artifacts (Runge's phenomenon).

**Outlier removal tuning:** Use sigma_thresh=3.0 with max 3 iterations as default. Aggressive thresholds (sigma=2.0) can remove GCPs with only 100-200m residuals — these are good GCPs that improve spatial coverage. Only tighten sigma if you have confirmed bad coordinates.

---

## Step 7: Apply Transform & Validate

Transform polygon vertices from pixel space to geographic coordinates using the fitted polynomial/affine. Set CRS to EPSG:4326 and compute areas by projecting to the estimated UTM zone. See @georeferencing-methods.md for the `transform_geometry()` function and code template.

### Validation Checks

1. **RMSE** — Report the residual error on GCPs in km.
   - State-level maps: < 2 km is good, < 1 km is excellent
   - County-level: < 500 m (< 100 m with verified coordinates)
   - Parcel-level: < 50 m
2. **Per-region RMSE** — Split GCPs into north/south (or quadrants) and report RMSE separately. If one region is 2x+ worse than another, GCPs are too sparse there or some coordinates are wrong. This catches edge distortion that overall RMSE hides.
3. **Point-in-polygon** — For each GCP feature (school, town, facility), check that its known geographic location falls inside the expected zone polygon. This is the most intuitive validation: if a feature's coordinates land in a neighboring zone instead of its own, either the coordinates or the transform are off.
4. **Total area** — Compare sum of zone areas to known area of the region (within 5%).
5. **Interactive overlay** — Generate a Plotly `choropleth_map` over OpenStreetMap tiles. This is the single most effective visual check — the user can immediately see whether zone edges align with real-world boundaries (state/county borders, rivers, roads). Always generate this, even if other validation passes.
6. **Residual plot** — Show histogram of GCP residual distances. Flag any bimodal patterns (suggests a systematic error in some GCPs).

---

## Step 8: Export

Export three artifacts:

1. **GeoJSON (EPSG:4326)** — individual polygons and dissolved (one per zone) via `gdf.dissolve(by="zone")`
2. **Shapefile in user's preferred CRS** — reproject with `to_crs()`, compute area in projected units. Note: column names must be ≤ 10 characters (DBF limitation).
3. **Optional: overlap removal** — if zones must be mutually exclusive, use priority-based subtraction. See @color-segmentation.md for the overlap removal code template.

### Interactive Preview (required)

Always generate an interactive Plotly overlay on OpenStreetMap tiles. This is the single most effective validation tool — the user can immediately see whether zone edges align with real-world features:

```python
import plotly.express as px
fig = px.choropleth_map(
    gdf_dissolved, geojson=json.loads(gdf_dissolved.to_json()),
    locations=gdf_dissolved.index, color="zone",
    map_style="open-street-map",
    center={"lat": center_lat, "lon": center_lon},
    zoom=10, opacity=0.5,
    title="Georeferenced Zone Boundaries",
)
fig.write_html("preview_georeferenced.html")
```

Open this in the browser and inspect before reporting results. Pay special attention to alignment near well-known boundaries (state/county borders, rivers, coastlines) — misalignment there reveals GCP coordinate errors that RMSE alone won't catch.

---

## Quality Checklist

Before delivering results, verify:

- [ ] **GCP coordinates verified** against an authoritative source (not estimated) — see GCP Data Quality Foundation
- [ ] **RMSE reported** and reasonable for the map scale, with **per-region split** (north/south or quadrants) to detect spatial bias
- [ ] **Point-in-polygon validation:** each labeled feature (school, town, etc.) falls inside its expected zone
- [ ] **Interactive overlay** on OpenStreetMap basemap (Plotly choropleth_map) — check alignment at known boundaries (state/county borders, coastlines, rivers)
- [ ] Total area within 5% of known area for the region (if known)
- [ ] No zone has zero coverage (unless expected)
- [ ] Zones are mutually exclusive (or overlaps documented)
- [ ] All zone labels present in output
- [ ] Output CRS matches user's request
- [ ] Geometries valid (no self-intersections) — check with `gdf.geometry.is_valid.all()`
- [ ] GeoJSON opens correctly in a GIS viewer or plotly preview

## Pitfalls

- **Inaccurate GCP coordinates are the #1 cause of bad georeferencing.** A GCP with 1 km coordinate error contributes 1+ km to transform RMSE regardless of how many other GCPs you have. Never estimate coordinates from memory — always verify against Google Maps, OpenStreetMap, or an authoritative geocoding source. This single factor dominates all other accuracy considerations.
- **PDF text removal with `fill=True`** (PyMuPDF default) paints white rectangles over colored zones — always use `fill=False`
- **HSV red wraps at 180** (OpenCV convention) — red is H < 10 OR H > 170, not a contiguous range
- **Polynomial transforms extrapolate poorly** outside the GCP convex hull — always add boundary GCPs at map edges. For maps with well-known geographic boundaries (e.g., state/county borders), use those boundary features as additional GCPs.
- **High-order polynomials with few GCPs** → Runge's phenomenon (wild oscillations between points). Use affine for < 6 GCPs. Even with 10+ GCPs, prefer affine (order=1) for vector-rendered maps unless you have evidence of non-linear distortion.
- **Text label positions ≠ feature positions.** When maps have point markers (triangles, dots) at feature locations, use the marker centroid as the GCP pixel position — not the text label centroid, which is typically offset 50-200px for readability.
- **Anti-aliased boundaries** create mixed-color pixels at zone edges — morphological cleanup (close + nearest-neighbor fill) handles this
- **Maps with hillshade or gradients** need preprocessing to flatten colors before HSV classification — consider adaptive thresholding or median filtering
- **Shapefile column names** must be <= 10 characters (DBF format limitation)
- **Large images at 600 DPI** can be multi-GB — monitor memory usage, downsample if needed
