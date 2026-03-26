# Georeferencing Methods

Code templates for all georeferencing transform paths. Referenced from the main skill via `@georeferencing-methods.md`.

---

## Reading an Embedded CRS (GeoTIFF)

When the input is a GeoTIFF with embedded CRS, no manual georeferencing is needed.

```python
import rasterio
import numpy as np

with rasterio.open(geotiff_path) as src:
    img = src.read()             # (bands, h, w)
    crs = src.crs                # e.g., CRS.from_epsg(4326)
    affine = src.transform       # pixel → geographic affine transform
    bounds = src.bounds          # BoundingBox(left, bottom, right, top)

# To get geographic coords for any pixel (col, row):
geo_x, geo_y = affine * (col, row)

# To transform a shapely geometry from pixel coords to geographic coords:
from shapely.ops import transform as shapely_transform
from shapely.geometry import Polygon

def pixel_to_geo_affine(x, y):
    """Transform pixel (col, row) to geographic (x, y) using rasterio affine."""
    gx, gy = affine * (x, y)
    return gx, gy

geo_polygon = shapely_transform(pixel_to_geo_affine, pixel_polygon)
```

---

## Path 6A: Affine Transform from Known Coordinates

Use when the map has coordinate ticks, grid lines, or a stated projection. Requires 3+ GCPs (more improves accuracy).

```python
import numpy as np

def fit_affine_transform(gcps):
    """Fit an affine transform from pixel coords to geographic coords.

    Args:
        gcps: list of dicts with keys: px_x, px_y, geo_x, geo_y

    Returns:
        coeff_x: [a, b, c] where geo_x = a + b*px_x + c*px_y
        coeff_y: [d, e, f] where geo_y = d + e*px_x + f*px_y
        rmse: residual error
    """
    n = len(gcps)
    px_x = np.array([g["px_x"] for g in gcps])
    px_y = np.array([g["px_y"] for g in gcps])
    geo_x = np.array([g["geo_x"] for g in gcps])
    geo_y = np.array([g["geo_y"] for g in gcps])

    # Design matrix: [1, px_x, px_y]
    A = np.column_stack([np.ones(n), px_x, px_y])

    # Solve for x and y coefficients
    coeff_x, _, _, _ = np.linalg.lstsq(A, geo_x, rcond=None)
    coeff_y, _, _, _ = np.linalg.lstsq(A, geo_y, rcond=None)

    # Compute RMSE
    pred_x = A @ coeff_x
    pred_y = A @ coeff_y
    residuals = np.sqrt((geo_x - pred_x)**2 + (geo_y - pred_y)**2)
    rmse = np.sqrt(np.mean(residuals**2))

    print(f"Affine fit: {n} GCPs, RMSE = {rmse:.6f} coordinate units")
    return coeff_x, coeff_y, rmse


def apply_affine(px_x, px_y, coeff_x, coeff_y):
    """Transform pixel coordinates to geographic using fitted affine."""
    geo_x = coeff_x[0] + coeff_x[1] * px_x + coeff_x[2] * px_y
    geo_y = coeff_y[0] + coeff_y[1] * px_x + coeff_y[2] * px_y
    return geo_x, geo_y
```

For coordinate-gridded maps where the projection is known, the RMSE should be near-zero. If it's not, check that the GCP coordinates are in the correct order and units.

---

## Path 6B: 2nd-Order Polynomial with Iterative Outlier Removal

The workhorse for most scanned maps. Handles non-linear distortions from scanning, printing, and map projections.

### Fitting the Transform

```python
import numpy as np

def fit_polynomial_transform(gcps, order=2, max_iterations=3, sigma_thresh=3.0):
    """Fit polynomial transform with iterative outlier removal.

    The polynomial maps normalized pixel coords to geographic coords:
        geo = c0 + c1*xn + c2*yn + c3*xn^2 + c4*xn*yn + c5*yn^2

    Normalization (subtracting mean, dividing by std) is critical for
    numerical stability — without it, the x^2 and xy terms can be
    many orders of magnitude larger than the linear terms.

    Args:
        gcps: list of dicts with keys: px_x, px_y, lat, lon
              (or geo_x, geo_y for projected coordinates)
        order: polynomial order (1=affine, 2=quadratic)
        max_iterations: outlier removal iterations
        sigma_thresh: remove GCPs with residual > mean + sigma_thresh * std

    Returns:
        coeff_lat, coeff_lon: polynomial coefficients
        norm: normalization parameters dict
        mask: boolean array of which GCPs were kept
        rmse: final RMSE in km
    """
    px_x = np.array([g["px_x"] for g in gcps])
    px_y = np.array([g["px_y"] for g in gcps])
    lat = np.array([g["lat"] for g in gcps])
    lon = np.array([g["lon"] for g in gcps])

    # Normalization parameters for numerical stability
    norm = {
        "px_x_mean": float(px_x.mean()),
        "px_x_std": float(px_x.std()),
        "px_y_mean": float(px_y.mean()),
        "px_y_std": float(px_y.std()),
    }

    mask = np.ones(len(gcps), dtype=bool)

    for iteration in range(max_iterations):
        xn = (px_x[mask] - norm["px_x_mean"]) / norm["px_x_std"]
        yn = (px_y[mask] - norm["px_y_mean"]) / norm["px_y_std"]

        # Build design matrix based on order
        if order == 1:
            A = np.column_stack([np.ones(len(xn)), xn, yn])
        elif order == 2:
            A = np.column_stack([
                np.ones(len(xn)), xn, yn, xn**2, xn * yn, yn**2
            ])
        else:
            raise ValueError(f"Order {order} not supported (use 1 or 2)")

        coeff_lat, _, _, _ = np.linalg.lstsq(A, lat[mask], rcond=None)
        coeff_lon, _, _, _ = np.linalg.lstsq(A, lon[mask], rcond=None)

        # Compute residual distance in km
        lat_pred = A @ coeff_lat
        lon_pred = A @ coeff_lon
        mean_lat = np.mean(lat[mask])
        km_per_deg_lat = 111.0
        km_per_deg_lon = 111.0 * np.cos(np.radians(mean_lat))

        dist_km = np.sqrt(
            ((lat[mask] - lat_pred) * km_per_deg_lat) ** 2 +
            ((lon[mask] - lon_pred) * km_per_deg_lon) ** 2
        )

        rmse = np.sqrt(np.mean(dist_km ** 2))
        thresh = dist_km.mean() + sigma_thresh * dist_km.std()

        # Remove outliers
        idx_in_mask = np.where(mask)[0]
        n_removed = 0
        for i, d in zip(idx_in_mask, dist_km):
            if d > thresh:
                mask[i] = False
                n_removed += 1

        print(f"  Iter {iteration + 1}: {mask.sum()} GCPs, "
              f"RMSE={rmse:.3f} km, removed={n_removed}")

        if n_removed == 0:
            break

    # Final fit with clean GCPs
    xn = (px_x[mask] - norm["px_x_mean"]) / norm["px_x_std"]
    yn = (px_y[mask] - norm["px_y_mean"]) / norm["px_y_std"]
    if order == 1:
        A = np.column_stack([np.ones(len(xn)), xn, yn])
    else:
        A = np.column_stack([np.ones(len(xn)), xn, yn, xn**2, xn * yn, yn**2])

    coeff_lat, _, _, _ = np.linalg.lstsq(A, lat[mask], rcond=None)
    coeff_lon, _, _, _ = np.linalg.lstsq(A, lon[mask], rcond=None)

    lat_pred = A @ coeff_lat
    lon_pred = A @ coeff_lon
    dist_km = np.sqrt(
        ((lat[mask] - lat_pred) * km_per_deg_lat) ** 2 +
        ((lon[mask] - lon_pred) * km_per_deg_lon) ** 2
    )
    rmse = np.sqrt(np.mean(dist_km ** 2))

    print(f"\n  Final: {mask.sum()} GCPs, RMSE={rmse:.3f} km")
    print(f"  Mean={dist_km.mean():.3f} km, Median={np.median(dist_km):.3f} km, "
          f"Max={dist_km.max():.3f} km")

    return coeff_lat, coeff_lon, norm, mask, rmse
```

### Applying the Transform

```python
def pixel_to_latlon(px_x, px_y, coeff_lat, coeff_lon, norm, order=2):
    """Transform pixel coordinates to lat/lon using fitted polynomial.

    Works with both scalar and array inputs.
    """
    xn = (px_x - norm["px_x_mean"]) / norm["px_x_std"]
    yn = (px_y - norm["px_y_mean"]) / norm["px_y_std"]

    if order == 1:
        lat = coeff_lat[0] + coeff_lat[1] * xn + coeff_lat[2] * yn
        lon = coeff_lon[0] + coeff_lon[1] * xn + coeff_lon[2] * yn
    elif order == 2:
        lat = (coeff_lat[0] + coeff_lat[1] * xn + coeff_lat[2] * yn +
               coeff_lat[3] * xn**2 + coeff_lat[4] * xn * yn +
               coeff_lat[5] * yn**2)
        lon = (coeff_lon[0] + coeff_lon[1] * xn + coeff_lon[2] * yn +
               coeff_lon[3] * xn**2 + coeff_lon[4] * xn * yn +
               coeff_lon[5] * yn**2)

    return lat, lon
```

### Transforming Geometries

```python
from shapely.geometry import Polygon, MultiPolygon

def transform_geometry(geom, coeff_lat, coeff_lon, norm, order=2):
    """Transform a shapely geometry from pixel to lat/lon coordinates.

    Handles Polygon and MultiPolygon types, including interior rings (holes).
    Output coordinates are in (lon, lat) order for GeoJSON compatibility.
    """
    def _transform_ring(coords):
        xs = np.array([c[0] for c in coords])
        ys = np.array([c[1] for c in coords])
        lats, lons = pixel_to_latlon(xs, ys, coeff_lat, coeff_lon, norm, order)
        return list(zip(lons.tolist(), lats.tolist()))

    if geom.geom_type == "Polygon":
        ext = _transform_ring(geom.exterior.coords)
        holes = [_transform_ring(h.coords) for h in geom.interiors]
        return Polygon(ext, holes)
    elif geom.geom_type == "MultiPolygon":
        polys = []
        for p in geom.geoms:
            ext = _transform_ring(p.exterior.coords)
            holes = [_transform_ring(h.coords) for h in p.interiors]
            polys.append(Polygon(ext, holes))
        return MultiPolygon(polys)
    else:
        raise ValueError(f"Unsupported geometry type: {geom.geom_type}")
```

---

## Building GCPs from Text Labels (Path 6B detail)

### Matching text spans to geographic coordinates

```python
def build_text_gcps(labeled_regions, big_regions, text_spans, gazetteer,
                    font_size_range=(5.0, 9.0)):
    """Build GCPs by matching text labels to a coordinate gazetteer.

    Args:
        labeled_regions: numpy array from scipy.ndimage.label — each connected
                         region has a unique integer label
        big_regions: dict of {region_id: pixel_count} for regions above threshold
        text_spans: list of dicts with keys: text, centroid_px, size
        gazetteer: dict of {place_name_lower: (lat, lon)}
        font_size_range: (min, max) font size in PDF points for place-name text

    Returns:
        list of GCP dicts with keys: name, px_x, px_y, lat, lon, area_px
    """
    # Filter to place-name text spans (by font size, content)
    place_spans = []
    for s in text_spans:
        text = s["text"].strip()
        size = s["size"]
        if (font_size_range[0] <= size <= font_size_range[1]
                and not text.replace(" ", "").replace("-", "").isdigit()
                and len(text) > 1):
            place_spans.append({
                "text": text,
                "cx": s["centroid_px"][0],
                "cy": s["centroid_px"][1],
            })

    # Map each text span to the region it falls in
    region_to_texts = {}
    for ts in place_spans:
        px_x = int(round(ts["cx"]))
        px_y = int(round(ts["cy"]))
        h, w = labeled_regions.shape
        if 0 <= px_y < h and 0 <= px_x < w:
            rid = labeled_regions[px_y, px_x]
            if rid > 0 and rid in big_regions:
                region_to_texts.setdefault(rid, []).append(ts["text"])

    # Build GCPs: compute pixel centroids, match to gazetteer
    gcps = []
    for rid, texts in region_to_texts.items():
        # Use the full text as the place name (join if multi-word)
        place_name = " ".join(texts).lower().strip()

        # Try exact match, then individual words
        if place_name in gazetteer:
            lat, lon = gazetteer[place_name]
        elif len(texts) == 1 and texts[0].lower() in gazetteer:
            lat, lon = gazetteer[texts[0].lower()]
            place_name = texts[0].lower()
        else:
            continue  # No match

        # Pixel centroid of the region
        ys, xs = np.where(labeled_regions == rid)
        cx, cy = float(xs.mean()), float(ys.mean())

        gcps.append({
            "name": place_name,
            "px_x": cx,
            "px_y": cy,
            "lat": lat,
            "lon": lon,
            "area_px": int(big_regions[rid]),
        })

    print(f"  Matched {len(gcps)} text-label GCPs from {len(region_to_texts)} labeled regions")
    return gcps
```

### Adding boundary extreme GCPs

Anchor the transform at map edges where text-label GCPs may be sparse.

```python
def build_boundary_gcps(map_mask, known_extremes):
    """Create GCPs from extreme points on the map boundary.

    Args:
        map_mask: boolean array (h, w) of the map region
        known_extremes: dict mapping extreme name to (lat, lon), e.g.:
            {"northernmost": (45.305, -71.085),
             "southernmost": (42.697, -71.294), ...}

    Returns:
        list of GCP dicts
    """
    mask_u8 = map_mask.astype(np.uint8)
    contours, _ = cv2.findContours(mask_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contour = max(contours, key=cv2.contourArea)
    pts = contour.squeeze()
    xs, ys = pts[:, 0], pts[:, 1]

    finders = {
        "northernmost": lambda: np.argmin(ys),
        "southernmost": lambda: np.argmax(ys),
        "westernmost": lambda: np.argmin(xs),
        "easternmost": lambda: np.argmax(xs),
    }

    gcps = []
    for name, (lat, lon) in known_extremes.items():
        if name in finders:
            idx = finders[name]()
            gcps.append({
                "name": f"__boundary_{name}",
                "px_x": float(xs[idx]),
                "px_y": float(ys[idx]),
                "lat": lat,
                "lon": lon,
                "area_px": 0,
            })
            print(f"    {name}: px=({xs[idx]:.0f}, {ys[idx]:.0f}) -> ({lat:.4f}, {lon:.4f})")

    return gcps
```

---

## Gazetteer Sources

For matching place names to coordinates:

| Source | Coverage | How to Access |
|--------|----------|---------------|
| **US Census Gazetteer** | US towns, places, counties | Download from census.gov/geographies/reference-files/time-series/geo/gazetteer-files.html |
| **GeoNames** | Global place names | Download from geonames.org or API |
| **GNIS** | US geographic feature names | Download from geonames.usgs.gov |
| **OpenStreetMap Nominatim** | Global, crowdsourced | API: nominatim.openstreetmap.org (rate limited) |

For US Census Gazetteer, the format is a tab-delimited file with columns including `NAME`, `INTPTLAT`, `INTPTLONG` (internal point latitude/longitude).

```python
import pandas as pd

def load_census_gazetteer(filepath):
    """Load US Census Gazetteer file as a place-name → (lat, lon) dict."""
    df = pd.read_csv(filepath, sep='\t')
    # Column names vary by file type — adapt as needed
    lat_col = [c for c in df.columns if 'LAT' in c.upper()][0]
    lon_col = [c for c in df.columns if 'LONG' in c.upper()][0]
    name_col = [c for c in df.columns if 'NAME' in c.upper()][0]

    gazetteer = {}
    for _, row in df.iterrows():
        name = str(row[name_col]).strip().lower()
        lat = float(row[lat_col])
        lon = float(row[lon_col])
        gazetteer[name] = (lat, lon)

    return gazetteer
```

---

## RMSE Computation and Residual Analysis

```python
def compute_rmse_km(gcps, coeff_lat, coeff_lon, norm, order=2):
    """Compute RMSE in km for a set of GCPs against a fitted transform."""
    px_x = np.array([g["px_x"] for g in gcps])
    px_y = np.array([g["px_y"] for g in gcps])
    lat_true = np.array([g["lat"] for g in gcps])
    lon_true = np.array([g["lon"] for g in gcps])

    lat_pred, lon_pred = pixel_to_latlon(px_x, px_y, coeff_lat, coeff_lon, norm, order)

    mean_lat = np.mean(lat_true)
    km_per_deg_lat = 111.0
    km_per_deg_lon = 111.0 * np.cos(np.radians(mean_lat))

    dist_km = np.sqrt(
        ((lat_true - lat_pred) * km_per_deg_lat) ** 2 +
        ((lon_true - lon_pred) * km_per_deg_lon) ** 2
    )

    rmse = np.sqrt(np.mean(dist_km ** 2))
    return rmse, dist_km


def plot_residuals(dist_km, title="GCP Residuals"):
    """Plot histogram of GCP residual distances."""
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(dist_km, bins=30, color="steelblue", edgecolor="white", alpha=0.8)
    ax.axvline(np.mean(dist_km), color="red", linestyle="--",
               label=f"Mean: {np.mean(dist_km):.2f} km")
    ax.set_xlabel("Residual distance (km)")
    ax.set_ylabel("Count")
    rmse = np.sqrt(np.mean(dist_km**2))
    ax.set_title(f"{title} (n={len(dist_km)}, RMSE={rmse:.2f} km)")
    ax.legend()
    fig.tight_layout()
    return fig
```

---

## Saving and Loading Transform Coefficients

```python
import json

def save_transform(filepath, coeff_lat, coeff_lon, norm, order, rmse, n_gcps_total, n_gcps_used):
    """Save transform coefficients to JSON for reproducibility."""
    transform = {
        "order": order,
        "normalization": norm,
        "coefficients_lat": coeff_lat.tolist() if hasattr(coeff_lat, 'tolist') else list(coeff_lat),
        "coefficients_lon": coeff_lon.tolist() if hasattr(coeff_lon, 'tolist') else list(coeff_lon),
        "rmse_km": float(rmse),
        "n_gcps_total": n_gcps_total,
        "n_gcps_used": n_gcps_used,
    }
    with open(filepath, "w") as f:
        json.dump(transform, f, indent=2)


def load_transform(filepath):
    """Load transform coefficients from JSON."""
    with open(filepath) as f:
        t = json.load(f)
    return (np.array(t["coefficients_lat"]),
            np.array(t["coefficients_lon"]),
            t["normalization"],
            t["order"])
```
