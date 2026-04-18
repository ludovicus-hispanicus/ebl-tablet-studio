import cv2
import numpy as np


def get_detection_parameters(museum_selection="Iraq Museum"):
    base_params = {
        "hough_min_line_length": 30,
        "hough_max_line_gap": 10,
        "hough_threshold": 60,
        "tick_max_width": 20,
        "tick_min_width": 1,
        "tick_min_height": 20,
        "max_tick_thickness_px": 30,
        "min_ticks_required": 11,
        "num_ticks_for_1cm": 11,
        "consistency_threshold": 0.7,
        "canny_low_threshold": 10,
        "canny_high_threshold": 40,
        "roi_height_fraction": 0.55,
        "text_match_threshold": 0.6
    }
    if museum_selection == "Iraq Museum (Sippar Library)":
        base_params.update({
            "num_ticks_for_1cm": 11,
            "hough_threshold": 19,
            "hough_min_line_length": 13,
            "hough_max_line_gap": 50,
            "tick_max_width": 11,
            "tick_min_width": 2,
            "tick_min_height": 51,
            "max_tick_thickness_px": 39,
            "min_ticks_required": 11,
            "consistency_threshold": 0.87,
            "canny_low_threshold": 22,
            "canny_high_threshold": 122,
            "roi_height_fraction": 0.60,
            "text_match_threshold": 0.42
            })
    return base_params


def find_ruler_text_location(roi, params):
    if roi is None or roi.size == 0:
        return None

    if len(roi.shape) == 3:
        roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    else:
        roi_gray = roi

    template_height = 30
    template_width = 70
    font_scale = 0.7
    template = np.zeros((template_height, template_width), dtype=np.uint8)

    for text in ["1 cm", "0 cm"]:
        template.fill(0)
        text_size, _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 1)
        text_x = (template_width - text_size[0]) // 2
        text_y = (template_height + text_size[1]) // 2
        cv2.putText(template, text, (text_x, text_y),
                    cv2.FONT_HERSHEY_SIMPLEX, font_scale, 255, 1, cv2.LINE_AA)

        try:
            result = cv2.matchTemplate(roi_gray, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)

            if max_val > params['text_match_threshold']:
                center_x = max_loc[0] + template_width // 2
                center_y = max_loc[1] + template_height // 2
                return center_x, center_y, text
        except cv2.error:
            continue

    return None


def extract_roi_around_text(image, text_location, params):
    if text_location is None:
        height, width = image.shape[:2]
        roi_height = int(height * params['roi_height_fraction'])
        return image[height - roi_height:, :]

    text_x, text_y, _ = text_location
    height, width = image.shape[:2]

    roi_width = min(width // 2, 400)
    roi_height = min(height // 3, 200)

    x1 = max(0, text_x - roi_width // 2)
    x2 = min(width, x1 + roi_width)
    y1 = max(0, text_y - roi_height // 2)
    y2 = min(height, y1 + roi_height)

    return image[y1:y2, x1:x2]


def detect_1cm_distance_iraq(image_path, museum_selection="Iraq Museum", params=None):
    if params is None:
        params = get_detection_parameters(museum_selection)

    image = cv2.imread(image_path)
    if image is None:
        return None

    text_location = find_ruler_text_location(image, params)
    roi = extract_roi_around_text(image, text_location, params)

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, params['canny_low_threshold'],
                      params['canny_high_threshold'])

    lines = cv2.HoughLinesP(
        edges, 1, np.pi / 180,
        threshold=params['hough_threshold'],
        minLineLength=params['hough_min_line_length'],
        maxLineGap=params['hough_max_line_gap']
    )
    if lines is None:
        return None

    vertical_lines = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        line_width = abs(x2 - x1)
        line_height = abs(y2 - y1)

        if (line_width < params['tick_min_width']
            or line_width > params['tick_max_width']
                or line_height < params['tick_min_height']):
            continue

        angle = 90 if x2 - \
            x1 == 0 else abs(np.arctan((y2 - y1) / (x2 - x1)) * 180 / np.pi)
        if 80 <= angle <= 90:
            vertical_lines.append((x1 + x2) / 2.0)

    if len(vertical_lines) < 2:
        return None

    vertical_lines.sort()

    merged_lines = []
    i = 0
    while i < len(vertical_lines):
        group = [vertical_lines[i]]
        j = i + 1
        while (j < len(vertical_lines)
               and abs(vertical_lines[j] - vertical_lines[i]) < params['max_tick_thickness_px']):
            group.append(vertical_lines[j])
            j += 1
        merged_lines.append(np.mean(group))
        i = j

    if len(merged_lines) < params['min_ticks_required']:
        return None

    num_ticks = params['num_ticks_for_1cm']
    candidate_1cm_distances = []

    for i in range(len(merged_lines) - num_ticks + 1):
        segment = merged_lines[i:i + num_ticks]
        span = segment[-1] - segment[0]
        if span <= 0:
            continue

        spacings = np.diff(segment)
        median_spacing = np.median(spacings)
        if median_spacing <= 0:
            continue

        stddev = np.std(spacings)
        if stddev < median_spacing * params['consistency_threshold']:
            candidate_1cm_distances.append(span)

    return float(np.median(candidate_1cm_distances)) if candidate_1cm_distances else None
