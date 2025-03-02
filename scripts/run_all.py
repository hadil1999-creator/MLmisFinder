"""import os
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

"""
import os
import importlib
import sys
import pandas as pd
import git

DETECTION_DIR = os.path.join(os.path.dirname(__file__), "../detection")  
sys.path.append(os.path.abspath(DETECTION_DIR))  

EXCEL_FILE = "repos_data.xlsx"  # Path to your Excel file
CLONE_DIR = "repos"  # Directory to store cloned repos

def clone_repo(repo_url):
    """Clone a repository from GitHub into the repos directory."""
    repo_name = repo_url.strip().split("/")[-1].replace(".git", "")  # Extract repo name
    repo_path = os.path.join(CLONE_DIR, repo_name)

    if os.path.exists(repo_path):
        print(f"Repository {repo_name} already cloned. Skipping...")
    else:
        print(f"Cloning {repo_url} into {repo_path}...")
        try:
            git.Repo.clone_from(repo_url, repo_path)
        except Exception as e:
            print(f"Failed to clone {repo_url}: {e}")
            return None

    return repo_path

def run_detections(repo_path):
    """Run all detection scripts on the given repo."""
    detection_files = [f for f in os.listdir(DETECTION_DIR) if f.startswith("detection_") and f.endswith(".py")]

    for file in detection_files:
        module_name = file[:-3]  
        detection_module = importlib.import_module(module_name)  

        if hasattr(detection_module, "detect"):
            print(f"Running {file} on {repo_path}...")
            try:
                result = detection_module.detect(repo_path)
                print(result)
            except Exception as e:
                print(f"Error running {file} on {repo_path}: {e}")

if __name__ == "__main__":
    # Load repository URLs from Excel
    df = pd.read_excel(EXCEL_FILE)
    if "repo" not in df.columns:
        print("Error: Excel file must contain a column named 'repo'")
        sys.exit(1)

    os.makedirs(CLONE_DIR, exist_ok=True)  # Ensure repos folder exists

    for repo_url in df["repo"].dropna():
        repo_path = clone_repo(repo_url)
        if repo_path:
            run_detections(repo_path)
