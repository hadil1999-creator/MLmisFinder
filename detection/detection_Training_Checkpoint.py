
from detection.common import *
from detection.output import *


class SDKImportAnalyzer(ast.NodeVisitor):
    """
    Analyzes SDK-specific imports in a given AST.
    """

    def __init__(self, sdk_imports: Dict[str, List[str]]):
        self.sdk_imports = sdk_imports
        self.detected_sdk = "None - an API is used"

    def visit_Import(self, node: ast.Import):
        self._analyze_imports(node.names)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        self._analyze_imports(node.names)
        self.generic_visit(node)

    def _analyze_imports(self, aliases):
        for alias in aliases:
            for sdk, keywords in self.sdk_imports.items():
                if any(keyword in alias.name for keyword in keywords):
                    self.detected_sdk = sdk
                    return  # Exit early once an SDK is detected


class CheckpointUsageAnalyzer(ast.NodeVisitor):
    """
    Analyzes checkpoint-related function calls in a given AST.
    """

    def __init__(self, checkpoint_keywords: List[str]):
        self.checkpoint_keywords = checkpoint_keywords
        self.usage = {
            "checkpoint_used": False,
            "checkpoint_restored": False,
            "misuse_detected": False,
        }

    def visit_Call(self, node: ast.Call):
        func_name = CheckpointMisuseDetector.get_function_name(node.func)
        if any(keyword in func_name for keyword in self.checkpoint_keywords):
            self.usage["checkpoint_used"] = True
            if "restore" in func_name or "load" in func_name:
                self.usage["checkpoint_restored"] = True
        self.generic_visit(node)


class CheckpointMisuseDetector:
    def __init__(self, repo_ast: ast.Module):
        """
        Initializes the detector with a single AST representing the entire repository.
        """
        self.repo_ast = repo_ast
        self.sdk_imports = {
            "azure": ["azureml.core", "azureml.train"],
            "google": ["google.cloud", "tensorflow"],
            "aws": ["sagemaker","boto3"],
        }
        self.checkpoint_functions = {
            "azure": ["outputs", "torch.save", "torch.load"],
            "google": ["ModelCheckpoint", "load_weights", "save_weights"],
            "aws": ["/opt/ml/checkpoints", "checkpoint_s3_uri"],
        }

    @staticmethod
    def get_function_name(node):
        """
        Extracts the function name from an AST node.
        :param node: AST node representing a function call.
        :return: The function name as a string.
        """
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            # Recursively build the full attribute name (e.g., torch.save)
            value = CheckpointMisuseDetector.get_function_name(node.value)
            return f"{value}.{node.attr}" if value else node.attr
        return ""

    def analyze_imports(self, tree: ast.Module) -> str:
        """
        Uses a visitor to analyze the SDK context from imports.
        :param tree: AST of a Python file.
        :return: Detected SDK (azure, google, aws) or "None - an API is used".
        """
        analyzer = SDKImportAnalyzer(self.sdk_imports)
        analyzer.visit(tree)
        return analyzer.detected_sdk

    def analyze_checkpoint_usage(self, sdk: str, tree: ast.Module) -> Dict[str, bool]:
        """
        Uses a visitor to analyze checkpoint-related function calls.
        :param sdk: Detected SDK (azure, google, aws).
        :param tree: AST of a Python file.
        :return: Dictionary indicating checkpoint usage and potential misuse.
        """
        checkpoint_keywords = self.checkpoint_functions.get(sdk, [])
        analyzer = CheckpointUsageAnalyzer(checkpoint_keywords)
        analyzer.visit(tree)

        # Determine misuse based on analysis
        if not analyzer.usage["checkpoint_used"] and not analyzer.usage["checkpoint_restored"]:
            analyzer.usage["misuse_detected"] = True

        elif analyzer.usage["checkpoint_used"] and not analyzer.usage["checkpoint_restored"]:
            analyzer.usage["misuse_detected"] = True

        return analyzer.usage

    def detect_misuse(self):
        """
        Detects misuse of training checkpoints across the single AST of the repository.
        """
        results = []
        try:
            sdk = self.analyze_imports(self.repo_ast)

            # If no SDK is found, return early without checking checkpoint usage
            if sdk == "None - an API is used":
                results.append({"sdk": sdk, "status": "Not Applicable"})
                return results  # Exit early

            # If SDK is found, proceed with checkpoint usage analysis
            usage = self.analyze_checkpoint_usage(sdk, self.repo_ast)
            results.append(
                {
                    "sdk": sdk,
                    "checkpoint_used": usage["checkpoint_used"],
                    "checkpoint_restored": usage["checkpoint_restored"],
                    "misuse_detected": usage["misuse_detected"],
                }
            )
        except Exception as e:
            results.append({"error": str(e)})

        return results

"""""
def detect_checkpoint_misuse(tree):
    detector = CheckpointMisuseDetector(tree)
    report = detector.detect_misuse()
    return {"misuse_report": report}
"""""

def detect_checkpoint_misuse(tree):
    detector = CheckpointMisuseDetector(tree)
    report = detector.detect_misuse()

    # Count the number of misuses (e.g., where misuse_detected is True)
    misuse_count = len([entry for entry in report if entry.get("misuse_detected") is True])

    # Return the misuse count and the analysis result in the required format
    return {
        "misuse_count_of_Training_Checkpoint": misuse_count,
        "analysis_result": report
    }

def detect(repo_path):
    return process_repos([repo_path], detect_checkpoint_misuse)
"""
repo_paths = [
    "Python-Azure-AI-REST-APIs/"
]

# Iterate over each repository
for repo_path in repo_paths:
    print(f"Processing repository: {repo_path}")
    tree = generate_ast_for_repo(repo_path)
    detector = CheckpointMisuseDetector(tree)
    report = detector.detect_misuse()
    for result in report:
      print(result)
"""
