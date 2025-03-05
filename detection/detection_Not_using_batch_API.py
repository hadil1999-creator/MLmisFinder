from detection.common import *
from detection.output import *

# Generate a combined AST for the entire repository
def generate_combined_ast_for_repo(repo_path):
    """Generate a combined AST for the entire repository."""
    combined_body = []  # Collect all AST nodes
    found_files = False

    for root, dirs, files in os.walk(repo_path):
        for file in files:
            if file.endswith(".py"):
                found_files = True
                file_path = os.path.join(root, file)

                try:
                    tree = generate_ast_for_file(file_path)
                    if isinstance(tree, ast.Module):  # Ensure it's an AST module
                        combined_body.extend(tree.body)  # Extract body only
                except Exception as e:
                    print(f"Error processing {file_path}: {e}")

    if not found_files:
        print("No Python (.py) files found in the repository.")

    # Ensure the final AST is correctly structured
    combined_tree = ast.Module(body=combined_body, type_ignores=[])
    BatchAPIDetector().link_parent_nodes(combined_tree)  # Link parent nodes
    return combined_tree  # Return the properly formatted AST




# Visitor class to analyze function calls in the AST
class FunctionCallVisitor(ast.NodeVisitor):
    def __init__(self, file_path, trees):
        self.file_path = file_path  # Store file path for reference in messages
        self.call_count = 0
        self.trees = trees
        self.inside_loop = 0  # Track nested loop depth
        self.misuses = set()  # Set to track unique misuse occurrences

    def visit_For(self, node):
        # Entering a loop increases the loop depth
        self.inside_loop += 1
        # Visit the loop body to check for function calls inside
        self.generic_visit(node)
        # After visiting the loop body, exit the loop and decrease the loop depth
        self.inside_loop -= 1

    def visit_Call(self, node):
        
        detected_provider = detect_cloud_provider(self.trees)

        if detected_provider == 'Azure':
            # Azure ML and Cognitive Services
            services = {
                 "detect_language", "analyze_sentiment","begin_abstract_summary","begin_analyze_actions", "begin_extract_summary","begin_multi_label_classify",
                "begin_recognize_custom_entities","begin_single_label_classify",""
                "extract_key_phrases", "recognize_pii_entities",
                "recognize_entities", "recognize_linked_entities", "analyze_image",
                "describe_image", "recognize_text", "detect_faces", "speech_to_text","describe_image_in_stream",
                "text_to_speech", "speech_translation", "translate_text", "train_model","automl_run","add_face_from_stream"
            }
        elif detected_provider == 'AWS':
            # AWS ML Services
            services = {
                "detect_dominant_language", "detect_sentiment", "detect_key_phrases",
                "detect_entities", "detect_syntax", "detect_labels", "detect_faces",
                "analyze_video", "recognize_celebrities", "translate_text", "text_to_speech",
                "speech_to_text", "train_model", "deploy_model", "automl"
            }
        elif detected_provider == 'Google':
            # Google Cloud AI and ML Services
            services = {
                "analyze_entities", "analyze_sentiment", "analyze_syntax",
                "classify_text", "analyze_entity_sentiment", "label_detection",
                "object_localization", "image_properties", "face_detection",
                "text_detection", "translate_text", "speech_to_text", "text_to_speech",
                "train_model", "deploy_model", "automl", "model_monitoring",
                "custom_model_training", "explainable_ai","long_running_recognize", "translate","synthesize_speech"
            }
        else:
            services = {}

        if isinstance(node.func, ast.Attribute):  # Ensure that func is an Attribute node (method call)
            if node.func.attr in services:  # Check if the method is in the services set
                if isinstance(node.func.value, ast.Name):  # Check if the object is a simple name (e.g., cog_client)
                    argument_type = self.check_argument_type(node)
                    service_name = node.func.attr
                    service_message = f"{service_name}"

                    if self.inside_loop > 0:  # Inside a loop
                        if argument_type == "plural":
                            print(f"Not misuse: '{service_message}' found inside a loop with plural argument at line {node.lineno} of {self.file_path}")
                        else:
                            misuse_message = f"Misuse: '{service_message}' found inside a loop with single argument at line {node.lineno} of {self.file_path}"
                            if misuse_message not in self.misuses:
                                self.misuses.add(misuse_message)
                                print(misuse_message)
                                self.call_count += 1

                    else:  # Outside a loop
                        if argument_type == "plural":
                            print(f"Not misuse: '{service_message}' found outside a loop with plural argument at line {node.lineno} of {self.file_path}")
                        else:
                            print(f"Check context and business requirements for '{service_message}' found outside a loop with single argument at line {node.lineno} of {self.file_path}")

        # Continue visiting child nodes
        self.generic_visit(node)

    def check_argument_type(self, node):
        if node.args:
            arg = node.args[0]
            # Check if argument is a list, tuple, or variable likely representing plural items
            if isinstance(arg, (ast.List, ast.Tuple)):
                return "plural"
            elif isinstance(arg, ast.Name):  # Variable name heuristic
                return "potential_plural" if arg.id.endswith("s") else "single"
        return "single"

    def get_misuses(self):
            return self.misuses  # Return the collected misuses


def analyze_function_calls_in_repo(trees):
    total_misuse_count = 0  # Total occurrences of misuse across all files
    all_misuses = set()  # Store all misuses

    for file_path, tree in trees:
        #print(f"Processing file: {file_path} (AST type: {type(tree)})")  # Debug: Check the type of AST being processed
        visitor = FunctionCallVisitor(file_path, tree)  # Pass single tree
        visitor.visit(tree)
        total_misuse_count += visitor.call_count
        all_misuses.update(visitor.get_misuses())  # Collect misuses

    print(f"Total occurrences of misuse: {total_misuse_count}")
    return total_misuse_count, all_misuses



class BatchAPIDetector(ast.NodeVisitor):
    def __init__(self):
        self.function_defs = {}  # Tracks all function definitions
        self.calls_in_loops = {}  # Functions called inside loops {caller: [called_funcs]}
        self.function_calls = {}  # Function-to-function call mapping
        self.api_calls = set()  # Functions that directly call an API
        self.misuses = []  # List of misuse violations

    def visit_FunctionDef(self, node):
        # Record function definitions and initialize their call lists
        self.function_defs[node.name] = node
        self.function_calls[node.name] = []
        self.generic_visit(node)

    def visit_Call(self, node):
        current_function = self.get_enclosing_function(node)

        # Track function calls
        if current_function:
            if isinstance(node.func, ast.Name):  # Direct call
                self.function_calls[current_function].append(node.func.id)
            elif isinstance(node.func, ast.Attribute):  # Attribute-based call
                self.function_calls[current_function].append(node.func.attr)

            # Check if the call is inside a loop
            if self.is_inside_loop(node):
                if isinstance(node.func, ast.Name):
                    self.calls_in_loops.setdefault(current_function, []).append(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    self.calls_in_loops.setdefault(current_function, []).append(node.func.attr)

        # Detect API calls and potential misuse with 'model_id'
        if self.is_api_call(node):
            self.api_calls.add(current_function)

            # Check for misuse of 'model_id' argument in API calls inside loops
            for keyword in getattr(node, "keywords", []):
                if keyword.arg == "model_id" and self.is_inside_loop(node):
                    self.misuses.append((current_function, "API call with 'model_id' inside a loop"))

        self.generic_visit(node)

    def is_inside_loop(self, node):
        # Ascend the tree to determine if node is inside a loop
        while node:
            if isinstance(node, (ast.For, ast.While)):
                return True
            node = getattr(node, 'parent', None)
        return False

    def is_api_call(self, node):
        # Detect API calls based on known API method names
        api_function_names = {"post", "get", "put", "delete", "begin_analyze_document_from_url"}
        if isinstance(node.func, ast.Attribute):
            return node.func.attr in api_function_names
        return False

    def get_enclosing_function(self, node):
        # Ascend the tree to find the enclosing function
        while node:
            if isinstance(node, ast.FunctionDef):
                return node.name
            node = getattr(node, 'parent', None)
        return None

    def link_parent_nodes(self, node, parent=None):
        # Recursively link parent nodes for traversal
        node.parent = parent
        for child in ast.iter_child_nodes(node):
            self.link_parent_nodes(child, node)

    def propagate_api_calls(self):
        # Propagate API call status through the call graph
        for function, calls in self.function_calls.items():
            for called_func in calls:
                if called_func in self.api_calls:
                    self.api_calls.add(function)

    def detect_batch_misuses(self):
        # Propagate API call status first
        self.propagate_api_calls()

        # Detect misuse of batch APIs
        for caller, called_funcs in self.calls_in_loops.items():
            for called_func in called_funcs:
                if called_func in self.api_calls:
                    self.misuses.append((caller, called_func))

        return self.misuses


def detect_batch(tree):
    if not isinstance(tree, ast.Module):
        raise ValueError(f"Expected an AST Module, but got {type(tree)}")
    detector = BatchAPIDetector()
    detector.link_parent_nodes(tree)  # Ensure parent nodes are linked for traversal
    detector.visit(tree)  # Traverse the tree

    # Detect batch API misuses
    misuses = detector.detect_batch_misuses()

    print(f"Total occurences of Misuses Detected in a linked function: {len(misuses)}")
    #print(f"Misuses Details: {misuses}")
    return misuses, len(misuses)



def detect_function_calls(trees, combined_tree): 
    misuse_count, misuses = analyze_function_calls_in_repo(trees)
    misuses1, additional_misuse_count = detect_batch(combined_tree)

    total_misuse_count = misuse_count + additional_misuse_count
    all_misuses = list(set(misuses).union(misuses1))
    

    # Return the result as a dictionary
    """return {
        "total_misuse_count": total_misuse_count,
        "misuses": all_misuses
    }"""
    return {"misuse_count_of_batch": total_misuse_count, "analysis_result": all_misuses}



def detect(repo_path):
    from detection.output import process_repos
    return process_repos([repo_path], detect_function_calls, save_to_excel=True, file_name="misuses_report.xlsx")

"""""
repo_paths = [
         "Python-Azure-AI-REST-APIs/",
]


# Initialize an empty list to collect all misuses and counts
all_repo_misuses = []

# Iterate over each repository
for repo_path in repo_paths:
    print(f"Processing repository: {repo_path}")
    trees = generate_asts_for_repo(repo_path)
    misuse_count, misuses = analyze_function_calls_in_repo(trees)
    tree = generate_combined_ast_for_repo(repo_path)
    misuses1, additional_misuse_count = detect(tree)

     # Calculate the total misuse count
    total_misuse_count = misuse_count + additional_misuse_count
    # Store the results in the list
    all_repo_misuses.append({
        "repo_path": repo_path,
        "total_misuse_count": total_misuse_count,
        "misuses": list(set(misuses).union(misuses1))
})

print(f"Total misuse occurrences in the repository '{repo_path}' is {total_misuse_count}")


# Optionally, convert the results to a DataFrame for easier analysis
import pandas as pd

misuses_df = pd.DataFrame(all_repo_misuses)

# Print the DataFrame for verification
print(misuses_df['misuses'])
# Assuming misuses_df is your DataFrame
import pandas as pd

# Define the file path where you want to save the Excel file
file_path = 'misuses_report.xlsx'

# Save the DataFrame to an Excel file
misuses_df.to_excel(file_path, index=False, sheet_name='Misuses_Report')

print(f"Data saved to {file_path}")
"""