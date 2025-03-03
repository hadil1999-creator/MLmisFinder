from .common import *

def process_repos(repo_paths, detection_function, save_to_excel=True, file_name="misuses_report.xlsx"):
    """
    Processes a list of repositories using a given detection function.

    :param repo_paths: List of repository paths.
    :param detection_function: Function to detect misuses.
    :param save_to_excel: Whether to save the results to an Excel file.
    :param file_name: Name of the Excel file if saving results.
    :return: List of results for each repository.
    """
    from detection_Not_using_batch_API import generate_combined_ast_for_repo

    all_repo_misuses = []
    print(repo_paths)
    for repo_path in repo_paths:
        print(f"Processing repository: {repo_path}")
        print(repo_path)
        tree = generate_ast_for_repo(repo_path)  # Generic AST generation
       
        if detection_function.__name__ == "detect_function_calls":
            combined_tree = generate_combined_ast_for_repo(repo_path)
            trees = generate_asts_for_repo(repo_path)  # Corrected here
            result = detection_function(trees, combined_tree) # Call detect_function_calls with repo_path
            
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
        # Reorder columns to make "repo_path" the first column
        cols = ["repo_path"] + [col for col in misuses_df.columns if col != "repo_path"]
        misuses_df = misuses_df[cols]

        try:
            with pd.ExcelWriter(file_name, mode="a", engine="openpyxl", if_sheet_exists="overlay") as writer:
                existing_df = pd.read_excel(file_name, sheet_name="Misuses_Report")
                combined_df = pd.concat([existing_df, misuses_df], ignore_index=True)
                combined_df.to_excel(writer, index=False, sheet_name="Misuses_Report")
        except FileNotFoundError:
            # If the file doesn't exist, create a new one
            misuses_df.to_excel(file_name, index=False, sheet_name="Misuses_Report")

        print(f"Data saved to {file_name}")
    return all_repo_misuses
