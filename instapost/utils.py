import json
import logging
import os
import sys
import psutil
from pathlib import Path
import time

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def load_json(filepath):
    full_path = PROJECT_ROOT / filepath
    if full_path.exists():
        with open(full_path, 'r') as f:
            return json.load(f)
    return []

def save_json(filepath, data):
    full_path = PROJECT_ROOT / filepath
    with open(full_path, 'w') as f:
        json.dump(data, f, indent=2)

def setup_logging(name):
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s [%(levelname)s] %(message)s',
                        handlers=[logging.StreamHandler()])
    return logging.getLogger(name)

def setup_logger(name: str, log_level=logging.INFO) -> logging.Logger:
    """Set up a logger with the given name and log level.
    
    Args:
        name: Name of the logger
        log_level: Logging level (default: logging.INFO)
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    
    # Create console handler
    ch = logging.StreamHandler()
    ch.setLevel(log_level)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Add formatter to console handler
    ch.setFormatter(formatter)
    
    # Add console handler to logger
    if not logger.handlers:
        logger.addHandler(ch)
    
    return logger

def show_idle_animation(symbol='👁️'):
    """Display an idle animation in the console."""
    sys.stdout.write(f"\r{symbol} Idle... ")
    sys.stdout.flush()
    time.sleep(1.0)  # Show the eye for 1 second
    sys.stdout.write("\r" + " " * 15 + "\r")  # Clear the line
    sys.stdout.flush()
    time.sleep(1.0)  # Pause for 1 second before next blink

def is_process_running(process_name):
    """Check if there is any running process that contains the given name."""
    # Iterate over all running processes
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            # Check if process name or command line contains the given name
            if (process_name.lower() in proc.info['name'].lower() or 
                (proc.info['cmdline'] and process_name.lower() in ' '.join(proc.info['cmdline']).lower())):
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return False

def ensure_single_instance(component_name):
    """Ensure only one instance of the component is running."""
    if is_process_running(f'python.*{component_name}'):
        print(f"Error: Another instance of {component_name} is already running.")
        print("Please stop it before starting a new one.")
        sys.exit(1)
import psutil
import sys

def is_process_running(process_name):
    """Check if there is any running process that contains the given name."""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if (process_name.lower() in proc.info['name'].lower() or 
                (proc.info['cmdline'] and process_name.lower() in ' '.join(proc.info['cmdline']).lower())):
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return False

def ensure_single_instance(component_name):
    """Ensure only one instance of the component is running."""
    if is_process_running(f'python.*{component_name}'):
        print(f"Error: Another instance of {component_name} is already running.")
        print("Please stop it before starting a new one.")
        sys.exit(1)
