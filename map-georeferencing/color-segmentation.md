# Color Segmentation & Preprocessing

Code templates for color classification, line removal, and morphological cleanup. Referenced from the main skill via `@color-segmentation.md`.

---

## Line Removal: Three-Detector Approach

Use when the map has boundary lines between zones that need to be removed before color classification.

### Detector 1: Absolute HSV Threshold

Catches black and grey boundary lines. Tune thresholds based on the specific map.

```python
import cv2
import numpy as np

def detect_lines_absolute(img_bgr, dark_v=80, grey_v=140, light_grey_v=200,
                          dark_max_s=40, grey_max_s=25, light_grey_max_s=10):
    """Detect boundary lines via absolute HSV thresholds.

    Args:
        img_bgr: input image (BGR)
        dark_v: V threshold for black lines
        grey_v: V threshold for medium grey lines
        light_grey_v: V threshold for light grey lines
        dark_max_s: max saturation for black line pixels
        grey_max_s: max saturation for grey line pixels
        light_grey_max_s: max saturation for light grey line pixels

    Returns:
        boolean mask of detected line pixels
    """
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    S, V = hsv[:, :, 1], hsv[:, :, 2]

    dark_mask = (V < dark_v) & (S < dark_max_s)
    grey_mask = (V >= dark_v) & (V < grey_v) & (S < grey_max_s)
    light_grey_mask = (V >= grey_v) & (V < light_grey_v) & (S < light_grey_max_s)

    return dark_mask | grey_mask | light_grey_mask
```

### Detector 2: Local Contrast

Catches faint lines that are darker than their neighborhood but above the absolute threshold.

```python
from scipy.ndimage import uniform_filter

def detect_lines_local_contrast(img_bgr, radius=8, contrast_threshold=30,
                                sat_drop_threshold=15):
    """Detect lines via local contrast in the V channel.

    Finds pixels significantly darker than their local neighborhood.
    Also considers saturation drop — boundary lines typically have
    lower saturation than surrounding colored zones.

    Args:
        img_bgr: input image (BGR)
        radius: neighborhood radius for local mean computation
        contrast_threshold: minimum V difference to flag as line
        sat_drop_threshold: minimum S difference for secondary detection

    Returns:
        boolean mask of detected line pixels
    """
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    V = hsv[:, :, 2].astype(np.float32)
    S = hsv[:, :, 1].astype(np.float32)

    kernel_size = 2 * radius + 1
    V_local_mean = uniform_filter(V, size=kernel_size)
    S_local_mean = uniform_filter(S, size=kernel_size)

    contrast = V_local_mean - V
    sat_drop = S_local_mean - S

    # Primary: significantly darker than neighborhood
    dark_relative = contrast > contrast_threshold
    # Secondary: moderate darkness + saturation drop (lines are achromatic)
    moderate_dark = (contrast > contrast_threshold / 2) & (sat_drop > sat_drop_threshold)

    return dark_relative | moderate_dark
```

### Detector 3: Text Remnant Cleanup

Catches text fragments that survived PDF redaction, within known text bounding boxes.

```python
def detect_text_remnants(img_bgr, text_spans, pad=6):
    """Detect text fragments within known text span bounding boxes.

    Catches both dark text remnants and white text on colored backgrounds.

    Args:
        img_bgr: input image (BGR)
        text_spans: list of dicts with bbox_px key (x0, y0, x1, y1 in pixels)
        pad: pixel padding around each text bbox

    Returns:
        boolean mask of detected text pixels
    """
    h, w = img_bgr.shape[:2]
    mask = np.zeros((h, w), dtype=bool)
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)

    for span in text_spans:
        bbox = span["bbox_px"]
        x0 = max(0, int(bbox[0]) - pad)
        y0 = max(0, int(bbox[1]) - pad)
        x1 = min(w, int(bbox[2]) + pad)
        y1 = min(h, int(bbox[3]) + pad)

        roi_hsv = hsv[y0:y1, x0:x1]
        roi_v = roi_hsv[:, :, 2]
        roi_s = roi_hsv[:, :, 1]

        # Dark text remnants
        dark_text = (roi_v < 120) & (roi_s < 80)

        # White text on colored backgrounds only
        colored_fraction = (roi_s > 40).sum() / max(roi_s.size, 1)
        if colored_fraction > 0.3:
            white_text = (roi_v > 220) & (roi_s < 20)
        else:
            white_text = np.zeros_like(roi_v, dtype=bool)

        mask[y0:y1, x0:x1] |= (dark_text | white_text)

    return mask
```

### Combining Detectors and Propagating Colors

```python
from scipy.ndimage import distance_transform_edt

def remove_lines_and_propagate(img_bgr, text_spans=None,
                                dark_v=80, contrast_radius=8,
                                contrast_threshold=30):
    """Full line removal pipeline: detect, dilate, propagate.

    Two-pass approach: Pass 1 removes major lines, Pass 2 catches
    anti-aliased residuals near Pass 1 detections.
    """
    # --- Pass 1: Major line + text removal ---
    abs_mask = detect_lines_absolute(img_bgr, dark_v=dark_v)
    contrast_mask = detect_lines_local_contrast(
        img_bgr, radius=contrast_radius, contrast_threshold=contrast_threshold
    )

    combined = abs_mask | contrast_mask
    if text_spans:
        text_mask = detect_text_remnants(img_bgr, text_spans)
        combined = combined | text_mask

    # Dilate to catch anti-aliased edges
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    pass1_mask = cv2.dilate(combined.astype(np.uint8), kernel, iterations=1).astype(bool)

    # Propagate colors (nearest non-masked pixel replaces each masked pixel)
    result = propagate_colors(img_bgr, pass1_mask)

    # --- Pass 2: Residual anti-aliased edges ---
    residual = detect_lines_local_contrast(
        result, radius=contrast_radius - 2, contrast_threshold=contrast_threshold // 2
    )
    near_lines = cv2.dilate(
        pass1_mask.astype(np.uint8), np.ones((21, 21), np.uint8)
    ).astype(bool)
    pass2_mask = residual & near_lines & ~pass1_mask

    if pass2_mask.sum() > 0:
        pass2_dilated = cv2.dilate(
            pass2_mask.astype(np.uint8), kernel, iterations=1
        ).astype(bool)
        result = propagate_colors(result, pass2_dilated)

    return result


def propagate_colors(img_bgr, removal_mask):
    """Replace masked pixels with nearest non-masked color.

    Uses scipy's distance transform to find the nearest non-masked pixel
    for each masked pixel. This effectively splits zone borders at the
    center line — each side gets the color from its respective zone.
    """
    dist, indices = distance_transform_edt(removal_mask, return_indices=True)

    result = img_bgr.copy()
    mask_y, mask_x = np.where(removal_mask)
    nearest_y = indices[0][mask_y, mask_x]
    nearest_x = indices[1][mask_y, mask_x]
    result[mask_y, mask_x] = img_bgr[nearest_y, nearest_x]

    return result
```

---

## Color Classification

### Approach A: HSV Thresholding

Best when zones have distinct, well-separated colors that can be described by HSV ranges.

```python
def classify_by_hsv(img_bgr, roi_mask, zone_profiles):
    """Classify pixels by zone using HSV thresholds.

    Args:
        img_bgr: input image (BGR), ideally after line removal
        roi_mask: boolean mask of the mappable area
        zone_profiles: dict of zone definitions, e.g.:
            {
                "wetland_A": {
                    "label": 1,
                    "h_range": (35, 75),   # Hue range (0-180 in OpenCV)
                    "s_range": (80, 255),  # Saturation range
                    "v_range": (80, 255),  # Value range
                },
                "upland": {
                    "label": 2,
                    "h_range": (20, 40),
                    "s_range": (100, 255),
                    "v_range": (100, 255),
                },
                # For red (wraps around Hue=0): set h_range to (170, 10)
                # The function handles the wrap-around automatically.
            }

    Returns:
        labels: uint8 array with zone label values
    """
    h, w = img_bgr.shape[:2]
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    H, S, V = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]

    labels = np.zeros((h, w), dtype=np.uint8)
    interior = roi_mask.astype(bool)

    for zone_name, profile in zone_profiles.items():
        label_val = profile["label"]
        h_lo, h_hi = profile["h_range"]
        s_lo, s_hi = profile["s_range"]
        v_lo, v_hi = profile["v_range"]

        # Handle hue wrap-around (red spans both ends of 0-180)
        if h_lo > h_hi:
            h_mask = (H >= h_lo) | (H <= h_hi)
        else:
            h_mask = (H >= h_lo) & (H <= h_hi)

        s_mask = (S >= s_lo) & (S <= s_hi)
        v_mask = (V >= v_lo) & (V <= v_hi)

        zone_mask = interior & h_mask & s_mask & v_mask & (labels == 0)
        labels[zone_mask] = label_val

        count = zone_mask.sum()
        pct = 100 * count / interior.sum() if interior.sum() > 0 else 0
        print(f"  {zone_name}: {count:>12,} px ({pct:.1f}%)")

    # Summary
    classified = (labels > 0) & interior
    unclassified = interior & (labels == 0)
    print(f"\n  Classified: {classified.sum():>12,} px "
          f"({100*classified.sum()/interior.sum():.1f}%)")
    print(f"  Unclassified: {unclassified.sum():>12,} px "
          f"({100*unclassified.sum()/interior.sum():.1f}%)")

    return labels
```

**Tips for defining HSV profiles:**
- Sample pixels from each zone using a crop: `hsv_crop = hsv[y1:y2, x1:x2]`
- Check the distribution: `np.percentile(hsv_crop[:,:,0][mask], [5, 25, 50, 75, 95])`
- Classify more-restrictive zones first (e.g., light blue before dark blue by saturation)
- Add an "other/background" catch-all for white, grey, or uncolored areas

### Approach B: K-Means Clustering

Best when colors are not known in advance or there are many similar shades.

```python
from sklearn.cluster import KMeans

def classify_by_kmeans(img_bgr, roi_mask, n_clusters, sample_size=50000):
    """Classify pixels using K-Means clustering in HSV space.

    Args:
        img_bgr: input image (BGR)
        roi_mask: boolean mask of the mappable area
        n_clusters: number of color clusters to find
        sample_size: number of pixels to sample for fitting

    Returns:
        labels: uint8 array with cluster labels (1-indexed)
        cluster_centers: HSV values of each cluster center
    """
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    interior_pixels = hsv[roi_mask]

    # Sample for speed
    n_pixels = len(interior_pixels)
    if n_pixels > sample_size:
        idx = np.random.choice(n_pixels, sample_size, replace=False)
        samples = interior_pixels[idx].astype(float)
    else:
        samples = interior_pixels.astype(float)

    # Fit K-Means
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    kmeans.fit(samples)

    # Predict all interior pixels
    all_predictions = kmeans.predict(interior_pixels.astype(float))

    # Build label array (1-indexed to reserve 0 for background)
    h, w = img_bgr.shape[:2]
    labels = np.zeros((h, w), dtype=np.uint8)
    labels[roi_mask] = all_predictions + 1

    # Report cluster centers
    centers = kmeans.cluster_centers_
    print("  Cluster centers (H, S, V):")
    for i, center in enumerate(centers):
        count = (all_predictions == i).sum()
        pct = 100 * count / len(all_predictions)
        print(f"    Cluster {i+1}: H={center[0]:.0f} S={center[1]:.0f} "
              f"V={center[2]:.0f}  ({count:,} px, {pct:.1f}%)")

    return labels, centers
```

After K-Means: show the user a swatch of each cluster center and ask them to name each one. Then remap cluster labels to meaningful zone labels.

---

## Morphological Cleanup

After classification, clean up noise from line remnants, anti-aliasing, and misclassified pixels.

```python
from scipy.ndimage import label as scipy_label

def morphological_cleanup(labels, roi_mask, zone_labels, min_speck_px=200,
                          close_kernel_size=9, nn_kernel_size=5, max_nn_iterations=50):
    """Clean up per-zone masks: close gaps, remove specks, fill unclassified.

    Args:
        labels: uint8 array of zone labels
        roi_mask: boolean mask of the mappable area
        zone_labels: dict of {label_value: zone_name}
        min_speck_px: remove isolated regions smaller than this
        close_kernel_size: morphological close kernel diameter
        nn_kernel_size: nearest-neighbor dilation kernel diameter
        max_nn_iterations: max iterations for nearest-neighbor fill

    Returns:
        cleaned labels array
    """
    h, w = labels.shape
    interior = roi_mask.astype(bool)
    cleaned = labels.copy()

    kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                                              (close_kernel_size, close_kernel_size))

    # 1. Per-zone morphological close (bridges boundary-line gaps)
    for lbl_val, zone_name in zone_labels.items():
        mask = (cleaned == lbl_val).astype(np.uint8)
        before = mask.sum()
        closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel_close)
        new_pixels = (closed > 0) & (cleaned == 0) & interior
        cleaned[new_pixels] = lbl_val
        gained = (cleaned == lbl_val).sum() - before
        if gained > 0:
            print(f"  {zone_name}: +{gained:,} px from close")

    # 2. Remove tiny speck regions
    for lbl_val, zone_name in zone_labels.items():
        mask = (cleaned == lbl_val).astype(np.uint8)
        labeled_regions, n_regions = scipy_label(mask)
        removed = 0
        for r in range(1, n_regions + 1):
            region = (labeled_regions == r)
            if region.sum() < min_speck_px:
                cleaned[region] = 0
                removed += region.sum()
        if removed > 0:
            print(f"  {zone_name}: removed {removed:,} speck px")

    # 3. Assign remaining unclassified interior pixels by nearest-neighbor
    remaining = interior & (cleaned == 0)
    if remaining.sum() > 0:
        print(f"\n  Filling {remaining.sum():,} unclassified pixels by nearest-neighbor...")
        kernel_nn = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                                               (nn_kernel_size, nn_kernel_size))
        for iteration in range(max_nn_iterations):
            if remaining.sum() == 0:
                break
            claims = np.zeros((h, w), dtype=np.uint8)
            for lbl_val in zone_labels:
                mask = (cleaned == lbl_val).astype(np.uint8)
                dilated = cv2.dilate(mask, kernel_nn, iterations=1)
                claim = (dilated > 0) & remaining
                claims[claim] = lbl_val
            newly_assigned = claims > 0
            cleaned[newly_assigned] = claims[newly_assigned]
            remaining = interior & (cleaned == 0)

        still_remaining = remaining.sum()
        if still_remaining > 0:
            print(f"  Still unclassified: {still_remaining:,} px")

    return cleaned
```

---

## Region-of-Interest Mask

Build a binary mask isolating the map area from margins, legends, and title blocks.

```python
from scipy.ndimage import binary_fill_holes

def build_roi_mask(img_bgr, saturation_floor=25):
    """Build a region-of-interest mask from colored pixel detection.

    Finds the largest contiguous colored region (the map), fills holes,
    and smooths the boundary.

    Args:
        img_bgr: input image (BGR)
        saturation_floor: minimum saturation to count as "colored"

    Returns:
        boolean mask (h, w) where True = map interior
    """
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    colored = hsv[:, :, 1] > saturation_floor

    # Find largest connected component
    labeled, n_features = scipy_label(colored.astype(np.uint8))
    sizes = {i: (labeled == i).sum() for i in range(1, n_features + 1)}
    if not sizes:
        print("  WARNING: No colored regions found. Using full image.")
        return np.ones(img_bgr.shape[:2], dtype=bool)

    largest_id = max(sizes, key=sizes.get)
    map_mask = (labeled == largest_id)

    # Fill holes
    map_mask = binary_fill_holes(map_mask)

    # Morphological close to bridge thin gaps
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
    map_mask = cv2.morphologyEx(
        map_mask.astype(np.uint8), cv2.MORPH_CLOSE, kernel
    ).astype(bool)

    # Final hole fill
    map_mask = binary_fill_holes(map_mask)

    pct = 100 * map_mask.sum() / map_mask.size
    print(f"  ROI mask: {map_mask.sum():,} pixels ({pct:.1f}% of image)")

    return map_mask
```

---

## HSV Color Exploration

Helper to explore the color distribution before defining zone profiles.

```python
def explore_colors(img_bgr, roi_mask, n_samples=10000):
    """Show HSV distribution of map pixels to help define zone profiles.

    Displays percentiles and a scatter plot of H vs S for interior pixels.
    """
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    pixels = hsv[roi_mask]

    # Sample for visualization speed
    if len(pixels) > n_samples:
        idx = np.random.choice(len(pixels), n_samples, replace=False)
        sample = pixels[idx]
    else:
        sample = pixels

    print("HSV percentiles of interior pixels:")
    for ch, name in enumerate(["Hue", "Saturation", "Value"]):
        vals = pixels[:, ch]
        p5, p25, p50, p75, p95 = np.percentile(vals, [5, 25, 50, 75, 95])
        print(f"  {name:12s}: p5={p5:.0f} p25={p25:.0f} p50={p50:.0f} "
              f"p75={p75:.0f} p95={p95:.0f}")

    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    # H vs S scatter
    ax = axes[0]
    ax.scatter(sample[:, 0], sample[:, 1], c=cv2.cvtColor(
        sample.reshape(1, -1, 3), cv2.COLOR_HSV2RGB
    ).reshape(-1, 3) / 255, s=1, alpha=0.3)
    ax.set_xlabel("Hue (0-180)")
    ax.set_ylabel("Saturation (0-255)")
    ax.set_title("H vs S")

    # S vs V scatter
    ax = axes[1]
    ax.scatter(sample[:, 1], sample[:, 2], c=cv2.cvtColor(
        sample.reshape(1, -1, 3), cv2.COLOR_HSV2RGB
    ).reshape(-1, 3) / 255, s=1, alpha=0.3)
    ax.set_xlabel("Saturation")
    ax.set_ylabel("Value")
    ax.set_title("S vs V")

    # Hue histogram
    ax = axes[2]
    high_sat = pixels[pixels[:, 1] > 50]  # only colored pixels
    if len(high_sat) > 0:
        ax.hist(high_sat[:, 0], bins=180, range=(0, 180),
                edgecolor="none", alpha=0.8)
    ax.set_xlabel("Hue (0-180)")
    ax.set_ylabel("Pixel count")
    ax.set_title("Hue Distribution (S > 50)")

    fig.tight_layout()
    return fig
```

This exploration step is critical for building accurate zone profiles. Run it before defining HSV thresholds, and show the results to the user for confirmation.
