import os
import ast
import re
import pandas 
import pandas as pd
import numpy
from typing import Dict,List


def generate_ast_for_file(file_path):
    with open(file_path, "r",encoding="utf-8") as source_file:
        source_code = source_file.read()
        tree = ast.parse(source_code)
        return tree  # Return



# Generate ASTs for the entire repository, excluding .ipynb_checkpoints directories
def generate_asts_for_repo(repo_path):
    trees = []  # List to store (file_path, tree) tuples
    found_files = False

    for root, dirs, files in os.walk(repo_path):
        # Skip .ipynb_checkpoints directories
        dirs[:] = [d for d in dirs if d != ".ipynb_checkpoints"]
        for file in files:
            if file.endswith(".py"):
                found_files = True
                file_path = os.path.join(root, file)
                tree = generate_ast_for_file(file_path)
                trees.append((file_path, tree))  # Store each file's path and AST tree

    if not found_files:
        print("No Python (.py) files found in the repository.")

    return trees  # Return the list of (file_path, tree) tuples



def generate_ast_for_repo(repo_path):
    trees = []  # List to store individual AST trees for each file
    found_files = False  # Track if any .py files are found

    for root, dirs, files in os.walk(repo_path):
        for file in files:
            if file.endswith(".py"):
                found_files = True
                file_path = os.path.join(root, file)
                tree = generate_ast_for_file(file_path)
                trees.append(tree)  # Store each file's AST

    if not found_files:
        print("No Python (.py) files found in the repository.")
        return None

    combined_ast = combine_asts(trees)  # Combine all individual ASTs
    return combined_ast  # Return the combined AST for the entire repositor



def preprocess_code(source_code):
    """Preprocess the code to skip lines that cause parsing issues."""
    lines = source_code.splitlines()
    cleaned_lines = []
    for line in lines:
        try:
            ast.parse(line)  # Try parsing the line
            cleaned_lines.append(line)  # If successful, keep the line
        except (SyntaxError, IndentationError):
            print(f"Skipping problematic line: {line.strip()}")
            cleaned_lines.append("# Skipped problematic line")  # Replace with a placeholder comment
    return "\n".join(cleaned_lines)



def combine_asts(trees):
    # Combine all individual ASTs into one root node
    combined_ast = ast.Module(body=[])
    for tree in trees:
        if tree is not None:  # Only add valid ASTs
            combined_ast.body.extend(tree.body)
    return combined_ast


# Define cloud provider patterns (matches names or modules in the AST)
cloud_patterns_ast = {
    "Azure": ["azure", "azureml"],
    "Google": ["google.cloud", "vertexai","tensorflow"],
    "AWS": ["boto3","sagemaker"],
}

def detect_cloud_provider(tree):
    provider_counts = {provider: 0 for provider in cloud_patterns_ast}
    for node in ast.walk(tree):
        # Check for imports and match them against the patterns
        if isinstance(node, ast.Import):
            for alias in node.names:
                for provider, patterns in cloud_patterns_ast.items():
                    if any(pattern in alias.name for pattern in patterns):
                        provider_counts[provider] += 1
        elif isinstance(node, ast.ImportFrom):
            for provider, patterns in cloud_patterns_ast.items():
                if node.module and any(pattern in node.module for pattern in patterns):
                    provider_counts[provider] += 1
    return max(provider_counts, key=provider_counts.get) if any(provider_counts.values()) else "Unknown"



