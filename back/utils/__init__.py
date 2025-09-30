"""
Utility module for loading environment variables consistently across the backend.
This ensures all backend modules load the .env file from the project root.
"""

import os
from dotenv import load_dotenv


def load_env_variables():
    """
    Load environment variables from the .env file in the project root.
    This function can be called from any backend module to ensure consistent
    environment variable loading regardless of the current working directory.

    Returns:
        bool: True if .env file was found and loaded, False otherwise
    """
    # Get the project root directory (3 levels up from this file: back/utils -> back -> project_root)
    current_file_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_file_dir))
    env_path = os.path.join(project_root, '.env')

    # Check if .env file exists
    if os.path.exists(env_path):
        load_dotenv(env_path)
        return True
    else:
        print(f"Warning: .env file not found at {env_path}")
        return False


def get_api_key(key_name: str = "NEXT_PUBLIC_GEMINI_API_KEY") -> str:
    """
    Get an API key from environment variables after ensuring .env is loaded.

    Args:
        key_name (str): The name of the environment variable containing the API key

    Returns:
        str: The API key value, or None if not found
    """
    load_env_variables()
    api_key = os.getenv(key_name)

    if not api_key:
        print(f"Warning: {key_name} environment variable not found or empty")

    return api_key


# Auto-load environment variables when this module is imported
load_env_variables()
