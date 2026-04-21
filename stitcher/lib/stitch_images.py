
import cv2
import numpy as np
import os

try:
    from stitch_file_utils import load_images_for_stitching_process
    from stitch_layout_manager import (
        resize_tablet_views_for_layout,
        calculate_stitching_layout,
        get_layout_bounding_box
    )
    from stitch_enhancement_utils import (
        add_logo_to_image_array,
        crop_canvas_to_content_with_margin
    )
    from stitch_output import save_stitched_output
    from stitch_config import (
        STITCH_VIEW_PATTERNS_BASE,
        STITCH_BACKGROUND_COLOR,
        STITCH_FINAL_MARGIN_PX,
        STITCH_VIEW_GAP_PX,
        STITCH_RULER_PADDING_PX,
        STITCH_OUTPUT_DPI,
        STITCH_LOGO_MAX_WIDTH_FRACTION,
        STITCH_LOGO_PADDING_ABOVE,
        STITCH_LOGO_PADDING_BELOW,
        get_extended_intermediate_suffixes
    )
    from image_utils import paste_image_onto_canvas
    from extract_measurements import add_measurement_record
except ImportError as e:
    print(f"CRITICAL ERROR in stitch_images.py: Could not import local utils: {e}")
    raise

DEFAULT_BLEND_OVERLAP_PX = 50


def _blend_images_horizontally(base_image_segment, new_image_segment, overlap_px):
    """Blends the new_image_segment onto the right side of base_image_segment with a horizontal gradient."""
    if base_image_segment is None or new_image_segment is None:
        return new_image_segment if base_image_segment is None else base_image_segment
    if overlap_px <= 0:
        return np.concatenate((base_image_segment, new_image_segment), axis=1)

    h = min(base_image_segment.shape[0], new_image_segment.shape[0])
    base_w = base_image_segment.shape[1]
    new_w = new_image_segment.shape[1]

    if base_w < overlap_px or new_w < overlap_px:

        return np.concatenate((base_image_segment[:, :base_w - overlap_px if base_w > overlap_px else 0], new_image_segment), axis=1)

    base_segment_cropped = base_image_segment[:h, :]
    new_segment_cropped = new_image_segment[:h, :]

    base_overlap = base_segment_cropped[:, base_w - overlap_px:]
    new_overlap = new_segment_cropped[:, :overlap_px]

    alpha = np.linspace(0, 1, overlap_px)[np.newaxis, :, np.newaxis]

    blended_overlap = cv2.addWeighted(base_overlap.astype(
        np.float32), 1 - alpha, new_overlap.astype(np.float32), alpha, 0).astype(np.uint8)

    non_overlap_base = base_segment_cropped[:, :base_w - overlap_px]
    non_overlap_new = new_segment_cropped[:, overlap_px:]

    result = np.concatenate(
        (non_overlap_base, blended_overlap, non_overlap_new), axis=1)
    return result


def _blend_images_vertically(base_image_segment, new_image_segment, overlap_px):
    """Blends the new_image_segment onto the bottom side of base_image_segment with a vertical gradient."""
    if base_image_segment is None or new_image_segment is None:
        return new_image_segment if base_image_segment is None else base_image_segment
    if overlap_px <= 0:
        return np.concatenate((base_image_segment, new_image_segment), axis=0)

    w = min(base_image_segment.shape[1], new_image_segment.shape[1])
    base_h = base_image_segment.shape[0]
    new_h = new_image_segment.shape[0]

    if base_h < overlap_px or new_h < overlap_px:
        return np.concatenate((base_image_segment[:base_h - overlap_px if base_h > overlap_px else 0, :], new_image_segment), axis=0)

    base_segment_cropped = base_image_segment[:, :w]
    new_segment_cropped = new_image_segment[:, :w]

    base_overlap = base_segment_cropped[base_h - overlap_px:, :]
    new_overlap = new_segment_cropped[:overlap_px, :]

    alpha = np.linspace(0, 1, overlap_px)[:, np.newaxis, np.newaxis]

    blended_overlap = cv2.addWeighted(base_overlap.astype(
        np.float32), 1 - alpha, new_overlap.astype(np.float32), alpha, 0).astype(np.uint8)

    non_overlap_base = base_segment_cropped[:base_h - overlap_px, :]
    non_overlap_new = new_segment_cropped[overlap_px:, :]

    result = np.concatenate(
        (non_overlap_base, blended_overlap, non_overlap_new), axis=0)
    return result


def process_tablet_subfolder(
    subfolder_path,
    view_file_patterns_config,
    pixels_per_cm,
    ruler_position,
    main_input_folder_path,
    output_base_name,
    photographer_name,
    ruler_image_for_scale_path,
    add_logo=False,
    logo_path=None,
    object_extraction_background_mode="auto",
    stitched_bg_color=(0, 0, 0),
    custom_layout=None,
    include_intermediates=True,
    output_folder_suffix="",
    **kwargs
):
    """
    Process all images in a tablet subfolder to create a stitched composite.

    include_intermediates: when False, intermediate views (_ob, _ol, _or, _rl,
    _rr, _ot2, ...) are skipped — used for the "print" variant which only
    stitches the six primary views _01–_06.
    output_folder_suffix: appended to `_Final_TIFF` / `_Final_JPG` so print
    variants write to `_Final_TIFF_Print/` / `_Final_JPG_Print/`.
    """
    variant_label = " (print)" if output_folder_suffix else ""
    print(f"  Stitching for tablet: {output_base_name}{variant_label}")

    view_gap_px_override = kwargs.get('view_gap_px_override', None)
    current_view_gap = STITCH_VIEW_GAP_PX if view_gap_px_override is None else view_gap_px_override
    current_ruler_padding = STITCH_RULER_PADDING_PX

    loaded_images = load_images_for_stitching_process(
        subfolder_path,
        output_base_name,
        STITCH_VIEW_PATTERNS_BASE,
        include_intermediates=include_intermediates,
        intermediate_suffix_patterns=get_extended_intermediate_suffixes()
    )
    if not loaded_images or loaded_images.get("obverse") is None and (custom_layout is None or custom_layout.get("obverse") is None):
        print(
            f"Warning/Error: Stitching requires a primary image (e.g. 'obverse'). Loaded: {list(loaded_images.keys()) if loaded_images else 'None'}")
        if not loaded_images:
            raise ValueError("No images loaded for stitching, cannot proceed.")

    resized_images = resize_tablet_views_for_layout(loaded_images)

    if pixels_per_cm is not None and resized_images.get("obverse") is not None:
        object_suffix = "_object.tif"
        obverse_object_pattern = f"{output_base_name}_01{object_suffix}"

        obverse_object_files = [f for f in os.listdir(subfolder_path)
                                if f.startswith(obverse_object_pattern)]

        if obverse_object_files:
            obverse_object_path = os.path.join(subfolder_path, obverse_object_files[0])

            gap_pixels = 50

            # Check if measurement record already exists at the main-folder level
            # (that's where add_measurement_record writes and where the Excel
            # finalizer reads). Per-subfolder JSONs from older runs are ignored
            # on purpose — recomputing into the main file is cheap and keeps
            # the finalizer's input in sync.
            from extract_measurements import measurement_record_exists
            record_exists_main = measurement_record_exists(output_base_name, main_input_folder_path)

            if record_exists_main:
                print(f"  Measurement record already exists for {output_base_name} (skipping calculation)")
            else:
                success = add_measurement_record(
                    object_image_path=obverse_object_path,
                    pixels_per_cm=pixels_per_cm,
                    file_id=output_base_name,
                    gap_pixels=gap_pixels,
                    output_dir=main_input_folder_path
                )

                if success:
                    print(f"  Measurements calculated and saved for {output_base_name}")
                else:
                    print(f"  Failed to calculate measurements for {output_base_name}")
        else:
            print(
                f"  Warning: No obverse object file found for measurements ({obverse_object_pattern})")

    canvas_w, canvas_h, layout_coords, images_to_paste_dict = calculate_stitching_layout(
        resized_images, ruler_image_for_scale_path, logo_path, pixels_per_cm,
        view_file_patterns_config, gap_px=current_view_gap, ruler_padding_px=current_ruler_padding, 
        custom_layout=custom_layout
    )

    final_image = create_stitched_canvas(
        canvas_w, canvas_h,
        images_to_paste_dict,
        layout_coords,
        stitched_bg_color if stitched_bg_color is not None else STITCH_BACKGROUND_COLOR,
        custom_layout=custom_layout
    )

    if add_logo and logo_path:
        final_image = add_logo_to_image_array(
            final_image, logo_path, stitched_bg_color if stitched_bg_color is not None else STITCH_BACKGROUND_COLOR,
            STITCH_LOGO_MAX_WIDTH_FRACTION, STITCH_LOGO_PADDING_ABOVE, STITCH_LOGO_PADDING_BELOW
        )

    final_margin_to_use = kwargs.get('final_margin', STITCH_FINAL_MARGIN_PX)
    final_image = crop_canvas_to_content_with_margin(
        final_image, stitched_bg_color if stitched_bg_color is not None else STITCH_BACKGROUND_COLOR, final_margin_to_use)

    output_dpi = STITCH_OUTPUT_DPI
    if pixels_per_cm and pixels_per_cm > 0:
        output_dpi = int(pixels_per_cm * 2.54)

    # Load measurement record for metadata embedding
    obj_width_cm = None
    obj_length_cm = None
    try:
        from extract_measurements import get_measurement_record
        record = get_measurement_record(output_base_name, main_input_folder_path)
        if not record:
            record = get_measurement_record(output_base_name, subfolder_path)
        if record:
            obj_width_cm = record.get('width_cm')
            obj_length_cm = record.get('length_cm')
    except Exception:
        pass

    tiff_path, jpg_path = save_stitched_output(
        final_image,
        main_input_folder_path,
        output_base_name,
        photographer_name,
        output_dpi,
        object_width_cm=obj_width_cm,
        object_length_cm=obj_length_cm,
        pixels_per_cm=pixels_per_cm,
        output_folder_suffix=output_folder_suffix,
    )

    print(f"  Finished processing and stitching for tablet: {output_base_name}")
    return tiff_path, jpg_path


def create_stitched_canvas(canvas_width, canvas_height, images_dict, layout_coords, bg_color, custom_layout=None, blend_overlap_px=DEFAULT_BLEND_OVERLAP_PX, image_paths=None):
    """
    Create a blank canvas and place all images according to the calculated layout.
    Handles single images and sequences of intermediate images with gradient blending.
    Then crop to content bounds.

    If image_paths is provided, images are loaded lazily from disk instead of from images_dict,
    reducing peak memory usage.
    """

    canvas = np.full((canvas_height, canvas_width, 3), bg_color, dtype=np.uint8)

    processed_view_segments = {}

    for view_key, coords_tuple in layout_coords.items():
        # Lazy loading: load from disk if path available, otherwise use pre-loaded dict
        image_data = images_dict.get(view_key)
        if image_data is None and image_paths and view_key in image_paths:
            from stitch_file_utils import load_single_image
            image_data = load_single_image(image_paths[view_key])
        if image_data is None:
            continue

        start_x, start_y = coords_tuple[0], coords_tuple[1]

        if isinstance(image_data, list):
            current_segment = None
            blend_axis = 'horizontal'
            if "left" in view_key.lower() or "right" in view_key.lower():
                blend_axis = 'vertical'

            for i, img_in_sequence in enumerate(image_data):
                if img_in_sequence is None:
                    continue
                if i == 0:
                    current_segment = img_in_sequence
                else:
                    if blend_axis == 'horizontal':
                        current_segment = _blend_images_horizontally(
                            current_segment, img_in_sequence, blend_overlap_px)
                    else:
                        current_segment = _blend_images_vertically(
                            current_segment, img_in_sequence, blend_overlap_px)

            if current_segment is not None:
                paste_image_onto_canvas(canvas, current_segment, start_x, start_y)
                processed_view_segments[view_key] = (current_segment, start_x, start_y)

        else:
            img_to_paste = image_data
            paste_image_onto_canvas(canvas, img_to_paste, start_x, start_y)
            processed_view_segments[view_key] = (img_to_paste, start_x, start_y)

    min_x_coord, min_y_coord = canvas_width, canvas_height
    max_x_coord, max_y_coord = 0, 0

    if not processed_view_segments:
        return canvas

    for seg_img, seg_x, seg_y in processed_view_segments.values():
        min_x_coord = min(min_x_coord, seg_x)
        min_y_coord = min(min_y_coord, seg_y)
        max_x_coord = max(max_x_coord, seg_x + seg_img.shape[1])
        max_y_coord = max(max_y_coord, seg_y + seg_img.shape[0])

    min_x_coord = max(0, min_x_coord)
    min_y_coord = max(0, min_y_coord)
    max_x_coord = min(canvas_width, max_x_coord)
    max_y_coord = min(canvas_height, max_y_coord)

    if max_x_coord > min_x_coord and max_y_coord > min_y_coord:
        return canvas[min_y_coord:max_y_coord, min_x_coord:max_x_coord]

    return canvas


def stitch_images(loaded_image_dict, output_tiff_path, output_jpg_path,
                  photographer_name, ruler_position="bottom",
                  add_logo=False, logo_path=None, museum="British Museum"):
    """
    Main function to stitch tablet images together.
    """

    intermediate_positions = [
        "intermediate_obverse_top", "intermediate_obverse_bottom",
        "intermediate_obverse_left", "intermediate_obverse_right",
        "intermediate_reverse_top", "intermediate_reverse_bottom",
        "intermediate_reverse_left", "intermediate_reverse_right"
    ]

    def place_intermediate_images(canvas, loaded_images, main_positions, spacing, relationships):
        """
        Place intermediate images between main views with gradient blending

        Args:
            canvas: The main canvas where images are placed
            loaded_images: Dictionary of loaded images
            main_positions: Dictionary of main image positions (x, y, width, height)
            spacing: Spacing between views
            relationships: Dictionary mapping intermediate positions to related main views
        """

        for inter_pos, (main_view, side_view) in relationships.items():
            if inter_pos not in loaded_images or loaded_images[inter_pos] is None:
                continue

            if main_view not in main_positions or side_view not in main_positions:
                print(f"      Warning: Cannot place {inter_pos}, missing main views")
                continue

            inter_img = loaded_images[inter_pos]

            main_pos = main_positions[main_view]
            side_pos = main_positions[side_view]

            if "top" in inter_pos or "bottom" in inter_pos:

                mid_x = (main_pos[0] + main_pos[2] // 2
                         + side_pos[0] + side_pos[2] // 2) // 2

                if "top" in inter_pos:

                    mid_y = (main_pos[1] + side_pos[1] + side_pos[3]) // 2
                else:

                    mid_y = (main_pos[1] + main_pos[3] + side_pos[1]) // 2

                inter_width = min(main_pos[2], side_pos[2])
                inter_height = max(
                    spacing, inter_img.shape[0] * inter_width // inter_img.shape[1])
                resized_inter = cv2.resize(inter_img, (inter_width, inter_height))

                place_x = mid_x - inter_width // 2
                place_y = mid_y - inter_height // 2

            else:

                mid_y = (main_pos[1] + main_pos[3] // 2
                         + side_pos[1] + side_pos[3] // 2) // 2

                if "left" in inter_pos:

                    mid_x = (main_pos[0] + side_pos[0] + side_pos[2]) // 2
                else:

                    mid_x = (main_pos[0] + main_pos[2] + side_pos[0]) // 2

                inter_height = min(main_pos[3], side_pos[3])
                inter_width = max(
                    spacing, inter_img.shape[1] * inter_height // inter_img.shape[0])
                resized_inter = cv2.resize(inter_img, (inter_width, inter_height))

                place_x = mid_x - inter_width // 2
                place_y = mid_y - inter_height // 2

            mask = np.zeros(
                (resized_inter.shape[0], resized_inter.shape[1]), dtype=np.uint8)

            gradient_width_x = max(1, resized_inter.shape[1] // 4)
            gradient_width_y = max(1, resized_inter.shape[0] // 4)

            mask.fill(255)

            for x in range(gradient_width_x):
                opacity = int(255 * x / gradient_width_x)
                mask[:, x] = opacity
                mask[:, resized_inter.shape[1] - x - 1] = opacity

            for y in range(gradient_width_y):
                opacity = int(255 * y / gradient_width_y)
                mask[y, :] = np.minimum(mask[y, :], opacity)
                mask[resized_inter.shape[0] - y - 1,
                     :] = np.minimum(mask[resized_inter.shape[0] - y - 1, :], opacity)

            mask_3ch = cv2.merge([mask, mask, mask])

            place_x = max(0, min(place_x, canvas.shape[1] - resized_inter.shape[1]))
            place_y = max(0, min(place_y, canvas.shape[0] - resized_inter.shape[0]))

            blend_region = canvas[place_y:place_y + resized_inter.shape[0],
                                  place_x:place_x + resized_inter.shape[1]]

            if blend_region.shape[:2] != resized_inter.shape[:2]:
                print(
                    f"      Warning: Region size mismatch for {inter_pos}, adjusting...")

                h = min(blend_region.shape[0], resized_inter.shape[0])
                w = min(blend_region.shape[1], resized_inter.shape[1])
                blend_region = canvas[place_y:place_y + h, place_x:place_x + w]
                resized_inter = resized_inter[:h, :w]
                mask_3ch = mask_3ch[:h, :w]

            for c in range(3):
                blend_region[:, :, c] = (resized_inter[:, :, c] * mask_3ch[:, :, c] // 255
                                         + blend_region[:, :, c] * (255 - mask_3ch[:, :, c]) // 255)

            print(f"      Placed intermediate image: {inter_pos}")

        return canvas

    main_positions = {}

    if "obverse" in loaded_image_dict and loaded_image_dict["obverse"] is not None:
        main_positions["obverse"] = (obverse_x, obverse_y,
                                     loaded_image_dict["obverse"].shape[1],
                                     loaded_image_dict["obverse"].shape[0])

    if "reverse" in loaded_image_dict and loaded_image_dict["reverse"] is not None:
        main_positions["reverse"] = (reverse_x, reverse_y,
                                     loaded_image_dict["reverse"].shape[1],
                                     loaded_image_dict["reverse"].shape[0])

    if "top" in loaded_image_dict and loaded_image_dict["top"] is not None:
        main_positions["top"] = (top_x, top_y,
                                 loaded_image_dict["top"].shape[1],
                                 loaded_image_dict["top"].shape[0])

    if "bottom" in loaded_image_dict and loaded_image_dict["bottom"] is not None:
        main_positions["bottom"] = (bottom_x, bottom_y,
                                    loaded_image_dict["bottom"].shape[1],
                                    loaded_image_dict["bottom"].shape[0])

    if "left" in loaded_image_dict and loaded_image_dict["left"] is not None:
        main_positions["left"] = (left_x, left_y,
                                  loaded_image_dict["left"].shape[1],
                                  loaded_image_dict["left"].shape[0])

    if "right" in loaded_image_dict and loaded_image_dict["right"] is not None:
        main_positions["right"] = (right_x, right_y,
                                   loaded_image_dict["right"].shape[1],
                                   loaded_image_dict["right"].shape[0])

    print("      Placing intermediate images...")
    main_canvas = place_intermediate_images(
        main_canvas, loaded_image_dict, main_positions, view_gap_px, intermediate_relationships)


def create_composite_stitched_image(object_images, intermediate_images, ruler_image, logo_image=None):
    """
    Create a stitched composite of all object views including intermediates.

    Args:
        object_images: Dict of main view images
        intermediate_images: Dict of edge position -> ordered list of images  
        ruler_image: Image of the ruler
        logo_image: Optional logo to include

    Returns:
        PIL composite image
    """


def calculate_layout_with_intermediates(main_images, intermediates, ruler_img, logo_img=None):
    """
    Calculate the layout positions for all images including multiple intermediates.

    Args:
        main_images: Dict of main object views
        intermediates: Dict of edge position -> ordered list of intermediate images
        ruler_img: Scaled ruler image
        logo_img: Optional logo image

    Returns:
        Dict of image positions and composite canvas dimensions
    """

    dimensions = {}
    for view, img in main_images.items():
        if img:
            dimensions[view] = (img.width, img.height)

    for edge, img_list in intermediates.items():
        for i, img in enumerate(img_list):
            if img:
                dimensions[f"{edge}_{i+1}"] = (img.width, img.height)

    return positions, canvas_width, canvas_height
