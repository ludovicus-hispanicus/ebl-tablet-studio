import os
from workflow_imports import (
    ruler_detector, ruler_detector_iraq_museum, convert_raw_image_to_tiff,
    get_tablet_width_from_measurements, determine_pixels_per_cm_from_measurement,
    DEFAULT_BACKGROUND_DETECTION_COLOR_TOLERANCE
)


def try_ruler_detection_with_fallback(primary_image_path, subfolder_path_item, raw_ext_config,
                                      museum_selection, ruler_position):
    """
    Try ruler detection on primary image, with fallback to other images in the same folder.

    Returns:
        tuple: (px_cm_val, cr2_conv_count)
    """
    
    MIN_REASONABLE_PX_PER_CM = 100

    # Determine detection method: prefer active project, else legacy museum check
    use_iraq_detector = False
    try:
        import project_manager
        active = project_manager.get_active_project()
        if active is not None and active.get("name") == museum_selection:
            use_iraq_detector = (active.get("detection_method") == "iraq_museum")
        else:
            use_iraq_detector = museum_selection in ("Iraq Museum", "Iraq Museum (Sippar Library)")
    except Exception:
        use_iraq_detector = museum_selection in ("Iraq Museum", "Iraq Museum (Sippar Library)")

    if use_iraq_detector:
        def detector_func(img_path): return ruler_detector_iraq_museum.detect_1cm_distance_iraq(
            img_path, museum_selection=museum_selection)
        detector_name = "Iraq Museum"
    else:
        def detector_func(img_path): return ruler_detector.estimate_pixels_per_centimeter_from_ruler(
            img_path, ruler_position=ruler_position)
        detector_name = "general"

    print(
        f"   Using {detector_name} ruler detector for {os.path.basename(primary_image_path)}...")

    cr2_conv_count = 0

    curr_scale_fp, is_temp_file = primary_image_path, False

    if curr_scale_fp.lower().endswith(raw_ext_config):
        tmp_fp = os.path.join(
            subfolder_path_item,
            f"{os.path.splitext(os.path.basename(curr_scale_fp))[0]}_rawscale.tif"
        )
        convert_raw_image_to_tiff(curr_scale_fp, tmp_fp)
        curr_scale_fp, is_temp_file = tmp_fp, True
        cr2_conv_count += 1

    try:
        px_cm_val = detector_func(curr_scale_fp)
        if px_cm_val is not None and px_cm_val >= MIN_REASONABLE_PX_PER_CM:
            print(
                f"     {detector_name} ruler detector returned px/cm: {px_cm_val}")
            if is_temp_file and os.path.exists(curr_scale_fp):
                os.remove(curr_scale_fp)
            return px_cm_val, cr2_conv_count
        elif px_cm_val is not None and px_cm_val < MIN_REASONABLE_PX_PER_CM:
            print(
                f"   Primary image detection returned unreasonably low value: {px_cm_val} px/cm (minimum: {MIN_REASONABLE_PX_PER_CM})")
        else:
            print(
                f"   Primary image detection failed or returned invalid value: {px_cm_val}")
    except Exception as e:
        print(f"   Primary image detection failed with error: {e}")

    if is_temp_file and os.path.exists(curr_scale_fp):
        os.remove(curr_scale_fp)

    print(f"   Ruler detection failed for primary image, trying fallback images...")

    base_name = os.path.splitext(os.path.basename(primary_image_path))[0]

    suffixes_to_remove = ['_rawscale', '_01', '_02', '_03', '_04', '_05']
    for suffix in suffixes_to_remove:
        if base_name.endswith(suffix):
            base_name = base_name[:-len(suffix)]
            break

    print(f"   Looking for fallback images with base name: {base_name}")

    fallback_suffixes = ['_01', '_02', '_03', '_04', '_05']
    fallback_images = []

    for suffix in fallback_suffixes:
        for ext in ['.jpg', '.jpeg', '.tif', '.tiff', '.png', '.JPG', '.JPEG', '.TIF', '.TIFF', '.PNG']:
            fallback_path = os.path.join(
                subfolder_path_item, f"{base_name}{suffix}{ext}")
            if os.path.exists(fallback_path) and fallback_path != primary_image_path:
                fallback_images.append(fallback_path)
                print(
                    f"   Found fallback image: {os.path.basename(fallback_path)}")
                break

    if not fallback_images:
        print(f"   No fallback images found for base name: {base_name}")
        return None, cr2_conv_count

    for fallback_image in fallback_images:
        print(f"   Trying fallback image: {os.path.basename(fallback_image)}")

        fallback_curr_fp = fallback_image
        fallback_is_temp = False

        if fallback_curr_fp.lower().endswith(raw_ext_config):
            fallback_tmp_fp = os.path.join(
                subfolder_path_item,
                f"{os.path.splitext(os.path.basename(fallback_curr_fp))[0]}_rawscale.tif"
            )
            convert_raw_image_to_tiff(fallback_curr_fp, fallback_tmp_fp)
            fallback_curr_fp, fallback_is_temp = fallback_tmp_fp, True
            cr2_conv_count += 1

        try:
            px_cm_val = detector_func(fallback_curr_fp)

            if fallback_is_temp and os.path.exists(fallback_curr_fp):
                os.remove(fallback_curr_fp)

            if px_cm_val is not None and px_cm_val >= MIN_REASONABLE_PX_PER_CM:
                print(
                    f"   SUCCESS: Ruler detected in fallback image {os.path.basename(fallback_image)}")
                print(
                    f"     {detector_name} ruler detector returned px/cm: {px_cm_val}")
                return px_cm_val, cr2_conv_count
            elif px_cm_val is not None and px_cm_val < MIN_REASONABLE_PX_PER_CM:
                print(
                    f"   Fallback detection returned unreasonably low value for {os.path.basename(fallback_image)}: {px_cm_val} px/cm (minimum: {MIN_REASONABLE_PX_PER_CM})")
            else:
                print(
                    f"   Ruler detection failed for {os.path.basename(fallback_image)}")

        except Exception as e:
            print(
                f"   Error in fallback detection for {os.path.basename(fallback_image)}: {e}")

            if fallback_is_temp and os.path.exists(fallback_curr_fp):
                os.remove(fallback_curr_fp)

    print(f"   All fallback images failed for {detector_name} ruler detection")
    return None, cr2_conv_count


def detect_scale_from_ruler(ruler_for_scale_fp, subfolder_path_item, raw_ext_config,
                            museum_selection, ruler_position, progress_callback=None):
    """
    Detect scale from ruler image using appropriate detector with fallback support.

    Returns:
        tuple: (px_cm_val, cr2_conv_count)
    """

    px_cm_val, cr2_conv_count = try_ruler_detection_with_fallback(
        ruler_for_scale_fp, subfolder_path_item, raw_ext_config,
        museum_selection, ruler_position
    )

    if px_cm_val is None or px_cm_val <= 0:
        detector_name = "Iraq Museum" if museum_selection == "Iraq Museum" or museum_selection == "Iraq Museum (Sippar Library)" else "general"
        raise ValueError(
            f"{detector_name} ruler detection failed for primary image and all fallback images.")

    return px_cm_val, cr2_conv_count


def get_scale_from_measurements(subfolder_path_item, measurements_dict, ruler_for_scale_fp,
                                background_color_tolerance=None):
    """
    Get scale from measurements database (sippar.json) or Excel measurements.

    Returns:
        tuple: (px_cm_val, measurements_used)
    """
    if background_color_tolerance is None:
        background_color_tolerance = DEFAULT_BACKGROUND_DETECTION_COLOR_TOLERANCE

    tablet_width_cm = get_tablet_width_from_measurements(
        subfolder_path_item, measurements_dict)
    if tablet_width_cm is None or tablet_width_cm <= 0:
        return None, False

    # Check if this is Excel measurements (has '_id' field) vs sippar.json
    from measurements_utils import extract_tablet_id_from_path
    tablet_id = extract_tablet_id_from_path(subfolder_path_item)
    
    # Check if this measurement comes from Excel (custom measurements)
    is_excel_measurement = False
    if tablet_id and tablet_id in measurements_dict:
        measurement_data = measurements_dict[tablet_id]
        if isinstance(measurement_data, dict) and '_id' in measurement_data:
            is_excel_measurement = True

    try:
        if is_excel_measurement:
            # Use Excel measurement workflow (scale calculation only, no measurement record creation)
            from extract_measurements import get_scale_from_excel_measurement
            px_cm_val, measurements_used = get_scale_from_excel_measurement(
                ruler_for_scale_fp, subfolder_path_item, measurements_dict, tablet_id,
                background_color_tolerance
            )
            return px_cm_val, measurements_used
        else:
            # Use sippar.json workflow (defer scale calculation to after object extraction)
            print(f"   Using measurement from database: {tablet_width_cm} cm")
            print(f"   Scale calculation deferred to after object extraction")
            
            # Return a placeholder scale that will be recalculated later
            placeholder_scale = 100.0  # pixels per cm placeholder
            return placeholder_scale, True
    except Exception as e:
        print(f"   Error using measurement: {e}")
        return None, False


def determine_pixels_per_cm_with_fallback(subfolder_path_item, subfolder_name_item, ruler_for_scale_fp,
                                        raw_ext_config, museum_selection, ruler_position,
                                        use_measurements_from_database, measurements_dict,
                                        background_color_tolerance=None, app_instance=None,
                                        force_manual_ruler=False):
    """
    Determine pixels per cm with automatic fallback to different ruler detection presets.
    """

    if force_manual_ruler:
        print(f"  Manual ruler drawing mode enabled - skipping automatic detection")
        from manual_ruler_gui import get_manual_ruler_measurement
        
        image_path = ruler_for_scale_fp
        if image_path.lower().endswith(raw_ext_config):
            from workflow_imports import convert_raw_image_to_tiff
            tmp_fp = os.path.join(
                subfolder_path_item,
                f"{os.path.splitext(os.path.basename(image_path))[0]}_manual_ruler.tif"
            )
            convert_raw_image_to_tiff(image_path, tmp_fp)
            image_path = tmp_fp
        
        px_cm_val = get_manual_ruler_measurement(image_path)
        
        if image_path != ruler_for_scale_fp and os.path.exists(image_path):
            os.remove(image_path)
        
        if px_cm_val is not None:
            print(f"  ✓ Manual ruler measurement: {px_cm_val:.2f} px/cm")
            return px_cm_val, False, 0, "Manual measurement"
        else:
            print(f"  ✗ Manual ruler measurement cancelled")
            return None, False, 0, "Manual measurement cancelled"

    from ruler_presets import (
        get_default_ruler_settings,
        get_fine_ruler_preset_settings, 
        get_wide_coverage_preset_settings
    )
    from ruler_detector import update_ruler_detection_settings

    current_settings = None
    if app_instance and hasattr(app_instance, 'advanced_tab'):
        current_settings = app_instance.advanced_tab.get_settings()

    fallback_presets = [
        {
            'name': 'Current Settings',
            'settings': current_settings if current_settings else get_default_ruler_settings()
        },
        {
            'name': 'Fine Graduation Ruler',
            'settings': get_fine_ruler_preset_settings()
        },
        {
            'name': 'Wide Coverage',
            'settings': get_wide_coverage_preset_settings()
        },
        {
            'name': 'Default Settings',
            'settings': get_default_ruler_settings()
        }
    ]

    seen_settings = set()
    unique_presets = []
    for preset in fallback_presets:
        settings_key = frozenset(preset['settings'].items()) if preset['settings'] else frozenset()
        if settings_key not in seen_settings:
            seen_settings.add(settings_key)
            unique_presets.append(preset)
    
    print(f"  Attempting ruler detection with {len(unique_presets)} different presets...")

    for i, preset in enumerate(unique_presets):
        preset_name = preset['name']
        preset_settings = preset['settings']
        
        print(f"  Attempt {i+1}/{len(unique_presets)}: Trying '{preset_name}' preset")

        if preset_settings:
            update_ruler_detection_settings(preset_settings)

        try:
            px_cm_val, measurements_used, cr2_conv_count = determine_pixels_per_cm(
                subfolder_path_item, subfolder_name_item, ruler_for_scale_fp,
                raw_ext_config, museum_selection, ruler_position,
                use_measurements_from_database, measurements_dict,
                background_color_tolerance
            )
            
            if px_cm_val is not None:
                if i == 0:
                    print(f"  ✓ Ruler detection successful with {preset_name}")
                else:
                    print(f"  ✓ Ruler detection successful with fallback preset: {preset_name}")
                    print(f"    Consider updating your default settings to '{preset_name}' for better results")
                
                return px_cm_val, measurements_used, cr2_conv_count, preset_name
            else:
                print(f"  ✗ Ruler detection failed with {preset_name}")
                
        except Exception as e:
            print(f"  ✗ Error with {preset_name}: {e}")

    print(f"  ✗ All ruler detection presets failed for {subfolder_name_item}")
    print(f"  Falling back to manual ruler measurement...")
    
    from manual_ruler_gui import get_manual_ruler_measurement
    
    image_path = ruler_for_scale_fp
    if image_path.lower().endswith(raw_ext_config):
        from workflow_imports import convert_raw_image_to_tiff
        tmp_fp = os.path.join(
            subfolder_path_item,
            f"{os.path.splitext(os.path.basename(image_path))[0]}_manual_ruler.tif"
        )
        convert_raw_image_to_tiff(image_path, tmp_fp)
        image_path = tmp_fp
    
    px_cm_val = get_manual_ruler_measurement(image_path)
    
    if image_path != ruler_for_scale_fp and os.path.exists(image_path):
        os.remove(image_path)
    
    if px_cm_val is not None:
        print(f"  ✓ Manual ruler measurement: {px_cm_val:.2f} px/cm")
        return px_cm_val, False, 0, "Manual measurement (fallback)"
    else:
        print(f"  ✗ Manual ruler measurement cancelled")
        return None, False, 0, "All presets failed"

def determine_pixels_per_cm(subfolder_path_item, subfolder_name_item, ruler_for_scale_fp,
                            raw_ext_config, museum_selection, ruler_position,
                            use_measurements_from_database, measurements_dict,
                            background_color_tolerance=None):
    """Original function - now serves as a single-attempt version"""
    px_cm_val = None
    measurements_used = False
    cr2_conv_count = 0
    
    MIN_REASONABLE_PX_PER_CM = 100
    MAX_REASONABLE_PX_PER_CM = 1500

    if use_measurements_from_database and measurements_dict:
        px_cm_val, measurements_used = get_scale_from_measurements(
            subfolder_path_item, measurements_dict, ruler_for_scale_fp, background_color_tolerance)

    if px_cm_val is None:
        try:
            px_cm_val, cr2_conv_count = detect_scale_from_ruler(
                ruler_for_scale_fp, subfolder_path_item, raw_ext_config,
                museum_selection, ruler_position)
            
            if px_cm_val is not None and px_cm_val < MIN_REASONABLE_PX_PER_CM:
                print(f"   WARNING: Detected px/cm value ({px_cm_val:.2f}) is too low (<{MIN_REASONABLE_PX_PER_CM}), rejecting...")
                px_cm_val = None
            
            if px_cm_val is not None and px_cm_val > MAX_REASONABLE_PX_PER_CM:
                print(f"   WARNING: Detected px/cm value ({px_cm_val:.2f}) is too high (>{MAX_REASONABLE_PX_PER_CM}), trying measurement fallback...")
                
                # Try to get measurement from database as fallback
                if measurements_dict:
                    fallback_px_cm, fallback_measurements_used = get_scale_from_measurements(
                        subfolder_path_item, measurements_dict, ruler_for_scale_fp, background_color_tolerance)
                    
                    if fallback_px_cm is not None:
                        print(f"   FALLBACK: Using measurement from database ({fallback_px_cm:.2f} px/cm) instead of high detection value")
                        px_cm_val = fallback_px_cm
                        measurements_used = fallback_measurements_used
                    else:
                        print(f"   No measurement available in database, keeping high detection value ({px_cm_val:.2f} px/cm)")
                        # Keep the detected value since no measurement exists
                else:
                    print(f"   No measurements database available, keeping high detection value ({px_cm_val:.2f} px/cm)")
                    # Keep the detected value since no measurements exist
                
        except Exception as e:
            print(f"   Error during ruler scale detection: {e}")

            # Fallback logic for when ruler detection completely fails
            if not measurements_used and measurements_dict:
                px_cm_val, measurements_used = get_scale_from_measurements(
                    subfolder_path_item, measurements_dict, ruler_for_scale_fp, background_color_tolerance)
                if px_cm_val is not None:
                    print(f"   FALLBACK: Using measurement from database")
                    # NOTE: Measurement record creation will happen after object extraction in gui_workflow_runner.py
                else:
                    print(f"   No measurement found in database for this tablet")

    return px_cm_val, measurements_used, cr2_conv_count


def was_excel_measurement_used(subfolder_path_item, measurements_dict):
    """
    Check if Excel measurements were used for this tablet.
    
    Args:
        subfolder_path_item: Path to the subfolder
        measurements_dict: Dictionary of measurements
        
    Returns:
        tuple: (is_excel_measurement, tablet_id, tablet_width_cm) or (False, None, None)
    """
    try:
        from measurements_utils import extract_tablet_id_from_path, get_tablet_width_from_measurements
        
        tablet_id = extract_tablet_id_from_path(subfolder_path_item)
        if not tablet_id or tablet_id not in measurements_dict:
            return False, None, None
            
        measurement_data = measurements_dict[tablet_id]
        
        # Check if this measurement comes from Excel (has '_id' field)
        is_excel_measurement = isinstance(measurement_data, dict) and '_id' in measurement_data
        
        if is_excel_measurement:
            tablet_width_cm = get_tablet_width_from_measurements(subfolder_path_item, measurements_dict)
            return True, tablet_id, tablet_width_cm
        
        return False, None, None
        
    except Exception as e:
        print(f"   Error checking if Excel measurement was used: {e}")
        return False, None, None