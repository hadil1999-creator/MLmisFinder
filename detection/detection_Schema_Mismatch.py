
from detection.common import *
from detection.output import *

class DatasetAnalyzer(ast.NodeVisitor):
    def __init__(self):
        # To track train and test data pairs
        self.train_data = []
        self.test_data = []
        self.train_test_split_results = []

    def visit_Assign(self, node):
        # Debugging: print the node to inspect its structure
        #print("Visiting Assign Node:", ast.dump(node, indent=4))

        # Check if the assignment is unpacking a result from train_test_split
        if isinstance(node.value, ast.Call):
            func_name = node.value.func.id if isinstance(node.value.func, ast.Name) else None

            # Handle train_test_split specifically
            if func_name == 'train_test_split':
                # Extract the variables on the left-hand side of the assignment (e.g., x1_train, y1_train)
                if isinstance(node.targets[0], ast.Tuple):
                    # Extract variable names from the tuple on the left-hand side of the assignment
                    assigned_vars = [target.id for target in node.targets[0].elts if isinstance(target, ast.Name)]
                    if len(assigned_vars) == 4:
                        # Expecting something like: (x1_train, y1_train, x1_test, y1_test)
                        self.train_test_split_results.append(tuple(assigned_vars))  # Store as a tuple

        # Call generic_visit to visit any other nodes
        self.generic_visit(node)


    def visit_Call(self, node):
        # Check if the function being called is related to training or testing
        if isinstance(node.func, ast.Attribute):
            func_name = node.func.attr

            # Detect training functions
            train_methods = ['train', 'fit', 'train_model', 'start_training', 'train_input', 'fit_model']
            # Detect testing functions
            test_methods = ['predict', 'evaluate', 'test', 'predict_model', 'evaluate_model', 'deploy']

            # If it's a training method, capture the arguments (train data)
            if func_name in train_methods:
                arguments = [arg.id for arg in node.args if isinstance(arg, ast.Name)]
                if arguments:
                    self.train_data.extend(arguments)  # Add train data to the list

            # If it's a testing method, capture the arguments (test data)
            if func_name in test_methods:
                arguments = [arg.id for arg in node.args if isinstance(arg, ast.Name)]
                if arguments:
                    self.test_data.extend(arguments)  # Add test data to the list

        self.generic_visit(node)

    def analyze(self, tree):
        self.visit(tree)
        if (len(self.train_data) != 0 and len(self.test_data) != 0) or (len(self.train_test_split_results) != 0):
            return True
        return False  # It's good practice to return something even if the condition isn't met

        #return {train_data": self.train_data,"test_data": self.test_data,"train_test_split_results": self.train_test_split_results}


class ProviderFunctionVisitor(ast.NodeVisitor):
    def __init__(self, cloud_provider):
        """
        Initialize the visitor for schema mismatch testing based on the cloud provider.
        """
        self.cloud_provider = cloud_provider.lower()
        self.is_imported = False
        self.is_used = False
        self.libraries = self._get_libraries_and_functions()

    def _get_libraries_and_functions(self):
        """
        Returns a mapping of libraries and their validation functions for schema mismatch
        testing, based on the cloud provider.
        """
        return {
            "azure": {"library": "azureml.dataprep", "function": "validate_schema"},
            "google": {"library": "tensorflow_data_validation", "function": "validate_statistics"},
            "aws": {"library": "databrew", "function": "validate_recipe"}
        }.get(self.cloud_provider, {})

    def visit_Import(self, node):
        """
        Check if the relevant library is imported.
        """
        for alias in node.names:
            if alias.name == self.libraries.get("library"):
                self.is_imported = True
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        """
        Check if the relevant library is imported with `from ... import ...` syntax.
        """
        if node.module == self.libraries.get("library"):
            self.is_imported = True
        self.generic_visit(node)

    def visit_Call(self, node):
        """
        Check if the relevant schema validation function is called.
        """
        if self.is_imported:
            library_function = self.libraries.get("function")
            if isinstance(node.func, ast.Attribute) and node.func.attr == library_function:
                self.is_used = True
        self.generic_visit(node)


class SchemaCheckVisitor(ast.NodeVisitor):
    def __init__(self,train_data,test_data):
        """
        Initialize with train_data and test_data, which are lists of train and test variables respectively.
        """
        self.schema_checks = []  # To store schema comparison details
        self.assignments = {}    # Map variable names to their assigned AST nodes
        self.train_data = train_data
        self.test_data = test_data

    def visit_Assign(self, node):
        """
        Track assignments in the code.
        """
        if isinstance(node.targets[0], ast.Name):
            var_name = node.targets[0].id
            self.assignments[var_name] = node.value
        self.generic_visit(node)

    def visit_Compare(self, node):
        """
        Check if a comparison involves variables, attributes, or subscript access from self.train_data
        and self.test_data (or vice versa).
        """
        def extract_base_variable(node):
            """
            Recursively extract the base variable from an AST node.
            """
            if isinstance(node, ast.Name):
                return node.id
            elif isinstance(node, ast.Attribute):
                return extract_base_variable(node.value)
            elif isinstance(node, ast.Subscript):
                return extract_base_variable(node.value)
            return None

        # Extract left and right base variables
        left_var = extract_base_variable(node.left)
        right_var = extract_base_variable(node.comparators[0]) if node.comparators else None

        # Check for cross train-test comparisons
        if left_var and right_var:
            if ((left_var in self.train_data and right_var in self.test_data) or
                (left_var in self.test_data and right_var in self.train_data)):
                self.schema_checks.append({
                    "train_var": left_var if left_var in self.train_data else right_var,
                    "test_var": right_var if right_var in self.test_data else left_var,
                    "comparison": ast.dump(node)
                })

        self.generic_visit(node)



    def visit_FunctionDef(self, node):
        """
        Skip trivial or empty functions when traversing.
        """
        if self.is_empty_or_trivial(node):
            return  # Skip trivial functions
        self.generic_visit(node)

    def is_empty_or_trivial(self, node):
        """
        Check if a function is trivial or empty.
        """
        if not node.body:
            return True

        for stmt in node.body:
            if isinstance(stmt, ast.Return):
                if stmt.value is None or (isinstance(stmt.value, ast.Constant) and stmt.value.value in [True, False]):
                    return True
        return False

    def analyze(self, tree):
        """
        Analyze the given AST tree for schema checks.
        """
        self.visit(tree)
        return self.schema_checks


def analyze_code(tree):
        cloud_provider = detect_cloud_provider(tree)
        misuse_count =0
        schema_check_found = False
        provider_keyword_check_found=False


        # Initialize visitors
        analyzer = DatasetAnalyzer()
        train_test_data = analyzer.train_test_split_results
        train_data = analyzer.train_data
        test_data = analyzer.test_data

    # Step 3: Check schema comparisons
        schema_test_identifier = SchemaCheckVisitor(train_data,test_data)
        provider_function_visitor = ProviderFunctionVisitor(cloud_provider)

        # Visit the parsed tree with each visitor
        analyzer.visit(tree)
        #provider_function_visitor.visit(tree)
        schema_test_identifier.visit(tree)

        # Step 1: Test Data Analysis
        print("Test Data Analysis:")


        if analyzer.analyze(tree):
            print("Both training and testing data are present.")

            # Step 2:Import Analysis based on detected cloud provider
            print("\nImport Analysis:")
            if  provider_function_visitor.is_imported:
                if cloud_provider == 'Azure':
                    print("azureml.dataprep is imported.")
                    if  provider_function_visitor.is_used:
                        print("validate_schema is used in the code.")
                        provider_keyword_check_found=True
                    else:
                        print("validate_schema is not used in the code. Misuse detected.")

                elif cloud_provider == 'Google':
                    print("tensorflow_data_validation is imported.")
                    if  provider_function_visitor.is_used:
                        print("validate_statistics is used in the code.")
                        provider_keyword_check_found=True
                    else:
                        print("validate_statistics is not used in the code. Misuse detected.")
                elif cloud_provider == 'AWS':
                    print("databrew is imported.")
                    if  provider_function_visitor.is_used:
                        print("validate_recipe is used in the code.")
                        provider_keyword_check_found=True
                    else:
                        print("validate_recipe is not used in the code. Misuse detected.")
            else:
                print(f"{cloud_provider} validation tool is not imported. Misuse detected.")

                # Step 3: Output Schema Test Result
                final_result = []

                for node in [n for n in tree.body if isinstance(n, ast.FunctionDef)]:
                    if not schema_test_identifier.is_empty_or_trivial(node):
                        # Proceed with schema check analysis for non-trivial functions
                        result = f"\nAnalyzing function: {node.name}"
                        if schema_test_identifier.schema_checks:
                            result += "\nSchema checks found:"
                            for check in schema_test_identifier.schema_checks:
                                result += f"\n{ast.dump(check)}"
                            schema_check_found = True
                        else:
                            result += "\nNo schema checks found."
                    else:
                        result = f"\nFunction {node.name} is trivial or empty. No testing schema"

                    final_result.append(result)                 

                if not schema_check_found and not provider_keyword_check_found:
                    misuse_count += 1

        else:
            print("No test or train data found. Misuse detected.")
            misuse_count += 1

        print(f"There are {misuse_count} Ignore testing schema mimsatch misuses detected")
        return misuse_count

def detect_schema_misuse(tree):
    misuse_count = analyze_code(tree)
    return {"misuse_count_of_Testing_Schema_Mismatch": misuse_count}

def detect(repo_path):
    return process_repos([repo_path], detect_schema_misuse, save_to_excel=True, file_name="misuses_report.xlsx")
