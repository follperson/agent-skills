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

---

## Step 0: Intake & Triage (DECISION GATE 1)

Before writing any code, ask the user these questions. Their answers determine which pipeline path to follow.

**Questions to ask:**

1. **Input format?** PDF, PNG, TIFF, or GeoTIFF?
2. **What do the colored zones represent?** Utility service areas, wetlands, land use, zoning districts, soil types, vegetation, geology, etc.
3. **Can you name the colors and what each represents?** Or should we auto-detect color clusters and have you label them?
4. **Is the map already georeferenced?** (GeoTIFF with embedded CRS → skip to Step 4)
5. **Does the map have text labels?** Town names, place names, feature labels that could serve as GCPs?
6. **Does the map show coordinate ticks, grid lines, or state a projection?** If yes, we can use a simpler affine transform.
7. **Do you have a reference shapefile/GeoJSON for the same area?** (e.g., Census boundaries, NHD wetlands, USGS geology) This helps both with GCP creation and validation.
8. **What geographic area does the map cover?** (state, county, watershed, etc.)
9. **What output CRS and format do you need?** Default: GeoJSON in EPSG:4326 + shapefile in a local projection.

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

### PDF Input
```python
import fitz  # PyMuPDF

doc = fitz.open(pdf_path)
page = doc[page_number]

# Render at high DPI (400-600 recommended; 600 for detailed maps)
dpi = 600
zoom = dpi / 72
mat = fitz.Matrix(zoom, zoom)
pix = page.get_pixmap(matrix=mat)
img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)

# Extract text spans (needed for Path 6B and text removal)
text_dict = page.get_text("dict")
text_spans = []
for block in text_dict["blocks"]:
    if "lines" not in block:
        continue
    for line in block["lines"]:
        for span in line["spans"]:
            bbox = span["bbox"]  # in PDF points
            text_spans.append({
                "text": span["text"],
                "bbox_pdf": list(bbox),
                "bbox_px": [b * zoom for b in bbox],
                "size": span["size"],
                "centroid_px": [(bbox[0] + bbox[2]) / 2 * zoom,
                                (bbox[1] + bbox[3]) / 2 * zoom],
            })
```

**If text needs removal** (text overlays colored zones): use PyMuPDF redactions with `fill=False` — this removes text content stream objects without painting white rectangles over the map.

```python
for span_info in text_spans_to_remove:
    bbox = fitz.Rect(span_info["bbox_pdf"])
    page.add_redact_annot(bbox, fill=False)
page.apply_redactions()
# Re-render after redaction
```

### PNG / TIFF Input
```python
import cv2
img = cv2.imread(str(image_path))  # BGR format
# Or for TIFF with alpha:
img = cv2.imread(str(image_path), cv2.IMREAD_UNCHANGED)
```

### GeoTIFF Input
```python
import rasterio
with rasterio.open(geotiff_path) as src:
    img = src.read()           # shape: (bands, h, w)
    crs = src.crs              # e.g., EPSG:4326
    transform = src.transform  # affine transform pixel→geo
    bounds = src.bounds
# Transpose to (h, w, bands) for OpenCV compatibility
img = np.moveaxis(img, 0, -1)
```

If GeoTIFF has an embedded CRS, skip to Step 4 — georeferencing is already done.

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

**Approach B — User-defined crop:**
If the user can specify the map boundaries, just crop to a bounding box.

---

## Step 4: Color Segmentation (DECISION GATE 2)

This is where zones are classified. Two approaches — choose based on color distinctiveness.

### Approach A: HSV Thresholding (preferred when colors are distinct)

Show the user an HSV histogram or color samples from the map. Ask them to confirm/adjust the zone-color mapping.

```python
# Define zone color profiles as dicts
ZONE_PROFILES = {
    "zone_name": {"h_range": (lo, hi), "s_range": (lo, hi), "v_range": (lo, hi)},
    # ...
}
```

See @color-segmentation.md for the full classification framework.

**Important HSV notes:**
- OpenCV HSV: H is 0-180 (not 0-360), S and V are 0-255
- Red wraps around: H < 10 OR H > 170
- Classify more-specific colors first (e.g., light blue before dark blue — separate by saturation)

### Approach B: K-Means Clustering (when colors are not pre-specified)

```python
from sklearn.cluster import KMeans

# Sample pixels for speed
interior_pixels = img_hsv[roi_mask]
sample_idx = np.random.choice(len(interior_pixels), min(50000, len(interior_pixels)), replace=False)
samples = interior_pixels[sample_idx].astype(float)

kmeans = KMeans(n_clusters=K, random_state=42, n_init=10).fit(samples)
```

Show cluster centers to the user and ask them to label each cluster.

### Post-classification cleanup

After classification: morphological close (bridge line-removal gaps), remove specks < threshold, then iterative dilation to assign unclassified interior pixels to their nearest zone. See @color-segmentation.md for cleanup code.

**Validation:** Show the classified overlay to the user. Report pixel counts per zone. Check mutual exclusivity.

---

## Step 5: Polygonize

Convert the raster label array to vector polygons in **pixel coordinates**.

```python
from rasterio.features import shapes
from rasterio.transform import from_bounds
import geopandas as gpd
from shapely.geometry import shape

h, w = labels.shape
transform = from_bounds(0, h, w, 0, w, h)  # identity: x=col, y=row

records = []
for zone_value, zone_name in ZONE_LABELS.items():
    mask = (labels == zone_value).astype(np.uint8)
    if mask.sum() == 0:
        continue
    for geom, value in shapes(mask, mask=mask, transform=transform):
        poly = shape(geom)
        poly = poly.simplify(2.0, preserve_topology=True)
        if not poly.is_valid:
            poly = poly.buffer(0)
        if poly.is_empty:
            continue
        records.append({
            "geometry": poly,
            "zone": zone_name,
            "label_id": int(zone_value),
            "area_px": poly.area,
        })

gdf_px = gpd.GeoDataFrame(records, geometry="geometry")
```

Output: GeoDataFrame in pixel coordinates (no CRS yet). Save as intermediate GeoJSON.

---

## Step 6: Georeference (DECISION GATE 3)

Choose the transform path based on Step 0 triage. See @georeferencing-methods.md for full code templates.

### Path 6A: Known Projection (Affine Transform)

Use when the map has coordinate ticks, grid lines, or a stated projection.

- User picks 3+ pixel positions that correspond to known coordinates (grid intersections, labeled tick marks)
- Fit affine transform (6 parameters): handles translation, rotation, scale, skew
- RMSE should be near-zero for clean grid coordinates

### Path 6B: Text-Label GCPs (Polynomial Transform)

Use when the map is a PDF with readable place names that can be matched to a gazetteer.

1. Extract text spans from PDF (Step 1 output)
2. Filter to place-name text (by font size, content — exclude numbers, legend text)
3. Match place names to geographic coordinates:
   - **US places:** Census Bureau Gazetteer files (state-specific town/place centroids)
   - **International:** GeoNames database
   - **Features:** GNIS (Geographic Names Information System) for natural features
4. For each matched text label, compute the pixel centroid of the region it labels
5. Build GCP pairs: `(pixel_x, pixel_y) → (lat, lon)`
6. Optionally add boundary extreme GCPs (northernmost, southernmost, etc. points of the map outline matched to known geographic extremes)
7. Fit 2nd-order polynomial with iterative outlier removal

### Path 6C: User-Provided GCPs

- User provides a list of `(pixel_x, pixel_y, lat, lon)` tuples
- Minimum 3 for affine, 6 for 2nd-order polynomial, 10 for 3rd-order
- **Recommendation:** Use affine if < 6 GCPs, polynomial if 6+

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
| 6-20 | 2nd-order polynomial | 12 | Most scanned maps, moderate distortion |
| 20+ | 2nd-order polynomial | 12 | High accuracy with outlier removal |
| 3+ (uniform grid) | Affine | 6 | Coordinate-gridded maps |

**Do not use 3rd-order polynomials** unless you have 30+ well-distributed GCPs. Overfitting with high-order polynomials causes severe extrapolation artifacts (Runge's phenomenon).

---

## Step 7: Apply Transform & Validate

Transform polygon vertices from pixel space to geographic coordinates.

```python
# Apply the fitted transform to all polygon geometries
geo_geoms = []
for geom in gdf_px.geometry:
    geo_geom = transform_geometry(geom, coeff_lat, coeff_lon, norm)
    if not geo_geom.is_valid:
        geo_geom = geo_geom.buffer(0)
    geo_geoms.append(geo_geom)

gdf_geo = gdf_px.copy()
gdf_geo["geometry"] = geo_geoms
gdf_geo = gdf_geo.set_crs("EPSG:4326")

# Compute area using a projected CRS
gdf_utm = gdf_geo.to_crs(gdf_geo.estimate_utm_crs())
gdf_geo["area_km2"] = gdf_utm.area / 1e6
```

See @georeferencing-methods.md for the `transform_geometry()` function.

### Validation Checks

1. **RMSE** — Report the residual error on GCPs in km.
   - State-level maps: < 2 km is good, < 1 km is excellent
   - County-level: < 500 m
   - Parcel-level: < 50 m
2. **Total area** — Compare sum of zone areas to known area of the region (within 5%).
3. **Visual overlay** — If a reference shapefile is available, overlay georeferenced polygons on reference boundaries. Show the user. Look for systematic shifts or distortions at edges.
4. **Residual plot** — Show histogram of GCP residual distances. Flag any bimodal patterns (suggests a systematic error in some GCPs).

---

## Step 8: Export

### GeoJSON (always export in EPSG:4326)
```python
gdf_geo.to_file("output_individual.geojson", driver="GeoJSON")

# Dissolved (one polygon per zone)
gdf_dissolved = gdf_geo.dissolve(by="zone", aggfunc="sum").reset_index()
gdf_dissolved.to_file("output_dissolved.geojson", driver="GeoJSON")
```

### Shapefile in user's preferred CRS
```python
target_crs = "EPSG:32619"  # or whatever the user specified
gdf_proj = gdf_geo.to_crs(target_crs)
gdf_proj["area_m2"] = gdf_proj.area
gdf_proj.to_file("output.shp", driver="ESRI Shapefile")
```

### Optional: Overlap Removal

If zones should be mutually exclusive, remove overlaps using priority-based subtraction:
```python
from shapely.validation import make_valid
from shapely.ops import unary_union

# User defines priority (1 = highest = keeps shape; higher numbers lose contested pixels)
PRIORITY = {"wetland_A": 1, "wetland_B": 2, "upland": 3}  # example

dissolved = gdf_geo.dissolve(by="zone").reset_index()
dissolved["priority"] = dissolved["zone"].map(PRIORITY)
dissolved = dissolved.sort_values("priority")

claimed = None
for idx, row in dissolved.iterrows():
    geom = make_valid(row.geometry)
    if claimed is not None:
        geom = geom.difference(claimed)
        geom = make_valid(geom)
    dissolved.at[idx, "geometry"] = geom
    claimed = geom if claimed is None else unary_union([claimed, geom])
```

### Previews

Generate a static PNG (matplotlib) and/or interactive HTML (plotly) preview for the user to validate.

---

## Quality Checklist

Before delivering results, verify:

- [ ] Total area within 5% of known area for the region (if known)
- [ ] No zone has zero coverage (unless expected)
- [ ] Zones are mutually exclusive (or overlaps documented)
- [ ] RMSE reported and reasonable for the map scale
- [ ] Visual overlay on reference boundaries looks correct at edges
- [ ] All zone labels present in output
- [ ] Output CRS matches user's request
- [ ] Geometries valid (no self-intersections) — check with `gdf.geometry.is_valid.all()`
- [ ] GeoJSON opens correctly in a GIS viewer or plotly preview

## Pitfalls

- **PDF text removal with `fill=True`** (PyMuPDF default) paints white rectangles over colored zones — always use `fill=False`
- **HSV red wraps at 180** (OpenCV convention) — red is H < 10 OR H > 170, not a contiguous range
- **Polynomial transforms extrapolate poorly** outside the GCP convex hull — always add boundary GCPs at map edges
- **High-order polynomials with few GCPs** → Runge's phenomenon (wild oscillations between points). Use affine for < 6 GCPs.
- **Anti-aliased boundaries** create mixed-color pixels at zone edges — morphological cleanup (close + nearest-neighbor fill) handles this
- **Maps with hillshade or gradients** need preprocessing to flatten colors before HSV classification — consider adaptive thresholding or median filtering
- **Shapefile column names** must be <= 10 characters (DBF format limitation)
- **Large images at 600 DPI** can be multi-GB — monitor memory usage, downsample if needed
