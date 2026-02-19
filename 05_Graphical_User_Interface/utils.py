"""
Utility Functions for BIM Safety Analysis GUI
Helper functions for file validation, API testing, logging, etc.
"""

import os
import json
import shutil
import logging
import platform
import subprocess
from pathlib import Path
from datetime import datetime


def setup_logging(log_file: Path):
    """Configure logging for GUI application"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    logging.info("GUI Application logging initialized")


def validate_ifc_file(file_path: Path) -> tuple:
    """
    Check if file is valid IFC

    Returns:
        (is_valid: bool, message: str)
    """
    if not file_path.exists():
        return False, f"File does not exist: {file_path}"

    if file_path.suffix.lower() != '.ifc':
        return False, f"File must be .ifc format, got {file_path.suffix}"

    # Check if file is readable (use latin-1 encoding for IFC files)
    try:
        with open(file_path, 'r', encoding='latin-1', errors='ignore') as f:
            first_line = f.readline()
            if not first_line.startswith('ISO-10303-21'):
                return False, "File does not appear to be a valid IFC file (missing ISO-10303-21 header)"
    except Exception as e:
        return False, f"Error reading file: {str(e)}"

    return True, "Valid IFC file"


def test_api_key(api_key: str, api_base: str = "https://openrouter.ai/api/v1") -> tuple:
    """
    Test DeepSeek API key validity

    Returns:
        (success: bool, message: str)
    """
    if not api_key or not api_key.strip():
        return False, "API key is empty"

    try:
        import requests
    except ImportError:
        return False, "requests library not installed"

    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json"
    }

    # Simple test request
    try:
        response = requests.post(
            f"{api_base}/chat/completions",
            headers=headers,
            json={
                "model": "deepseek/deepseek-chat",
                "messages": [{"role": "user", "content": "test"}],
                "max_tokens": 5
            },
            timeout=10
        )

        if response.status_code == 200:
            return True, "API key is valid ✓"
        elif response.status_code == 401:
            return False, "API key is invalid (401 Unauthorized)"
        elif response.status_code == 429:
            return False, "Rate limit exceeded (429 Too Many Requests)"
        else:
            return False, f"API error: HTTP {response.status_code}"

    except requests.exceptions.Timeout:
        return False, "Connection timeout - check your internet connection"
    except requests.exceptions.ConnectionError:
        return False, "Connection failed - check your internet connection"
    except Exception as e:
        return False, f"Connection error: {str(e)}"


def load_api_key(api_key_file: Path) -> str:
    """Load API key from file (ignoring comments)"""
    if api_key_file.exists():
        try:
            with open(api_key_file) as f:
                # Read all lines and filter out comments
                lines = f.readlines()
                for line in lines:
                    line = line.strip()
                    # Skip empty lines and comments
                    if line and not line.startswith('#'):
                        # Return first non-comment line
                        return line
                return ""
        except Exception as e:
            logging.error(f"Error loading API key: {e}")
            return ""
    return ""


def save_api_key(api_key: str, api_key_file: Path):
    """Save API key to file"""
    try:
        with open(api_key_file, 'w') as f:
            f.write(api_key.strip())
        logging.info("API key saved successfully")
    except Exception as e:
        logging.error(f"Error saving API key: {e}")
        raise


def open_folder_in_explorer(folder_path: Path):
    """Open folder in system file explorer"""
    if not folder_path.exists():
        logging.error(f"Folder does not exist: {folder_path}")
        return

    system = platform.system()

    try:
        if system == "Windows":
            os.startfile(folder_path)
        elif system == "Darwin":  # macOS
            subprocess.run(["open", folder_path])
        else:  # Linux
            subprocess.run(["xdg-open", folder_path])
    except Exception as e:
        logging.error(f"Error opening folder: {e}")


def open_file_in_explorer(file_path: Path):
    """Open file location in explorer and highlight the file"""
    if not file_path.exists():
        logging.error(f"File does not exist: {file_path}")
        return

    system = platform.system()

    try:
        if system == "Windows":
            # Use explorer with /select flag to highlight the file
            subprocess.run(['explorer', '/select,', str(file_path)])
        elif system == "Darwin":  # macOS
            subprocess.run(["open", "-R", str(file_path)])
        else:  # Linux
            # Open parent folder (can't highlight specific file on Linux easily)
            subprocess.run(["xdg-open", str(file_path.parent)])
    except Exception as e:
        logging.error(f"Error opening file in explorer: {e}")


def format_timestamp(timestamp_str: str) -> str:
    """Convert YYYYMMDD_HHMMSS to readable format"""
    try:
        dt = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
        return dt.strftime("%B %d, %Y at %I:%M %p")
    except:
        return timestamp_str


def calculate_progress(current_phase: int, phase_progress: float) -> float:
    """
    Calculate overall pipeline progress

    Args:
        current_phase: 1-4
        phase_progress: 0.0-1.0 for current phase

    Returns:
        Overall progress 0.0-1.0
    """
    # Each phase is 25% of total
    base_progress = (current_phase - 1) * 0.25
    phase_contribution = phase_progress * 0.25
    return base_progress + phase_contribution


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"


def get_latest_run_directory(base_path: Path, pattern: str = "run_*") -> Path:
    """
    Find the most recent run directory

    Args:
        base_path: Base directory to search in
        pattern: Glob pattern for run directories

    Returns:
        Path to latest run directory or None
    """
    if not base_path.exists():
        return None

    run_dirs = sorted(base_path.glob(pattern))
    return run_dirs[-1] if run_dirs else None


def safe_json_load(file_path: Path) -> dict:
    """
    Safely load JSON file with error handling

    Returns:
        dict or None if error
    """
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Error loading JSON from {file_path}: {e}")
        return None


def safe_json_save(data: dict, file_path: Path) -> bool:
    """
    Safely save JSON file with error handling

    Returns:
        True if successful, False otherwise
    """
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        logging.error(f"Error saving JSON to {file_path}: {e}")
        return False


def truncate_text(text: str, max_length: int = 50) -> str:
    """Truncate text with ellipsis if too long"""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."


def ensure_directory(directory: Path):
    """Ensure directory exists, create if needed"""
    directory.mkdir(parents=True, exist_ok=True)
