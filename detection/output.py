from .common import *
from detection_Not_using_batch_API import generate_combined_ast_for_repo

def process_repos(repo_paths, detection_function, save_to_excel=True, file_name="misuses_report.xlsx"):
    """
    Processes a list of repositories using a given detection function.

    :param repo_paths: List of repository paths.
    :param detection_function: Function to detect misuses.
    :param save_to_excel: Whether to save the results to an Excel file.
    :param file_name: Name of the Excel file if saving results.
    :return: List of results for each repository.
    """
    all_repo_misuses = []

    for repo_path in repo_paths:
        print(f"Processing repository: {repo_path}")
        tree = generate_ast_for_repo(repo_path)  # Generic AST generation
        if detection_function.__name__ == "detect_function_calls":

            trees = generate_asts_for_repo(repo_path)
            print('hi')
            combined_tree = generate_combined_ast_for_repo(repo_path)
            print('hi')
            result = detection_function(trees, combined_tree)  # Call detect_function_calls with repo_path
        else:
            result = detection_function(tree)  # Call detection function with AST tree
        
        # Ensure result is in dictionary format
        if isinstance(result, dict):
            result["repo_path"] = repo_path
            all_repo_misuses.append(result)
        else:
            all_repo_misuses.append({"repo_path": repo_path, "result": result})

    # Save results to Excel if needed
    if save_to_excel:
        misuses_df = pd.DataFrame(all_repo_misuses)
        misuses_df.to_excel(file_name, index=False, sheet_name="Misuses_Report")
        print(f"Data saved to {file_name}")

    return all_repo_misuses
