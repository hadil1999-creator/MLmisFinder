
from detection.common import *
from detection.output import *

class EarlyStoppingAnalyzer:
    def __init__(self, tree, detect_cloud_provider):
        """
        Initialize the EarlyStoppingAnalyzer class.

        Args:
            tree (ast.AST): The abstract syntax tree of the Python source code to analyze.
            detect_cloud_provider (function): A function that detects the cloud provider from the tree.
        """
        self.tree = tree
        self.detect_cloud_provider = detect_cloud_provider
        self.provider = self.detect_cloud_provider(tree)
        self.cloud_provider_info = {
            "Azure": {
                "import_patterns": [
                    "azure.ai.ml.sweep",
                    "from azure.ai.ml.sweep import BanditPolicy",
                    "from azure.ai.ml.sweep import MedianStoppingPolicy",
                    "from azure.ai.ml.sweep import TruncationSelectionPolicy",
                ],
                "target_policies": ["BanditPolicy", "MedianStoppingPolicy", "TruncationSelectionPolicy"],
            },
            "AWS": {
                "import_patterns": [
                    "from sagemaker.tuner import HyperparameterTuner"
                ],
                "target_policies": ["HyperparameterTuner"],
            },
            "Google": {
                "import_patterns": [
                    "from tensorflow.keras.callbacks import EarlyStopping"
                ],
                "target_policies": ["EarlyStopping"],
            },
        }

        # SDK import patterns
        self.sdk_imports = {
            "azure": ["azureml.core", "azureml.train"],
            "google": ["google.cloud", "tensorflow"],
            "aws": ["sagemaker"]
        }

    def analyze(self):
        """
        Analyze the early stopping practices based on the cloud provider.

        Returns:
            dict: A dictionary containing the analysis results.
        """
        if self.provider not in self.cloud_provider_info:
            return {"details": f"Unsupported provider: {self.provider}"}

        # Check if SDK is used first
        sdk_used = self._check_sdk_usage()
        if not sdk_used:
            return {"details": "Not use of SDK - Not applicable"}

        imported = self._check_imports()
        if not imported:
            return {
                "details": "Early stopping functionality is not imported for the provider.",
                "imported": imported,
            }

        valid, details, used, early_stopping_auto = self._check_usage()
        return {
            "valid": valid,
            "details": details,
            "imported": imported,
            "used": used,
            "early_stopping_auto": early_stopping_auto,
        }

    def _check_sdk_usage(self):
        """
        Check if the SDK for the provider is imported.

        Returns:
            bool: True if the SDK is used, otherwise False.
        """
        sdk_patterns = self.sdk_imports.get(self.provider.lower(), [])
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for pattern in sdk_patterns:
                        if pattern in alias.name:
                            return True
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for pattern in sdk_patterns:
                        if pattern in f"from {node.module} import {', '.join([alias.name for alias in node.names])}":
                            return True
        return False

    def _check_imports(self):
        """
        Check if the early stopping functionality is imported for the cloud provider.

        Returns:
            bool: True if the functionality is imported, otherwise False.
        """
        provider_info = self.cloud_provider_info[self.provider]
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for pattern in provider_info["import_patterns"]:
                        if pattern in alias.name:
                            return True
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for pattern in provider_info["import_patterns"]:
                        if pattern in f"from {node.module} import {', '.join([alias.name for alias in node.names])}":
                            return True
        return False

    def _check_usage(self):
        """
        Dynamically checks early stopping usage based on the provider.

        Returns:
            tuple: A tuple containing validity, details, usage flag, and early stopping auto flag.
        """
        provider_info = self.cloud_provider_info[self.provider]
        used, early_stopping_auto, valid = False, False, False
        details = "The best practices for early stopping are not followed."

        for node in ast.walk(self.tree):
            if self.provider == "Azure":
                used, valid, details = self._check_azure_usage(node, provider_info)
            elif self.provider == "AWS":
                used, early_stopping_auto, valid, details = self._check_aws_usage(node)
            elif self.provider == "Google":
                used, valid, details = self._check_google_usage(node)

            if used:
                break  # If usage is found, stop checking further

        return valid, details, used, early_stopping_auto

    def _check_azure_usage(self, node, provider_info):
        """
        Check Azure-specific early stopping usage.

        Args:
            node (ast.AST): AST node to analyze.
            provider_info (dict): Azure provider information.

        Returns:
            tuple: A tuple containing usage, validity, and details for Azure.
        """
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in provider_info["target_policies"]:
                return True, False, "Valid policy imported but not used correctly."
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "set_limits" and isinstance(node.func.value, ast.Name):
                if node.func.value.id == "sweep_job":
                    max_total_trials = max_concurrent_trials = timeout = None
                    for keyword in node.keywords:
                        if keyword.arg == "max_total_trials":
                            max_total_trials = keyword.value
                        elif keyword.arg == "max_concurrent_trials":
                            max_concurrent_trials = keyword.value
                        elif keyword.arg == "timeout":
                            timeout = keyword.value
                    if all(arg is not None for arg in [max_total_trials, max_concurrent_trials, timeout]):
                        return True, True, "Valid use of sweep_job.set_limits."
        return False, False, "Azure early stopping not used."

    def _check_aws_usage(self, node):
        """
        Check AWS-specific early stopping usage.

        Args:
            node (ast.AST): AST node to analyze.

        Returns:
            tuple: A tuple containing usage, early stopping flag, validity, and details for AWS.
        """
        if isinstance(node, ast.Call):
            func_name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr
            if func_name == "HyperparameterTuner":
                for keyword in node.keywords:
                    if keyword.arg == "early_stopping_type" and isinstance(keyword.value, ast.Str):
                        if keyword.value.s == "Auto":
                            return True, True, True, "Valid use of HyperparameterTuner with early_stopping_type='Auto'."
        return False, False, False, "AWS early stopping not used."

    def _check_google_usage(self, node):
        """
        Check Google-specific early stopping usage.

        Args:
            node (ast.AST): AST node to analyze.

        Returns:
            tuple: A tuple containing usage, validity, and details for Google.
        """
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == "EarlyStopping":
                monitor_set = patience_set = restore_set = None
                for keyword in node.keywords:
                    if keyword.arg == "monitor" and isinstance(keyword.value, ast.Str):
                        monitor_set = keyword.value.s
                    if keyword.arg == "patience" and isinstance(keyword.value, ast.Constant):
                        patience_set = keyword.value.value
                    if keyword.arg == "restore_best_weights" and isinstance(keyword.value, ast.Constant):
                        restore_set = keyword.value.value
                if all(arg is not None for arg in [monitor_set, patience_set, restore_set]):
                    return True, True, "Valid configuration of EarlyStopping with monitor, patience, and restore_best_weights."
        return False, False, "Google early stopping not used."


def detect_early_stopping(tree):
    analyzer = EarlyStoppingAnalyzer(tree, detect_cloud_provider)
    result = analyzer.analyze()
    misuse_count = 0
    if not (result.get("imported") and result.get("used") and result.get("valid")):
        misuse_count += 1
        return {"misuse_count_of_Early_Stopping": misuse_count, "analysis_result": result}


def detect(repo_path):
    return process_repos([repo_path], detect_early_stopping)

"""""
repo_paths = [
    "Python-Azure-AI-REST-APIs/"
]

# Initialize an empty list to collect all misuses and counts
all_repo_misuses = []

# Iterate over each repository
for repo_path in repo_paths:
    print(f"Processing repository: {repo_path}")
    tree = generate_ast_for_repo(repo_path)
    analyzer = EarlyStoppingAnalyzer(tree, detect_cloud_provider)
    result = analyzer.analyze()
    # Determine misuse or not
    if result.get("imported") and result.get("used") and result.get("valid"):
        print("not misuse")
    else:
        print("misuse")

    print(result)
"""""