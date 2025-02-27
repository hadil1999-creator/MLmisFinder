import os
import importlib
import sys

DETECTION_DIR = os.path.join(os.path.dirname(__file__), "../detection")  # Ensure correct path
sys.path.append(os.path.abspath(DETECTION_DIR))  # 🔥 Add detection folder to sys.path

REPO_PATH = "repos/Python-Azure-AI-REST-APIs"  # Change this dynamically

def run_detections(repo_path):
    detection_files = [f for f in os.listdir(DETECTION_DIR) if f.startswith("detection_") and f.endswith(".py")]

    for file in detection_files:
        module_name = file[:-3]  # Remove .py extension
        detection_module = importlib.import_module(module_name)  # Import without "detection."
        
        if hasattr(detection_module, "detect"):
            print(f"Running {file} on {repo_path}...")
            try:
                result = detection_module.detect(repo_path)
                print(result)
            except Exception as e:
                print(f"Error running {file} on {repo_path}: {e}")

if __name__ == "__main__":
    repo = sys.argv[1] if len(sys.argv) > 1 else REPO_PATH
    run_detections(repo)

