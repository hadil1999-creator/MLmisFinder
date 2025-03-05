
from detection.common import *
from detection.output import *

class ImportChecker(ast.NodeVisitor):
    def __init__(self):
        self.imports = set()

    def visit_Import(self, node):
        for alias in node.names:
            self.imports.add(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        module = node.module
        if module:
            self.imports.add(module)
        self.generic_visit(node)

class ImportUsageChecker(ast.NodeVisitor):
    def __init__(self, import_name):
        self.import_name = import_name
        self.is_used = False

    def visit_Name(self, node):
        if node.id.startswith(self.import_name):
            self.is_used = True
        self.generic_visit(node)

    def visit_Call(self, node):
        if isinstance(node.func, ast.Attribute):
            # Check if the attribute is called on a `Name` (e.g., requests.get)
            if isinstance(node.func.value, ast.Name) and node.func.value.id == self.import_name:
                self.is_used = True
        elif isinstance(node.func, ast.Subscript):
            # Handle case like `requests.get['key']`
            if isinstance(node.func.value, ast.Name) and node.func.value.id == self.import_name:
                self.is_used = True
        self.generic_visit(node)

# A helper function to check if requests is used for monitoring-related API calls
def is_monitoring_request(node):
    """
    This function checks if a request is related to monitoring ML API limits.
    It inspects the URL, HTTP method, and headers for relevant information.
    """
    url = None
    method = None
    headers = None
    query_params = None

    # Loop through the arguments passed to the request call
    for arg in node.keywords:
        if arg.arg == "url":
            url = arg.value.s if isinstance(arg.value, ast.Str) else None
        elif arg.arg == "method":
            method = arg.value.s if isinstance(arg.value, ast.Str) else None
        elif arg.arg == "headers":
            headers = arg.value
        elif arg.arg == "params":
            query_params = arg.value

    # Check if URL contains monitoring-related keywords
    if url and any(keyword in url for keyword in ["cloudwatch", "googleapis", "monitor", "ml", "metrics"]):
        print(f"URL detected for monitoring: {url}")
        if method in ["GET", "POST"]:
            print(f"HTTP Method: {method} is valid for monitoring.")
            return True

    # Check for specific query parameters that might indicate monitoring-related activity
    if query_params:
        if isinstance(query_params, ast.Dict):
            # If query_params is a dictionary (ast.Dict), process its keys
            for key in query_params.keys:
                param_name = key.s if isinstance(key, ast.Str) else None
                if param_name and any(keyword in param_name for keyword in ["limit", "quota", "rate", "metrics"]):
                    print(f"Query Parameter related to limits/metrics detected: {param_name}")
                    return True
        elif isinstance(query_params, ast.Name):
            # If query_params is a variable (ast.Name), try to resolve its value in the AST
            resolved_query_params = None
            for node in ast.walk(tree):  # Assume `tree` is the AST of the source code
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == query_params.id:
                            resolved_query_params = node.value
                            break
                    if resolved_query_params:
                        break

            # Process the resolved value if it's a dictionary
            if isinstance(resolved_query_params, ast.Dict):
                for key in resolved_query_params.keys:
                    param_name = key.s if isinstance(key, ast.Str) else None
                    if param_name and any(keyword in param_name for keyword in ["limit", "quota", "rate", "metrics"]):
                        print(f"Query Parameter related to limits/metrics detected: {param_name}")
                        return True
            else:
                print("Query parameters could not be resolved or are not a dictionary.")
        else:
            print(f"Unhandled query_params type: {type(query_params)}")
    else:
        print("query_params is None or empty.")


    if isinstance(headers, ast.Dict):
      for key in headers.keys:
          header_name = key.s if isinstance(key, ast.Str) else None
          if header_name and any(keyword in header_name.lower() for keyword in ["x-apilimit", "x-ratelimit", "x-usage"]):
              print(f"Header related to limits detected: {header_name}")
              return True
          elif isinstance(headers, ast.Name):
              print(f"Headers is a Name node: {headers.id}")
              # Resolve the value of the variable `headers.id` in the broader code context.
          else:
              print(f"Unhandled headers type: {type(headers)}")


    # If no relevant features found, return False
    print("No monitoring-related indicators found.")
    return False

"""""
def check_api_limits_in_trees(tree):
    misuse_count = 0
    cloud_provider = detect_cloud_provider(tree)  # Ensure this function is defined

    if cloud_provider == 'Azure':
        module_to_metric = {
            "azure.identity": "IdentityClient",
            "azure.monitor.query": "MetricsQueryClient",
            "requests": "requests"
        }
    elif cloud_provider == 'Google':
        module_to_metric = {
            "google.cloud": "monitoring_v3",
            "google.auth": "MetricsQueryClient",
            "requests": "requests"
        }
    elif cloud_provider == 'Aws':
        module_to_metric = {
            "boto3": ["cloudwatch.get_metric_data", "list_service_quotas"],
            "requests": "requests"
        }
    else:
        module_to_metric = {}

    # Step 1: Check for import of monitoring libraries
    checker = ImportChecker()
    checker.visit(tree)
    imported_modules = checker.imports

    # Step 2: Check if any relevant package is imported and if its metric is used
    for module, metrics in module_to_metric.items():
        if module in imported_modules:
            print(f"Module '{module}' is imported. Checking usage...")

            if isinstance(metrics, list):  # Handle multiple metrics for boto3
                for metric in metrics:
                    usage_checker = ImportUsageChecker(metric)
                    usage_checker.visit(tree)
                    if not usage_checker.is_used:
                        print(f"Misuse detected: '{metric}' is NOT used despite being imported.")
                        misuse_count += 1
            else:
                usage_checker = ImportUsageChecker(metrics)
                usage_checker.visit(tree)
                if not usage_checker.is_used:
                    print(f"Misuse detected: '{metrics}' is NOT used despite being imported.")
                    misuse_count += 1

            # Special handling for the `requests` module
            if module == "requests":
                print("Module 'requests' is detected. Now verifying if it is used for monitoring ML service limits...")

                for node in ast.walk(tree):
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                        # Check if `requests` is being used and if it's for monitoring ML API limits
                        func_value = node.func.value
                        if isinstance(func_value, ast.Name) and func_value.id == "requests":
                            if is_monitoring_request(node):
                                print(f"No Misuse: 'requests' is used to monitor ML service limits.")
                                break
                else:
                    print("Misuse detected: 'requests' is not used for monitoring ML service limits.")
                    misuse_count += 1

        else:
            # Handle the case where module and its metric are not in `module_to_metric.items()`
            print(f"Misuse detected: '{module}' or its associated metric is not in `module_to_metric.items()`. This is flagged.")
            misuse_count += 1

    print(f"There are {misuse_count} improper handling ML API limits misuses detected.")
    return misuse_count

"""""
def check_api_limits_in_trees(tree):
    misuse_count = 0
    cloud_provider = detect_cloud_provider(tree)  # Ensure this function is defined

    if cloud_provider == 'Azure':
        module_to_metric = {
            "azure.identity": "IdentityClient",
            "azure.monitor.query": "MetricsQueryClient",
            "requests": "requests"
        }
    elif cloud_provider == 'Google':
        module_to_metric = {
            "google.cloud": "monitoring_v3",
            "google.auth": "MetricsQueryClient",
            "requests": "requests"
        }
    elif cloud_provider == 'Aws':
        module_to_metric = {
            "boto3": ["cloudwatch.get_metric_data", "list_service_quotas"],
            "requests": "requests"
        }
    else:
        module_to_metric = {}

    # Step 1: Check for import of monitoring libraries
    checker = ImportChecker()
    checker.visit(tree)
    imported_modules = checker.imports

    misuse_detected = False  # Variable to track if any misuse happens

    # Step 2: Check if any relevant package is imported and if its metric is used
    for module, metrics in module_to_metric.items():
        if module in imported_modules:
            print(f"Module '{module}' is imported. Checking usage...")

            if isinstance(metrics, list):  # Handle multiple metrics for boto3
                for metric in metrics:
                    usage_checker = ImportUsageChecker(metric)
                    usage_checker.visit(tree)
                    if not usage_checker.is_used:
                        print(f"Misuse detected: '{metric}' is NOT used despite being imported.")
                        misuse_detected = True
                        break  # Stop further checks if we already detected a misuse
            else:
                usage_checker = ImportUsageChecker(metrics)
                usage_checker.visit(tree)
                if not usage_checker.is_used:
                    print(f"Misuse detected: '{metrics}' is NOT used despite being imported.")
                    misuse_detected = True

            # Special handling for the `requests` module
            if module == "requests":
                print("Module 'requests' is detected. Now verifying if it is used for monitoring ML service limits...")

                for node in ast.walk(tree):
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                        # Check if `requests` is being used and if it's for monitoring ML API limits
                        func_value = node.func.value
                        if isinstance(func_value, ast.Name) and func_value.id == "requests":
                            if is_monitoring_request(node):
                                print(f"No Misuse: 'requests' is used to monitor ML service limits.")
                                break
                else:
                    print("Misuse detected: 'requests' is not used for monitoring ML service limits.")
                    misuse_detected = True

        else:
            # Handle the case where module and its metric are not in `module_to_metric.items()`
            print(f"Misuse detected: '{module}' or its associated metric is not in `module_to_metric.items()`. This is flagged.")
            misuse_detected = True

    # If any misuse has been detected, increment misuse_count by 1
    if misuse_detected:
        misuse_count += 1

    print(f"There are {misuse_count} improper handling ML API limits misuses detected.")
    return misuse_count

def detect_api_limits(tree):
    misuse_count = check_api_limits_in_trees(tree)
    #return {"status": "checked"}
    return {"misuse_count_of_Improper_Handling_ML_API_Limit": misuse_count}

def detect(repo_path):
    return process_repos([repo_path], detect_api_limits)

""""
#need to add the layer of SDK/API
repo_paths = [
    "Python-Azure-AI-REST-APIs/"
]

# Initialize an empty list to collect all misuses and counts
all_repo_misuses = []

# Iterate over each repository
for repo_path in repo_paths:
    print(f"Processing repository: {repo_path}")
    tree = generate_ast_for_repo(repo_path)
    check_api_limits_in_trees(tree)
    
"""