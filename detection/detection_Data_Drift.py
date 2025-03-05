
from detection.common import *
from detection.output import *


class ImportChecker(ast.NodeVisitor):
    def __init__(self):
        self.imports = set()

    def visit_Import(self, node):
        # Capture 'import module_name' statements
        for alias in node.names:
            self.imports.add(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        # Capture 'from module import submodule' statements
        module = node.module
        if module:
            self.imports.add(module)
        self.generic_visit(node)

# Step 2: Create a class to check if the imported monitoring library is used in the code
class ImportUsageChecker(ast.NodeVisitor):
    def __init__(self, import_name, metric_name):
        self.import_name = import_name
        self.metric_name = metric_name
        self.is_used = False

    def visit_Attribute(self, node):
        # Check if the metric is used as an attribute of the module
        if isinstance(node.value, ast.Name) and node.value.id == self.import_name and node.attr == self.metric_name:
            print(f"Usage detected: {self.import_name}.{self.metric_name}")
            self.is_used = True
        self.generic_visit(node)

    def visit_Name(self, node):
        # For cases where the metric is used directly without being an attribute
        if node.id == self.metric_name:
            print(f"Usage detected: {self.metric_name}")
            self.is_used = True
        self.generic_visit(node)


def check_data_drift(tree):
    # Define the modules and corresponding metrics to check for
    module_to_metric = {
        "alibi_detect": ["Report", "Dashboard", "DataDriftPreset","MMDDrift"],
        "evidently": ["Report", "Dashboard", "DataDriftPreset"],
        "scipy": ["Report", "Dashboard", "ks_2samp"],
        "sklearn": ["ModelQualityMonitor"],
        "MLFlow": ["Report"],
        "DVC": ["Report"],
        "azureml-datadrift": ["DataDriftDetector","AlertConfiguration"],
        #"azureml-core": ["DataDriftDetector"],
        "azure.ai.ml.entitie ": ["AlertNotification", "MonitorDefinition", "MonitoringTarget"],
        "google-cloud-aiplatform": ["aiplatform.ModelDeploymentMonitoringJob"],
        "sagemaker.model_monitor": ["DefaultModelMonitor", "ModelQualityMonitor"]
    }


    # Step 1: Extract imported modules using ImportChecker
    checker = ImportChecker()
    checker.visit(tree)
    imported_modules = checker.imports
    #print("Imported modules:", imported_modules)

    at_least_one_used = False
    misuse_count = 0

    for module, metrics in module_to_metric.items():
        if module in imported_modules:
            print(f"Module '{module}' is imported. Now checking for usage of its metric(s)...")
            for metric in metrics:
                usage_checker = ImportUsageChecker(import_name=module, metric_name=metric)
                usage_checker.visit(tree)

                if usage_checker.is_used:
                    print(f"No Misuse: '{metric}' is used in the code.")
                    at_least_one_used = True
                else:
                    print(f"Warning: '{metric}' is NOT used in the code despite being relevant.")
        else:
            print(f"Module '{module}' is not imported, skipping metric checks for it.")

    if at_least_one_used:
        print("No Misuse: At least one relevant module or metric is used in the code.")
    else:
        misuse_count = 1
        print(f"Misuse detected: None of the required modules or metrics are used. There is {misuse_count} Data_Drift misuse.")
    return misuse_count    

def detect_data_drift(tree):
    misuse_count = check_data_drift(tree)
    return {"misuse_count_of_Data_Drift": misuse_count}

def detect(repo_path):
    return process_repos([repo_path], detect_data_drift)

""""

repo_paths = [
    "Python-Azure-AI-REST-APIs/"
]

# Initialize an empty list to collect all misuses and counts
all_repo_misuses = []

# Iterate over each repository
for repo_path in repo_paths:
    print(f"Processing repository: {repo_path}")
    tree = generate_ast_for_repo(repo_path)
    misuse_count = check_data_drift(tree)

    # Store the results in the list
    all_repo_misuses.append({
        "repo_path": repo_path,
        "misuse_count": misuse_count

})
"""