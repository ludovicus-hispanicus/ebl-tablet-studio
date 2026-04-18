# Configuration for the stitching process - use consistent patterns

OBJECT_FILE_SUFFIX = "_object.tif"
SCALED_RULER_FILE_SUFFIX = "_ruler.tif"
FINAL_TIFF_SUBFOLDER_NAME = "_Final_TIFF"
FINAL_JPG_SUBFOLDER_NAME = "_Final_JPG"

STITCH_VIEW_PATTERNS_BASE = {
    "obverse": "_01",
    "reverse": "_02",
    "bottom": "_04",
    "top": "_03",
    "right": "_06",
    "left": "_05",
    "ruler": ""
}

STITCH_VIEW_PATTERNS_WITH_EXT = {k: f"{v}." for k,
                                 v in STITCH_VIEW_PATTERNS_BASE.items()}

STITCH_VIEW_PATTERNS_FOR_OBJECTS = {
    k: f"{v}{OBJECT_FILE_SUFFIX}" for k, v in STITCH_VIEW_PATTERNS_BASE.items() if k != "ruler"}

INTERMEDIATE_SUFFIX_BASE = {
    "ot": "intermediate_obverse_top",
    "ob": "intermediate_obverse_bottom",
    "ol": "intermediate_obverse_left",
    "or": "intermediate_obverse_right",
    "rt": "intermediate_reverse_top",
    "rb": "intermediate_reverse_bottom",
    "rl": "intermediate_reverse_left",
    "rr": "intermediate_reverse_right"
}
MAX_ADDITIONAL_INTERMEDIATES = 5


def generate_extended_intermediates():
    extended = dict(INTERMEDIATE_SUFFIX_BASE)

    extendable_codes = ["ot", "ob", "ol", "or", "rt", "rb", "rl", "rr"]

    for code in extendable_codes:
        base_name = INTERMEDIATE_SUFFIX_BASE[code]
        for i in range(2, MAX_ADDITIONAL_INTERMEDIATES + 1):
            extended[f"{code}{i}"] = f"{base_name}_{i}"

    return extended


EXTENDED_INTERMEDIATE_SUFFIX_BASE = generate_extended_intermediates()

INTERMEDIATE_SUFFIX_WITH_EXT = {
    k: f"_{k}." for k in EXTENDED_INTERMEDIATE_SUFFIX_BASE.keys()}
INTERMEDIATE_SUFFIX_FOR_OBJECTS = {
    k: f"_{k}{OBJECT_FILE_SUFFIX}" for k in EXTENDED_INTERMEDIATE_SUFFIX_BASE.keys()}

INTERMEDIATE_VIEW_RELATIONSHIPS = {
    "intermediate_obverse_top": ("obverse", "top"),
    "intermediate_obverse_bottom": ("obverse", "bottom"),
    "intermediate_obverse_left": ("obverse", "left"),
    "intermediate_obverse_right": ("obverse", "right"),
    "intermediate_reverse_top": ("reverse", "top"),
    "intermediate_reverse_bottom": ("reverse", "bottom"),
    "intermediate_reverse_left": ("reverse", "left"),
    "intermediate_reverse_right": ("reverse", "right")
}


def generate_extended_relationships():
    relationships = dict(INTERMEDIATE_VIEW_RELATIONSHIPS)

    for code, (main_view, adjacent_view) in INTERMEDIATE_VIEW_RELATIONSHIPS.items():

        for prefix, base_name in INTERMEDIATE_SUFFIX_BASE.items():
            if base_name == code:

                for i in range(2, MAX_ADDITIONAL_INTERMEDIATES + 1):

                    extended_name = f"{base_name}_{i}"
                    relationships[extended_name] = (main_view, adjacent_view)
                break

    return relationships


EXTENDED_INTERMEDIATE_VIEW_RELATIONSHIPS = generate_extended_relationships()

STITCH_VIEW_GAP_PX = 100
STITCH_RULER_PADDING_PX = 100
STITCH_FINAL_MARGIN_PX = 100

STITCH_LOGO_STANDARD_WIDTH_PX = 1800
STITCH_LOGO_MAX_WIDTH_FRACTION = 0.70
STITCH_LOGO_PADDING_ABOVE = 30
STITCH_LOGO_PADDING_BELOW = 30

STITCH_OUTPUT_DPI = 600
STITCH_BACKGROUND_COLOR = (0, 0, 0)
STITCH_TIFF_COMPRESSION = "lzw"
JPEG_SAVE_QUALITY = 85

MUSEUM_CONFIGS = {
    "British Museum": {
        "background_color": (0, 0, 0),
        "ruler_type": "tif",
        "ruler_templates": {
            "1cm": "BM_1cm_scale.tif",
            "2cm": "BM_2cm_scale.tif",
            "5cm": "BM_5cm_scale.tif"
        }
    },
    "Iraq Museum": {
        "background_color": (255, 255, 255),
        "ruler_type": "svg",
        "ruler_template": "IM_photo_ruler.svg",
        "ruler_size_cm": 4.599
    },
    "Iraq Museum (Sippar Library)": {
        "background_color": (255, 255, 255),
        "ruler_type": "svg",
        "ruler_template": "Sippar_Library_Ruler.svg",
        "ruler_size_cm": 3.886
    },
    "eBL Ruler (CBS)": {
        "background_color": (255, 255, 255),
        "ruler_type": "svg",
        "ruler_template": "General_eBL_photo_ruler.svg",
        "ruler_size_cm": 4.317
    },
    "Non-eBL Ruler (VAM)": {
        "background_color": (255, 255, 255),
        "ruler_type": "svg",
        "ruler_template": "General_External_photo_ruler.svg",
        "ruler_size_cm": 3.248
    },
    "Black background (Jena)": {
        "background_color": (0, 0, 0),
        "ruler_type": "tif",
        "ruler_templates": {
            "1cm": "Black_1cm_scale.tif",
            "2cm": "Black_2cm_scale.tif",
            "5cm": "Black_5cm_scale.tif"
        }
    }
}

STITCH_INSTITUTION = "LMU Munich"
STITCH_CREDIT_LINE = "The image was produced with funding from the European Research Council (ERC) under the European Union's Horizon Europe research and innovation programme (Grant agreement No. 101171038). Grant Acronym RECC (DOI: 10.3030/101171038). Published under a CC BY NC 4.0 license."
STITCH_XMP_USAGE_TERMS = f"Published under a CC BY NC 4.0 license."


def get_extended_intermediate_suffixes():
    """
    Generate a dictionary of all intermediate suffixes including numbered variants.
    Includes support for _07/_08 equivalence to _ol/_or as documented in README.

    Returns:
        Dictionary mapping all suffix codes (e.g., 'ol', 'ol2', 'or3', '07', '08') to their position names
    """
    extended_suffixes = {}
    for code in INTERMEDIATE_SUFFIX_BASE.keys():
        extended_suffixes[code] = INTERMEDIATE_SUFFIX_BASE[code]
    for code in INTERMEDIATE_SUFFIX_BASE.keys():
        base_position = INTERMEDIATE_SUFFIX_BASE[code]
        for i in range(2, MAX_ADDITIONAL_INTERMEDIATES + 1):
            numbered_code = f"{code}{i}"
            extended_suffixes[numbered_code] = base_position
    extended_suffixes["07"] = INTERMEDIATE_SUFFIX_BASE["ol"]
    extended_suffixes["08"] = INTERMEDIATE_SUFFIX_BASE["or"]

    return extended_suffixes
