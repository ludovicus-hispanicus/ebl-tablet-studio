"""Project-based configuration manager for eBL Photo Stitcher.

Each project defines background color, ruler file(s), physical size, metadata,
logo, and optional measurements database. Built-in projects ship with the app;
users can duplicate and edit them or create their own from scratch.

A project dict uses these keys:

    name                    : str  (unique identifier, also shown in dropdown)
    builtin                 : bool (True for shipped projects; False for user)
    background_color        : [r, g, b]
    ruler_mode              : "single" | "adaptive_set"
    ruler_file              : str  (single mode: relative to assets/ or absolute)
    ruler_size_cm           : float
    ruler_files             : {"1cm": "...", "2cm": "...", "5cm": "..."}    (adaptive mode)
    ruler_sizes_cm          : {"1cm": float, "2cm": float, "5cm": float}
    detection_method        : "general" | "iraq_museum"
    ruler_position_locked   : bool
    fixed_ruler_position    : str (e.g. "top", "bottom-left-fixed")
    institution             : str
    credit_line             : str
    logo_enabled            : bool
    logo_path               : str
    measurements_file       : str  (name in assets/, or absolute path, or empty)
"""

import json
import os
import re
import shutil
import sys

try:
    from gui_utils import resource_path, get_persistent_config_dir_path
except ImportError:
    from lib.gui_utils import resource_path, get_persistent_config_dir_path


BUILTIN_ASSET_PROJECTS_DIR = "projects"
USER_PROJECTS_SUBDIR = "projects"


def _slugify(name):
    slug = re.sub(r"[^\w\-]+", "_", name.strip().lower())
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or "project"


def get_user_projects_dir():
    """Return the absolute path to the user's projects directory, creating it if needed."""
    base = get_persistent_config_dir_path()
    projects_dir = os.path.join(base, USER_PROJECTS_SUBDIR)
    if not os.path.exists(projects_dir):
        try:
            os.makedirs(projects_dir, exist_ok=True)
        except OSError as e:
            print(f"Warning: could not create user projects dir: {e}")
    return projects_dir


def get_builtin_projects_dir():
    """Return the absolute path to the built-in project templates shipped with the app."""
    return resource_path(os.path.join("assets", BUILTIN_ASSET_PROJECTS_DIR))


def _load_project_file(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and data.get("name"):
            return data
    except Exception as e:
        print(f"Warning: could not load project {path}: {e}")
    return None


def list_projects():
    """Return a list of all projects, built-ins first, then user projects.

    User projects with the same name as a built-in override the built-in.
    """
    builtin_projects = {}
    user_projects = {}

    # Load built-in projects
    builtin_dir = get_builtin_projects_dir()
    if os.path.isdir(builtin_dir):
        for filename in sorted(os.listdir(builtin_dir)):
            if filename.endswith(".json"):
                data = _load_project_file(os.path.join(builtin_dir, filename))
                if data:
                    data["builtin"] = True
                    builtin_projects[data["name"]] = data

    # Load user projects (override built-ins with same name)
    user_dir = get_user_projects_dir()
    if os.path.isdir(user_dir):
        for filename in sorted(os.listdir(user_dir)):
            if filename.endswith(".json"):
                data = _load_project_file(os.path.join(user_dir, filename))
                if data:
                    data["builtin"] = False
                    user_projects[data["name"]] = data

    # Merge: user overrides built-in
    merged = {}
    for name, project in builtin_projects.items():
        merged[name] = user_projects.pop(name, project)

    # Add remaining user-only projects
    for name, project in user_projects.items():
        merged[name] = project

    return list(merged.values())


def get_project_by_name(name):
    """Return a project dict by its display name, or None if not found."""
    for p in list_projects():
        if p.get("name") == name:
            return p
    return None


def save_user_project(project):
    """Save a user project to the user projects directory.

    Raises ValueError if trying to overwrite a built-in.
    Returns the absolute path to the saved file.
    """
    if not isinstance(project, dict) or not project.get("name"):
        raise ValueError("Project must be a dict with a 'name' field")

    project = dict(project)
    project["builtin"] = False

    user_dir = get_user_projects_dir()
    filename = _slugify(project["name"]) + ".json"
    path = os.path.join(user_dir, filename)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(project, f, indent=2, ensure_ascii=False)
    return path


def delete_user_project(name):
    """Delete a user project by name. Built-ins cannot be deleted."""
    user_dir = get_user_projects_dir()
    if not os.path.isdir(user_dir):
        return False
    for filename in os.listdir(user_dir):
        if filename.endswith(".json"):
            path = os.path.join(user_dir, filename)
            data = _load_project_file(path)
            if data and data.get("name") == name:
                try:
                    os.remove(path)
                    return True
                except OSError as e:
                    print(f"Error deleting project {name}: {e}")
                    return False
    return False


def duplicate_project(source_project, new_name):
    """Create a user-editable copy of any project under a new name."""
    copy = dict(source_project)
    copy["name"] = new_name
    copy["builtin"] = False
    return save_user_project(copy)


def default_new_project(name="New Project"):
    """Return a minimal valid project dict suitable for editing."""
    return {
        "name": name,
        "builtin": False,
        "background_color": [0, 0, 0],
        "ruler_mode": "single",
        "ruler_file": "",
        "ruler_size_cm": 5.0,
        "detection_method": "general",
        "ruler_position_locked": False,
        "fixed_ruler_position": "top",
        "institution": "",
        "credit_line": "",
        "logo_enabled": False,
        "logo_path": "",
        "measurements_file": "",
    }


def resolve_asset_path(relative_or_absolute_path):
    """Resolve a filename against assets/ if not absolute; return absolute path."""
    if not relative_or_absolute_path:
        return ""
    if os.path.isabs(relative_or_absolute_path) and os.path.exists(relative_or_absolute_path):
        return relative_or_absolute_path
    # Try assets folder
    candidate = resource_path(os.path.join("assets", relative_or_absolute_path))
    if os.path.exists(candidate):
        return candidate
    # Return whatever was given (caller can check existence)
    return relative_or_absolute_path


def resolve_ruler_path(project, ruler_key=None):
    """Resolve the ruler file path for a project.

    For single mode, returns the absolute path to ruler_file.
    For adaptive_set mode, returns the absolute path for the requested ruler_key
    (one of "1cm", "2cm", "5cm"). If ruler_key is None, returns the "5cm" default.
    """
    if project.get("ruler_mode") == "adaptive_set":
        key = ruler_key or "5cm"
        files = project.get("ruler_files", {})
        return resolve_asset_path(files.get(key, ""))
    return resolve_asset_path(project.get("ruler_file", ""))


def get_project_background_color(project):
    """Return the project's background color as a tuple (r, g, b)."""
    bg = project.get("background_color", [0, 0, 0])
    if isinstance(bg, (list, tuple)) and len(bg) >= 3:
        return (int(bg[0]), int(bg[1]), int(bg[2]))
    return (0, 0, 0)


# Active project state ------------------------------------------------------
# The currently-active project is stored in memory so workflow code can read
# project-specific configuration without passing it through every function.

_active_project = None


def set_active_project(project):
    """Mark a project as active for the current processing run."""
    global _active_project
    _active_project = project


def get_active_project():
    """Return the active project dict, or None if none is set."""
    return _active_project
