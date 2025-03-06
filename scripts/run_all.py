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
import time
import shutil
import stat

DETECTION_DIR = os.path.join(os.path.dirname(__file__), r"../detection")  
sys.path.append(os.path.abspath(DETECTION_DIR))  

EXCEL_FILE = r"repos_data.xlsx"  # Path to your Excel file
CLONE_DIR =  r"repos"   # Directory to store cloned repos

def clone_repo(repo_url):
    """Clone a repository from GitHub into the repos directory."""
    repo_name = repo_url.rstrip("/").split("/")[-1].replace(".git", "")  # Ensure no trailing slash, remove .git if present
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

def remove_readonly(func, path, _):
    """Clear the read-only flag and retry deletion."""
    os.chmod(path, stat.S_IWRITE)  # Change file permission to writable
    func(path)  # Retry deletion

def delete_repo(repo_path):
    """Force delete the cloned repository, handling locked files."""
    try:
        shutil.rmtree(repo_path)  # Force remove
        print(f"Deleted repository: {repo_path}")
    except Exception as e:
        print(f"Failed to delete {repo_path}: {e}")

        
def save_results_to_excel(results, file_name):
    """Save detection execution times and misuses to an Excel file."""
    df = pd.DataFrame(results)

    try:
        with pd.ExcelWriter(file_name, mode="a", engine="openpyxl", if_sheet_exists="overlay") as writer:
            existing_df = pd.read_excel(file_name, sheet_name="Execution_Times")
            combined_df = pd.concat([existing_df, df], ignore_index=True)
            combined_df.to_excel(writer, index=False, sheet_name="Execution_Times")
    except FileNotFoundError:
        # If the file doesn't exist, create a new one
        df.to_excel(file_name, index=False, sheet_name="Execution_Times")

    print(f"Execution times saved to {file_name}")

def run_detections(repo_path):
    """Run all detection scripts on the given repo and measure execution time."""
    detection_files = [f for f in os.listdir(DETECTION_DIR) if f.startswith("detection_") and f.endswith(".py")]
    
    detection_results = []  # List to store execution time and results
    total_detection_time = 0  # Total execution time for all detection scripts

    for file in detection_files:
        module_name = file[:-3]  
        detection_module = importlib.import_module(module_name)  

        if hasattr(detection_module, "detect"):
            print(f"Running {file} on {repo_path}...")
            start_time = time.time()  # Start timing
            
            try:
                result = detection_module.detect(repo_path)
                end_time = time.time()  # End timing
                
                execution_time = end_time - start_time  # Calculate execution time
                total_detection_time += execution_time  # Sum execution times

                print(f"{file} execution time: {execution_time:.4f} seconds")
                print(result)

                # Store the data in a structured format
                detection_results.append({
                    "repo_name": os.path.basename(repo_path),
                    "misuse_name": file,  # Detection file name as misuse identifier
                    "execution_time": round(execution_time, 4),
                    "result": [{k: v for k, v in result.items() if k != "repo_path"} for result in result]  # Can be extended with more details if needed
                })

            except Exception as e:
                print(f"Error running {file} on {repo_path}: {e}")

    print(f"Total execution time for all detection scripts on {repo_path}: {total_detection_time:.4f} seconds\n")
    
    # Save results to Excel
    save_results_to_excel(detection_results, "final_report.xlsx")

    return total_detection_time

if __name__ == "__main__":
    # Load repository URLs from Excel
    df = pd.read_excel(EXCEL_FILE)
    if "repo" not in df.columns:
        print("Error: Excel file must contain a column named 'repo'")
        sys.exit(1)

    os.makedirs(CLONE_DIR, exist_ok=True)  # Ensure repos folder exists
    df = df.iloc[625:]  

    df = df.dropna(subset=["repo"])  
    for repo_url in df["repo"].dropna():
        repo_path = clone_repo(repo_url)
        if repo_path:
            run_detections(repo_path)
            print(f"Deleting repo: {repo_path}")  # Debugging
            delete_repo(repo_path)



"""""
def run_detections(repo_path):
    Run all detection scripts on the given repo.
    detection_files = [f for f in os.listdir(DETECTION_DIR) if f.startswith("detection_") and f.endswith(".py")]
    total_detection_time = 0 
    for file in detection_files:
        module_name = file[:-3]  
        detection_module = importlib.import_module(module_name)  

        if hasattr(detection_module, "detect"):
            print(f"Running {file} on {repo_path}...")
            start_time = time.time()  # Start timing
            try:
                result = detection_module.detect(repo_path)
                end_time = time.time()
                execution_time = end_time - start_time  # Calculate execution time
                total_detection_time += execution_time
                print(f"{file} execution time: {execution_time:.4f} seconds")
                print(result)
            except Exception as e:
                print(f"Error running {file} on {repo_path}: {e}")
    print(f"Total execution time for all detection scripts on {repo_path}: {total_detection_time:.4f} seconds\n")
    return total_detection_time  # Return total execution time for repo
"""""