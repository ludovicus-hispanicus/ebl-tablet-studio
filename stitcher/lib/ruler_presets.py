"""
Central configuration for ruler detection presets.
This module contains all ruler preset definitions to avoid duplication.
"""

def get_default_ruler_settings():
    """Get default ruler detection settings"""
    return {
        'roi_vertical_start': 0.02,
        'roi_vertical_end': 0.30,
        'roi_horizontal_start': 0.02,
        'roi_horizontal_end': 0.30,
        'analysis_scanline_count': 7,
        'mark_binarization_threshold': 150,
        'min_mark_width_fraction': 0.04,
        'max_mark_width_fraction': 0.40,
        'mark_width_tolerance': 0.40,
        'min_alternating_marks': 2
    }

def get_fine_ruler_preset_settings():
    """Get fine graduation ruler preset settings"""
    return {
        'roi_vertical_start': 0.0,
        'roi_vertical_end': 1.0,
        'roi_horizontal_start': 0.0,
        'roi_horizontal_end': 0.8,
        'analysis_scanline_count': 7,
        'mark_binarization_threshold': 120,
        'min_mark_width_fraction': 0.005,
        'max_mark_width_fraction': 0.40,
        'mark_width_tolerance': 0.60,
        'min_alternating_marks': 3
    }

def get_wide_coverage_preset_settings():
    """Get wide coverage preset settings"""
    return {
        'roi_vertical_start': 0.0,
        'roi_vertical_end': 1.0,
        'roi_horizontal_start': 0.0,
        'roi_horizontal_end': 0.9,
        'analysis_scanline_count': 10,
        'mark_binarization_threshold': 130,
        'min_mark_width_fraction': 0.01,
        'max_mark_width_fraction': 0.50,
        'mark_width_tolerance': 0.50,
        'min_alternating_marks': 2
    }

def get_preset_by_name(preset_name):
    """Get preset settings by name"""
    presets = {
        'Default Settings': get_default_ruler_settings(),
        'Fine Graduation Ruler': get_fine_ruler_preset_settings(),
        'Wide Coverage': get_wide_coverage_preset_settings()
    }
    return presets.get(preset_name, get_default_ruler_settings())

def apply_settings_to_vars(settings, var_dict):
    """
    Apply settings dictionary to tkinter variables.
    
    Args:
        settings (dict): Settings dictionary
        var_dict (dict): Dictionary mapping setting keys to tkinter variables
    """
    for key, value in settings.items():
        if key in var_dict:
            var_dict[key].set(value)