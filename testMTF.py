"""
ISO 12233 Live Camera Calibration Monitor
即時相機校正監測工具

Metrics:
  - MTF50 (Sharpness) via slanted edge analysis
  - Distortion coefficient via edge line detection
  - Exposure/Contrast via grayscale wedge analysis

Usage:
    python iso_live_monitor.py [--camera 0] [--width 1920] [--height 1080]

Dependencies:
    pip install opencv-python numpy scipy
"""

import cv2
import numpy as np
import argparse
import time
from collections import deque
from scipy.optimize import curve_fit
from scipy.interpolate import interp1d


# ── CONFIG ──────────────────────────────────────────────────────────────────
HISTORY_LEN   = 30          # rolling average window
UPDATE_EVERY  = 10          # frames between metric recalculation
PANEL_W       = 420         # right-panel width (px)
FONT          = cv2.FONT_HERSHEY_SIMPLEX


# ── COLOUR PALETTE ──────────────────────────────────────────────────────────
C = {
    "bg":       (18,  18,  18),
    "panel":    (28,  28,  35),
    "border":   (60,  60,  80),
    "accent":   (0,  200, 255),    # cyan
    "good":     (80, 220, 100),
    "warn":     (220,190,  50),
    "bad":      (80,  80, 230),    # BGR red
    "text":     (220,220,220),
    "dim":      (120,120,120),
    "mtf":      (0,  200, 255),
    "dist":     (80, 180, 255),
    "exp":      (80, 220, 160),
}


# ════════════════════════════════════════════════════════════════════════════
#  METRIC: MTF50 via slanted-edge ESF
# ════════════════════════════════════════════════════════════════════════════
def compute_mtf50(gray: np.ndarray) -> float | None:
    """
    Find the sharpest slanted edge in the frame and estimate MTF50.
    Returns MTF50 in cycles/pixel, or None if no edge found.
    """
    h, w = gray.shape

    # Canny to find edges
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges   = cv2.Canny(blurred, 50, 150)

    # Hough lines → find a near-vertical or near-horizontal slanted edge
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=60,
                             minLineLength=80, maxLineGap=10)
    if lines is None:
        return None

    best_line = None
    best_len  = 0
    for l in lines:
        x1, y1, x2, y2 = l[0]
        angle = abs(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
        # Accept lines 3–20° off-axis (slanted edge requirement)
        off = min(angle, abs(angle - 90), abs(angle - 180))
        if 3 < off < 20:
            length = np.hypot(x2 - x1, y2 - y1)
            if length > best_len:
                best_len  = length
                best_line = l[0]

    if best_line is None:
        return None

    x1, y1, x2, y2 = best_line
    # Extract a 32-pixel-wide ROI around the line (horizontal edge preferred)
    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
    roi_h, roi_w = 64, min(int(best_len * 0.8), w // 3)
    rx = max(0, cx - roi_w // 2);  ry = max(0, cy - roi_h // 2)
    rx2 = min(w, rx + roi_w);      ry2 = min(h, ry + roi_h)
    roi = gray[ry:ry2, rx:rx2].astype(np.float64)
    if roi.size == 0:
        return None

    # Collapse to 1-D ESF (edge spread function) along short axis
    esf = np.mean(roi, axis=0)
    if len(esf) < 16:
        return None

    # Differentiate → LSF
    lsf = np.diff(esf)
    lsf -= lsf.mean()

    # Window + FFT → MTF
    win = np.hanning(len(lsf))
    lsf_w = lsf * win
    mtf = np.abs(np.fft.rfft(lsf_w))
    mtf /= mtf[0] if mtf[0] != 0 else 1.0

    freqs = np.fft.rfftfreq(len(lsf_w))   # cycles/pixel

    # Find MTF50 by interpolation
    try:
        f_interp = interp1d(freqs, mtf, kind='linear')
        test_f   = np.linspace(freqs[0], freqs[-1], 1000)
        test_m   = f_interp(test_f)
        idx50    = np.where(test_m <= 0.5)[0]
        if len(idx50) == 0:
            return None
        return float(test_f[idx50[0]])
    except Exception:
        return None


# ════════════════════════════════════════════════════════════════════════════
#  METRIC: Distortion coefficient
# ════════════════════════════════════════════════════════════════════════════
def compute_distortion(gray: np.ndarray) -> float | None:
    """
    Detect the outer border rectangle of the ISO chart and measure
    how much the sides bow (barrel < 0 < pincushion).
    Returns distortion % or None.
    """
    h, w = gray.shape
    blur  = cv2.GaussianBlur(gray, (7, 7), 0)
    edges = cv2.Canny(blur, 30, 100)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    # Find largest contour that looks like a rectangle
    best_area = 0
    best_rect = None
    for c in contours:
        area = cv2.contourArea(c)
        if area < (h * w * 0.05):
            continue
        peri  = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        if len(approx) == 4 and area > best_area:
            best_area = area
            best_rect = approx

    if best_rect is None:
        return None

    pts = best_rect.reshape(4, 2).astype(np.float32)
    pts = pts[np.argsort(pts[:, 1])]          # sort by y

    top_pts    = pts[:2][np.argsort(pts[:2, 0])]   # TL, TR
    bottom_pts = pts[2:][np.argsort(pts[2:, 0])]   # BL, BR

    tl, tr = top_pts
    bl, br = bottom_pts

    # Sample mid-point of top edge from the actual edge image
    top_mid_x = int((tl[0] + tr[0]) / 2)
    top_mid_y = int((tl[1] + tr[1]) / 2)
    straight_top_y = top_mid_y

    # Sample actual edge position along top line
    search_col = np.clip(top_mid_x, 5, w - 5)
    col_slice  = edges[max(0, top_mid_y - 20):min(h, top_mid_y + 20), search_col]
    edge_rows  = np.where(col_slice > 0)[0]
    if len(edge_rows) == 0:
        return None
    actual_y = max(0, top_mid_y - 20) + edge_rows[0]

    # Distortion = deviation of mid-edge vs straight line / image height
    deviation = straight_top_y - actual_y   # +ve = bowing outward (barrel)
    distortion_pct = (deviation / h) * 100.0
    return float(distortion_pct)


# ════════════════════════════════════════════════════════════════════════════
#  METRIC: Exposure / Contrast from grayscale wedge
# ════════════════════════════════════════════════════════════════════════════
def compute_exposure(gray: np.ndarray) -> dict:
    """
    Analyse the top grayscale wedge region (top-centre of ISO chart).
    Returns mean brightness, std, min, max, dynamic range.
    """
    h, w = gray.shape
    # Top-centre wedge: roughly 20–45% from top, 25–75% from left
    ry1, ry2 = int(h * 0.05), int(h * 0.22)
    rx1, rx2 = int(w * 0.28), int(w * 0.72)
    wedge = gray[ry1:ry2, rx1:rx2]

    if wedge.size == 0:
        return {}

    mean_val = float(np.mean(wedge))
    std_val  = float(np.std(wedge))
    min_val  = float(np.min(wedge))
    max_val  = float(np.max(wedge))
    dr       = max_val - min_val

    # Split wedge into 8 horizontal strips → step levels
    strip_w = wedge.shape[1] // 8
    levels  = []
    for i in range(8):
        s = wedge[:, i * strip_w:(i + 1) * strip_w]
        levels.append(float(np.mean(s)))

    return {
        "mean":   mean_val,
        "std":    std_val,
        "min":    min_val,
        "max":    max_val,
        "dr":     dr,
        "levels": levels,
    }


# ════════════════════════════════════════════════════════════════════════════
#  DRAWING HELPERS
# ════════════════════════════════════════════════════════════════════════════
def draw_panel(canvas: np.ndarray, x: int, y: int, w: int, h: int, label: str):
    cv2.rectangle(canvas, (x, y), (x + w, y + h), C["panel"], -1)
    cv2.rectangle(canvas, (x, y), (x + w, y + h), C["border"], 1)
    cv2.putText(canvas, label, (x + 10, y + 20), FONT, 0.45, C["accent"], 1, cv2.LINE_AA)


def draw_bar(canvas, x, y, w, h, value, vmin, vmax, color, bg=(40,40,50)):
    cv2.rectangle(canvas, (x, y), (x + w, y + h), bg, -1)
    frac = np.clip((value - vmin) / (vmax - vmin + 1e-9), 0, 1)
    bw   = int(w * frac)
    if bw > 0:
        cv2.rectangle(canvas, (x, y), (x + bw, y + h), color, -1)
    cv2.rectangle(canvas, (x, y), (x + w, y + h), C["border"], 1)


def rating_color(value, good_min, good_max):
    if good_min <= value <= good_max:
        return C["good"]
    elif abs(value - (good_min + good_max) / 2) < (good_max - good_min):
        return C["warn"]
    return C["bad"]


def put_text_right(canvas, text, x_right, y, scale, color, thickness=1):
    (tw, th), _ = cv2.getTextSize(text, FONT, scale, thickness)
    cv2.putText(canvas, text, (x_right - tw, y), FONT, scale, color, thickness, cv2.LINE_AA)


# ════════════════════════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════════════════════════
def main(camera_id: int, cap_w: int, cap_h: int):
    cap = cv2.VideoCapture(camera_id)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  cap_w)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cap_h)

    if not cap.isOpened():
        print(f"Cannot open camera {camera_id}")
        return

    # Rolling histories
    mtf_hist  = deque(maxlen=HISTORY_LEN)
    dist_hist = deque(maxlen=HISTORY_LEN)
    exp_hist  = deque(maxlen=HISTORY_LEN)

    frame_count = 0
    fps_timer   = time.time()
    fps_val     = 0.0

    # Cached metric values
    mtf_val  = None
    dist_val = None
    exp_data = {}

    print("ISO 12233 Live Monitor — press Q to quit")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Frame read failed, retrying...")
            time.sleep(0.05)
            continue
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # ── Metric update (not every frame for performance) ──
        if frame_count % UPDATE_EVERY == 0:
            h_g, w_g = gray.shape
            rois = {
                "Center": (h_g//3, 2*h_g//3, w_g//3, 2*w_g//3),
                "TL": (0, h_g//3, 0, w_g//3),
                "TR": (0, h_g//3, 2*w_g//3, w_g),
                "BL": (2*h_g//3, h_g, 0, w_g//3),
                "BR": (2*h_g//3, h_g, 2*w_g//3, w_g)
            }
            mtf_curr = {}
            for name, (ry1, ry2, rx1, rx2) in rois.items():
                roi_gray = gray[ry1:ry2, rx1:rx2]
                val = compute_mtf50(roi_gray)
                if val is not None:
                    mtf_curr[name] = val
                    
            if mtf_curr:
                mtf_hist.append(mtf_curr)

            dist_val = compute_distortion(gray)
            exp_data = compute_exposure(gray)

            if dist_val is not None: dist_hist.append(dist_val)
            if "mean" in exp_data:   exp_hist.append(exp_data["mean"])

        # ── FPS ──
        frame_count += 1
        if frame_count % 15 == 0:
            now = time.time()
            fps_val   = 15 / max(now - fps_timer, 1e-6)
            fps_timer = now

        # ────────────────────────────────────────────────────────────────
        # BUILD OUTPUT CANVAS
        # ────────────────────────────────────────────────────────────────
        fh, fw = frame.shape[:2]
        total_w = fw + PANEL_W
        canvas  = np.full((fh, total_w, 3), C["bg"], dtype=np.uint8)

        # ── Left: camera feed ──
        canvas[:fh, :fw] = frame

        # Overlay FPS on video
        cv2.putText(canvas, f"FPS {fps_val:.1f}", (10, fh - 12),
                    FONT, 0.5, C["dim"], 1, cv2.LINE_AA)

        # Draw 3x3 grid to indicate the 5 ROIs (Center + 4 Corners)
        cv2.line(canvas, (fw//3, 0), (fw//3, fh), (80,80,80), 1)
        cv2.line(canvas, (2*fw//3, 0), (2*fw//3, fh), (80,80,80), 1)
        cv2.line(canvas, (0, fh//3), (fw, fh//3), (80,80,80), 1)
        cv2.line(canvas, (0, 2*fh//3), (fw, 2*fh//3), (80,80,80), 1)

        # ── Right panel background ──
        px = fw   # panel x offset
        cv2.rectangle(canvas, (px, 0), (total_w, fh), C["bg"], -1)

        # Title
        cv2.putText(canvas, "ISO 12233", (px + 12, 30),
                    FONT, 0.75, C["accent"], 2, cv2.LINE_AA)
        cv2.putText(canvas, "LIVE CALIBRATION", (px + 12, 50),
                    FONT, 0.38, C["dim"], 1, cv2.LINE_AA)
        cv2.line(canvas, (px + 8, 58), (total_w - 8, 58), C["border"], 1)

        y_cursor = 72
        PW = PANEL_W - 16   # inner panel width

        # ════════════════════════════════
        #  MTF50 PANEL
        # ════════════════════════════════
        draw_panel(canvas, px + 8, y_cursor, PW, 190, "MTF50  (5 ROIs)")

        if mtf_hist:
            avg_mtf = {}
            for key in ["Center", "TL", "TR", "BL", "BR"]:
                vals = [m[key] for m in mtf_hist if key in m]
                if vals:
                    avg_mtf[key] = np.mean(vals)
            
            if "Center" in avg_mtf:
                center_lp = avg_mtf["Center"] * fh
                col = rating_color(center_lp, fh * 0.1, fh * 0.4)
                cv2.putText(canvas, f"Center: {center_lp:.0f} lp/ph", (px + 18, y_cursor + 45), FONT, 0.7, col, 2, cv2.LINE_AA)
                cv2.putText(canvas, f"({avg_mtf['Center']:.3f} cy/px)", (px + 220, y_cursor + 45), FONT, 0.4, C["dim"], 1)
            else:
                cv2.putText(canvas, "Center: Detecting...", (px + 18, y_cursor + 45), FONT, 0.6, C["warn"], 1)

            c_y = y_cursor + 80
            corner_lps = []
            for i, key in enumerate(["TL", "TR", "BL", "BR"]):
                col_offset = (i % 2) * 160
                row_offset = (i // 2) * 25
                if key in avg_mtf:
                    val = avg_mtf[key] * fh
                    corner_lps.append(val)
                    cv2.putText(canvas, f"{key}: {val:.0f}", (px + 18 + col_offset, c_y + row_offset), FONT, 0.5, C["text"], 1)
                else:
                    cv2.putText(canvas, f"{key}: --", (px + 18 + col_offset, c_y + row_offset), FONT, 0.5, C["dim"], 1)

            if "Center" in avg_mtf and corner_lps:
                center_lp = avg_mtf["Center"] * fh
                corner_avg = np.mean(corner_lps)
                ratio = (corner_avg / center_lp) * 100 if center_lp > 0 else 0
                r_col = C["good"] if ratio >= 80 else C["bad"]
                cv2.putText(canvas, f"Corner/Center Ratio: {ratio:.1f}%", (px + 18, c_y + 60), FONT, 0.5, r_col, 1)

            if len(corner_lps) == 4:
                std_dev = np.std(corner_lps)
                s_col = C["good"] if std_dev < 50 else C["warn"]
                cv2.putText(canvas, f"Tilt (Corners StdDev): {std_dev:.1f}", (px + 18, c_y + 85), FONT, 0.5, s_col, 1)

        else:
            cv2.putText(canvas, "Detecting edges in ROIs...", (px + 18, y_cursor + 60),
                        FONT, 0.45, C["dim"], 1, cv2.LINE_AA)

        y_cursor += 200

        # ════════════════════════════════
        #  DISTORTION PANEL
        # ════════════════════════════════
        draw_panel(canvas, px + 8, y_cursor, PW, 110, "Distortion")

        dist_avg = np.mean(dist_hist) if dist_hist else None
        if dist_avg is not None:
            col  = rating_color(abs(dist_avg), 0, 0.5)
            sign = "+" if dist_avg > 0 else ""
            label = "Barrel" if dist_avg < -0.1 else ("Pincushion" if dist_avg > 0.1 else "Flat")

            cv2.putText(canvas, f"{sign}{dist_avg:.2f}%", (px + 18, y_cursor + 60),
                        FONT, 1.2, col, 2, cv2.LINE_AA)
            cv2.putText(canvas, label, (px + 18, y_cursor + 80),
                        FONT, 0.45, C["dim"], 1, cv2.LINE_AA)

            # Centre bar (0 = centre, barrel left, pincushion right)
            bx = px + 18;  bw = PW - 20;  bh = 10
            cy_bar = y_cursor + 92
            cv2.rectangle(canvas, (bx, cy_bar), (bx + bw, cy_bar + bh), (40,40,50), -1)
            mid = bx + bw // 2
            cv2.line(canvas, (mid, cy_bar), (mid, cy_bar + bh), C["border"], 1)
            frac = np.clip((dist_avg + 2) / 4, 0, 1)
            bar_x = int(bx + frac * bw)
            cv2.circle(canvas, (bar_x, cy_bar + bh // 2), 5, col, -1)
            cv2.rectangle(canvas, (bx, cy_bar), (bx + bw, cy_bar + bh), C["border"], 1)
            cv2.putText(canvas, "Barrel", (bx, cy_bar + bh + 12), FONT, 0.32, C["dim"], 1)
            put_text_right(canvas, "Pincushion", bx + bw, cy_bar + bh + 12, 0.32, C["dim"])
        else:
            cv2.putText(canvas, "Detecting border...", (px + 18, y_cursor + 60),
                        FONT, 0.45, C["dim"], 1, cv2.LINE_AA)

        y_cursor += 120

        # ════════════════════════════════
        #  EXPOSURE / CONTRAST PANEL
        # ════════════════════════════════
        draw_panel(canvas, px + 8, y_cursor, PW, 160, "Exposure / Contrast")

        if exp_data:
            mean_v = exp_data["mean"]
            dr_v   = exp_data["dr"]
            std_v  = exp_data["std"]

            # Mean brightness bar
            col_exp = rating_color(mean_v, 90, 165)
            cv2.putText(canvas, "Mean", (px + 18, y_cursor + 42), FONT, 0.38, C["dim"], 1)
            draw_bar(canvas, px + 60, y_cursor + 30, PW - 80, 14,
                     mean_v, 0, 255, col_exp)
            cv2.putText(canvas, f"{mean_v:.0f}", (px + PW - 38, y_cursor + 42),
                        FONT, 0.38, col_exp, 1)

            # Dynamic range bar
            col_dr = rating_color(dr_v, 100, 220)
            cv2.putText(canvas, "DR  ", (px + 18, y_cursor + 65), FONT, 0.38, C["dim"], 1)
            draw_bar(canvas, px + 60, y_cursor + 53, PW - 80, 14,
                     dr_v, 0, 255, col_dr)
            cv2.putText(canvas, f"{dr_v:.0f}", (px + PW - 38, y_cursor + 65),
                        FONT, 0.38, col_dr, 1)

            # Std dev
            cv2.putText(canvas, f"Std {std_v:.1f}", (px + 18, y_cursor + 85),
                        FONT, 0.38, C["dim"], 1)

            # 8-step wedge strip
            if "levels" in exp_data and len(exp_data["levels"]) == 8:
                strip_y  = y_cursor + 98
                strip_h  = 28
                strip_x  = px + 18
                sw       = (PW - 20) // 8
                for i, lv in enumerate(exp_data["levels"]):
                    v = int(np.clip(lv, 0, 255))
                    cv2.rectangle(canvas,
                                  (strip_x + i * sw, strip_y),
                                  (strip_x + (i + 1) * sw, strip_y + strip_h),
                                  (v, v, v), -1)
                cv2.rectangle(canvas,
                               (strip_x, strip_y),
                               (strip_x + sw * 8, strip_y + strip_h),
                               C["border"], 1)
                cv2.putText(canvas, "Wedge reconstruction",
                            (strip_x, strip_y + strip_h + 14),
                            FONT, 0.32, C["dim"], 1)
        else:
            cv2.putText(canvas, "Detecting wedge...", (px + 18, y_cursor + 60),
                        FONT, 0.45, C["dim"], 1, cv2.LINE_AA)

        y_cursor += 170

        # ════════════════════════════════
        #  STATUS / LEGEND
        # ════════════════════════════════
        cv2.line(canvas, (px + 8, y_cursor), (total_w - 8, y_cursor), C["border"], 1)
        y_cursor += 14
        for label, col in [("■ Good", C["good"]), ("■ Warn", C["warn"]), ("■ Out", C["bad"])]:
            cv2.putText(canvas, label, (px + 12, y_cursor), FONT, 0.35, col, 1)
            px += 90 if label != "■ Out" else 0
        px = fw  # reset

        y_cursor += 18
        cv2.putText(canvas, f"Update every {UPDATE_EVERY} frames",
                    (fw + 12, y_cursor), FONT, 0.32, C["dim"], 1)
        y_cursor += 14
        cv2.putText(canvas, "Q — quit",
                    (fw + 12, y_cursor), FONT, 0.32, C["dim"], 1)

        cv2.imshow("ISO 12233 Live Calibration Monitor", canvas)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == 27:
            break

    cap.release()
    cv2.destroyAllWindows()
    print("Monitor closed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ISO 12233 Live Calibration Monitor")
    parser.add_argument("--camera", type=int,   default=0,    help="Camera index (default: 0)")
    parser.add_argument("--width",  type=int,   default=1920, help="Capture width")
    parser.add_argument("--height", type=int,   default=1080, help="Capture height")
    args = parser.parse_args()
    main(args.camera, args.width, args.height)