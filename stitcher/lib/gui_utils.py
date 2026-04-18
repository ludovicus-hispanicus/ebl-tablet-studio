"""
Minimal stub left after the Tkinter GUI was removed in the Phase B merge.

The deleted gui_utils.py was ~370 lines of Tkinter helpers (text widget
redirection, file-dialog wrappers, window geometry, etc.), none of which
is needed when the stitcher runs headlessly behind an Electron UI. Two
non-GUI helpers survived because project_manager.py still imports them:
resource_path() and get_persistent_config_dir_path().

The module filename stays as-is (`gui_utils`) to avoid a cross-repo
rename during vendoring — callers across lib/ still import it by that
name. Renaming to something honest (e.g. `app_paths`) is deferred to
Phase B.6 alongside the gui_workflow_runner → workflow_runner rename.
"""

import os
import sys

# Shared config namespace: %APPDATA%/eBLImageProcessor/projects/
# (also read/written by the Electron app's project manager).
APP_NAME_FOR_CONFIG = "eBLImageProcessor"


def resource_path(relative_path):
    """
    Resolve a resource path that works in both dev and PyInstaller bundles.
    In a frozen bundle, sys._MEIPASS points at the runtime extraction dir.
    """
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(os.path.dirname(sys.argv[0]))
    return os.path.join(base_path, relative_path)


def get_persistent_config_dir_path():
    """
    Platform-appropriate user config dir for the shared eBLImageProcessor
    namespace. Created if missing. Callers that can't write to it fall back
    to the script directory.
    """
    home_dir = os.path.expanduser("~")
    if sys.platform == "win32":
        app_data_env = os.getenv("APPDATA", os.path.join(home_dir, "AppData", "Roaming"))
    elif sys.platform == "darwin":
        app_data_env = os.path.join(home_dir, "Library", "Application Support")
    else:
        app_data_env = os.getenv("XDG_CONFIG_HOME", os.path.join(home_dir, ".config"))

    config_directory = os.path.join(app_data_env, APP_NAME_FOR_CONFIG)

    if not os.path.exists(config_directory):
        try:
            os.makedirs(config_directory, exist_ok=True)
        except OSError:
            # Read-only filesystem or permission issue: fall back to script dir.
            return os.path.abspath(os.path.dirname(sys.argv[0]))

    return config_directory
