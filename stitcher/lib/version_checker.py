import requests
import json
import threading
from typing import Optional, Tuple
import tkinter as tk
from tkinter import ttk

CURRENT_VERSION = "v1.0"
GITHUB_API_URL = "https://api.github.com/repos/ElectronicBabylonianLiterature/ebl-photo-stitcher/releases/latest"
GITHUB_RELEASES_URL = "https://github.com/ElectronicBabylonianLiterature/ebl-photo-stitcher/releases/latest"

class VersionChecker:
    def __init__(self, callback=None):
        self.callback = callback
        self.latest_version = None
        self.is_newer_available = False
        self.check_completed = False
        
    def check_for_updates_async(self):
        """Check for updates in a background thread with timeout."""
        thread = threading.Thread(target=self._check_for_updates_with_timeout, daemon=True)
        thread.start()
        
    def _check_for_updates_with_timeout(self):
        """Check for updates with automatic timeout."""
        try:
            print("Starting version check...")

            session = requests.Session()
            session.timeout = 5

            headers = {
                'User-Agent': 'ebl-photo-stitcher/version-checker',
                'Accept': 'application/vnd.github.v3+json'
            }
            
            response = session.get(GITHUB_API_URL, headers=headers, timeout=5)
            response.raise_for_status()
            
            release_data = response.json()
            self.latest_version = release_data.get('tag_name', '').strip()
            
            current_clean = CURRENT_VERSION.lstrip('v')
            latest_clean = self.latest_version.lstrip('v')
            
            if self.latest_version and self._is_version_newer(latest_clean, current_clean):
                self.is_newer_available = True
            else:
                self.is_newer_available = False
                
            self.check_completed = True

            if self.callback:
                self.callback(self.latest_version, self.is_newer_available)
                
        except requests.exceptions.Timeout:
            print("Version check timed out after 5 seconds")
            self._handle_check_failure("timeout")
        except requests.exceptions.ConnectionError:
            print("Version check failed: No internet connection")
            self._handle_check_failure("no_connection")
        except requests.exceptions.RequestException as e:
            print(f"Version check failed: Network error - {e}")
            self._handle_check_failure("network_error")
        except Exception as e:
            print(f"Version check failed: Unexpected error - {e}")
            self._handle_check_failure("unexpected_error")
    
    def _is_version_newer(self, latest, current):
        """Compare version strings (e.g., '0.8' vs '0.7')."""
        try:
            latest_parts = [int(x) for x in latest.split('.')]
            current_parts = [int(x) for x in current.split('.')]

            max_len = max(len(latest_parts), len(current_parts))
            latest_parts.extend([0] * (max_len - len(latest_parts)))
            current_parts.extend([0] * (max_len - len(current_parts)))
            
            return latest_parts > current_parts
        except (ValueError, AttributeError):

            return latest > current
    
    def _handle_check_failure(self, reason):
        """Handle failed version check."""
        self.check_completed = True

        if self.callback:
            self.callback(None, False)
    
    def open_releases_page(self):
        """Open the GitHub releases page in default browser."""
        try:
            import webbrowser
            webbrowser.open(GITHUB_RELEASES_URL)
        except Exception as e:
            print(f"Could not open releases page: {e}")

def get_current_version():
    """Get the current application version."""
    return CURRENT_VERSION