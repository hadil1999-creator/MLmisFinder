#!/usr/bin/env python3
"""

This detector identifies misinterpretation of ML API outputs, particularly focusing on
sentiment analysis APIs where developers incorrectly use only one field (e.g., score)
instead of considering multiple fields together (e.g., both score and magnitude).

"""

from detection.common import *
from detection.output import *
import re


class ImprovedOutputMisinterpreterConfig:
    """Improved configuration with better coverage of sentiment API patterns"""
   
    def __init__(self):
        # Enhanced API patterns with more comprehensive detection
        self.api_patterns = {
            'Google': {
                'sentiment_analysis': {
                    'import_indicators': [
                        r'google\.cloud\.language',
                        r'from\s+google\.cloud\s+import\s+language',
                        r'LanguageServiceClient',
                        r'google-cloud-language',
                        r'language_v1'
                    ],
                    'api_call_patterns': [
                        r'analyze_sentiment\s*\(',
                        r'\.analyze_sentiment\s*\(',
                        r'client\.analyze_sentiment',
                        r'language_client\.analyze_sentiment',
                        r'sentiment_analyze'
                    ],
                    'result_field_patterns': {
                        'score': [
                            r'\.score\b',
                            r'document_sentiment\.score',
                            r'sentiment\.score',
                            r'result\.score',
                            r'response\.score',
                            r'\[[\"\']score[\"\']\]',
                            r'getattr\(.*,\s*["\']score["\']',
                            r'\.get\(\s*["\']score["\']'
                        ],
                        'magnitude': [
                            r'\.magnitude\b',
                            r'document_sentiment\.magnitude',
                            r'sentiment\.magnitude',
                            r'result\.magnitude',
                            r'response\.magnitude',
                            r'\[[\"\']magnitude[\"\']\]',
                            r'getattr\(.*,\s*["\']magnitude["\']',
                            r'\.get\(\s*["\']magnitude["\']'
                        ]
                    },
                    'correct_usage_patterns': [
                        r'score.*magnitude|magnitude.*score',
                        r'abs\s*\(\s*.*score.*\)',
                        r'score.*and.*magnitude',
                        r'magnitude.*and.*score',
                        r'if.*score.*and.*magnitude',
                        r'if.*magnitude.*and.*score'
                    ],
                    'misuse_patterns': [
                        r'if\s+.*\.score\s*[<>=]',
                        r'elif\s+.*\.score\s*[<>=]',
                        r'while\s+.*\.score\s*[<>=]',
                        r'score\s*[<>=]\s*0',
                        r'score\s*[<>=]\s*-?\d+\.?\d*',
                        r'\.score\s*>\s*0',
                        r'\.score\s*<\s*0'
                    ]
                }
            },
            'Azure': {
                'sentiment_analysis': {
                    'import_indicators': [
                        r'azure\.ai\.textanalytics',
                        r'from\s+azure\.ai\.textanalytics',
                        r'TextAnalyticsClient',
                        r'azure-ai-textanalytics',
                        r'azure\.cognitiveservices'
                    ],
                    'api_call_patterns': [
                        r'analyze_sentiment\s*\(',
                        r'\.analyze_sentiment\s*\(',
                        r'client\.analyze_sentiment',
                        r'text_client\.analyze_sentiment',
                        r'begin_analyze_sentiment'
                    ],
                    'result_field_patterns': {
                        'sentiment': [
                            r'\.sentiment\b',
                            r'result\.sentiment',
                            r'response\.sentiment',
                            r'\[[\"\']sentiment[\"\']\]',
                            r'getattr\(.*,\s*["\']sentiment["\']'
                        ],
                        'confidence_scores': [
                            r'\.confidence_scores\b',
                            r'confidence_score',
                            r'result\.confidence_scores',
                            r'response\.confidence_scores',
                            r'\[[\"\']confidence_scores[\"\']\]'
                        ]
                    },
                    'correct_usage_patterns': [
                        r'sentiment.*confidence',
                        r'confidence.*sentiment',
                        r'confidence_scores',
                        r'if.*sentiment.*and.*confidence',
                        r'if.*confidence.*and.*sentiment'
                    ],
                    'misuse_patterns': [
                        r'if\s+.*\.sentiment\s*[<>=]',
                        r'sentiment\s*==\s*["\']positive["\']',
                        r'sentiment\s*==\s*["\']negative["\']',
                        r'sentiment\s*==\s*["\']neutral["\']',
                        r'\.sentiment\s*==',
                        r'\.sentiment\s*!='
                    ]
                }
            },
            'AWS': {
                'sentiment_analysis': {
                    'import_indicators': [
                        r'import\s+boto3',
                        r'boto3\.client',
                        r'comprehend',
                        r'from\s+boto3',
                        r'aws.*comprehend'
                    ],
                    'api_call_patterns': [
                        r'detect_sentiment\s*\(',
                        r'\.detect_sentiment\s*\(',
                        r'client\.detect_sentiment',
                        r'comprehend\.detect_sentiment',
                        r'batch_detect_sentiment'
                    ],
                    'result_field_patterns': {
                        'Sentiment': [
                            r'\.Sentiment\b',
                            r'result\.Sentiment',
                            r'response\.Sentiment',
                            r'\[[\"\']Sentiment[\"\']\]',
                            r'\.get\(\s*["\']Sentiment["\']'
                        ],
                        'SentimentScore': [
                            r'\.SentimentScore\b',
                            r'result\.SentimentScore',
                            r'response\.SentimentScore',
                            r'\[[\"\']SentimentScore[\"\']\]',
                            r'\.get\(\s*["\']SentimentScore["\']'
                        ]
                    },
                    'correct_usage_patterns': [
                        r'Sentiment.*SentimentScore',
                        r'SentimentScore.*Sentiment',
                        r'if.*Sentiment.*and.*SentimentScore',
                        r'if.*SentimentScore.*and.*Sentiment'
                    ],
                    'misuse_patterns': [
                        r'if\s+.*\.Sentiment\s*[<>=]',
                        r'Sentiment\s*==\s*["\']POSITIVE["\']',
                        r'Sentiment\s*==\s*["\']NEGATIVE["\']',
                        r'Sentiment\s*==\s*["\']NEUTRAL["\']',
                        r'\.Sentiment\s*==',
                        r'\.Sentiment\s*!='
                    ]
                }
            }
        }


class ImprovedOutputMisinterpreterVisitor(ast.NodeVisitor):
    """Enhanced visitor for better sentiment API misuse detection"""
   
    def __init__(self, file_path, cloud_provider):
        self.file_path = file_path
        self.cloud_provider = cloud_provider
        self.config = ImprovedOutputMisinterpreterConfig()
        self.misuses = []
       
        # Detection state
        self.has_sentiment_import = False
        self.has_sentiment_api_call = False
        self.api_result_variables = set()
        self.field_usage = {'primary': False, 'secondary': False}
        self.has_correct_usage = False
        self.detected_misuse_patterns = []
       
        # Get provider config
        self.provider_config = self.get_provider_config()
       
    def get_provider_config(self):
        """Get configuration for detected cloud provider"""
        if self.cloud_provider in self.config.api_patterns:
            return self.config.api_patterns[self.cloud_provider]['sentiment_analysis']
        return None
   
    def visit_Import(self, node):
        """Check for sentiment API imports"""
        if not self.provider_config:
            return
           
        for alias in node.names:
            import_name = alias.name
            for pattern in self.provider_config['import_indicators']:
                if re.search(pattern, import_name, re.IGNORECASE):
                    self.has_sentiment_import = True
                    break
       
        self.generic_visit(node)
   
    def visit_ImportFrom(self, node):
        """Check for sentiment API imports with from statement"""
        if not self.provider_config:
            return
           
        if node.module:
            full_import = f"from {node.module} import"
            for pattern in self.provider_config['import_indicators']:
                if re.search(pattern, full_import, re.IGNORECASE):
                    self.has_sentiment_import = True
                    break
       
        self.generic_visit(node)
   
    def visit_Call(self, node):
        """Check for sentiment API calls"""
        if not self.provider_config:
            return
           
        call_str = self.get_call_string(node)
        if call_str:
            for pattern in self.provider_config['api_call_patterns']:
                if re.search(pattern, call_str, re.IGNORECASE):
                    self.has_sentiment_api_call = True
                    break
       
        self.generic_visit(node)
   
    def visit_Assign(self, node):
        """Track API result variable assignments"""
        if not self.provider_config:
            return
           
        # Check if this is assigning a sentiment API result
        if isinstance(node.value, ast.Call):
            call_str = self.get_call_string(node.value)
            if call_str:
                for pattern in self.provider_config['api_call_patterns']:
                    if re.search(pattern, call_str, re.IGNORECASE):
                        # Store the variable that will hold the result
                        if isinstance(node.targets[0], ast.Name):
                            self.api_result_variables.add(node.targets[0].id)
                        break
       
        self.generic_visit(node)
   
    def visit_If(self, node):
        """Analyze if statements for misuse patterns"""
        if not self.provider_config:
            return
           
        condition_str = self.get_node_string(node.test)
        if condition_str:
            self.analyze_condition_for_misuse(condition_str, node.lineno)
       
        self.generic_visit(node)
   
    def visit_While(self, node):
        """Analyze while statements for misuse patterns"""
        if not self.provider_config:
            return
           
        condition_str = self.get_node_string(node.test)
        if condition_str:
            self.analyze_condition_for_misuse(condition_str, node.lineno)
       
        self.generic_visit(node)
   
    def visit_Attribute(self, node):
        """Check for field access patterns"""
        if not self.provider_config:
            return
           
        attr_str = self.get_node_string(node)
        if attr_str:
            # Check for primary field usage (score/sentiment)
            primary_field = list(self.provider_config['result_field_patterns'].keys())[0]
            for pattern in self.provider_config['result_field_patterns'][primary_field]:
                if re.search(pattern, attr_str, re.IGNORECASE):
                    self.field_usage['primary'] = True
                    break
           
            # Check for secondary field usage (magnitude/confidence)
            if len(self.provider_config['result_field_patterns']) > 1:
                secondary_field = list(self.provider_config['result_field_patterns'].keys())[1]
                for pattern in self.provider_config['result_field_patterns'][secondary_field]:
                    if re.search(pattern, attr_str, re.IGNORECASE):
                        self.field_usage['secondary'] = True
                        break
       
        self.generic_visit(node)
   
    def get_call_string(self, node):
        """Get string representation of function call"""
        try:
            if hasattr(ast, 'unparse'):
                return ast.unparse(node)
            else:
                # Fallback for older Python versions
                if isinstance(node.func, ast.Attribute):
                    return f"{node.func.attr}()"
                elif isinstance(node.func, ast.Name):
                    return f"{node.func.id}()"
        except:
            pass
        return None
   
    def get_node_string(self, node):
        """Get string representation of AST node"""
        try:
            if hasattr(ast, 'unparse'):
                return ast.unparse(node)
            else:
                # Fallback - limited functionality
                return str(node)
        except:
            return None
   
    def analyze_condition_for_misuse(self, condition_str, line_number):
        """Analyze condition for sentiment API misuse patterns"""
        # First check if this condition involves our API result variables
        involves_api_result = any(var in condition_str for var in self.api_result_variables)
       
        if not involves_api_result:
            return
       
        # Check for correct usage patterns first
        for pattern in self.provider_config.get('correct_usage_patterns', []):
            if re.search(pattern, condition_str, re.IGNORECASE):
                self.has_correct_usage = True
                return
       
        # Check for misuse patterns
        for pattern in self.provider_config.get('misuse_patterns', []):
            if re.search(pattern, condition_str, re.IGNORECASE):
                self.detected_misuse_patterns.append({
                    'pattern': pattern,
                    'line': line_number,
                    'condition': condition_str
                })
                break
   
    def analyze_file_content(self, file_content):
        """Analyze entire file content for additional patterns"""
        if not self.provider_config:
            return
       
        # Check for correct usage patterns in entire file
        for pattern in self.provider_config.get('correct_usage_patterns', []):
            if re.search(pattern, file_content, re.IGNORECASE):
                self.has_correct_usage = True
                break
       
        # Check for misuse patterns in entire file
        for pattern in self.provider_config.get('misuse_patterns', []):
            if re.search(pattern, file_content, re.IGNORECASE):
                # Find line number
                lines = file_content.split('\n')
                for i, line in enumerate(lines, 1):
                    if re.search(pattern, line, re.IGNORECASE):
                        self.detected_misuse_patterns.append({
                            'pattern': pattern,
                            'line': i,
                            'condition': line.strip()
                        })
                        break
   
    def determine_final_result(self):
        """Determine if there is a misuse based on all evidence"""
        # If no sentiment API usage detected, return no misuse
        if not (self.has_sentiment_import and self.has_sentiment_api_call):
            return False, "No sentiment API usage detected"
       
        # If correct usage patterns are found, no misuse
        if self.has_correct_usage:
            return False, "Correct usage patterns detected"
       
        # If both primary and secondary fields are used, likely correct
        if self.field_usage['primary'] and self.field_usage['secondary']:
            return False, "Both primary and secondary fields used"
       
        # If misuse patterns are detected, it's a misuse
        if self.detected_misuse_patterns:
            return True, f"Misuse patterns detected: {len(self.detected_misuse_patterns)} instances"
       
        # If only primary field used without secondary, likely misuse
        if self.field_usage['primary'] and not self.field_usage['secondary']:
            return True, "Only primary field used without secondary field"
       
        # If API is used but no clear field usage, potential misuse
        if self.has_sentiment_api_call and not (self.field_usage['primary'] or self.field_usage['secondary']):
            return True, "API used but no clear field usage detected"
       
        return False, "Insufficient evidence for misuse"


def analyze_output_misinterpretation_in_repo(trees):
    """Analyze output misinterpretation across repository files"""
    total_misuse_count = 0
    all_misuses = []
   
    for file_path, tree in trees:
        # Detect cloud provider for this file
        cloud_provider = detect_cloud_provider(tree)
       
        if not cloud_provider:
            continue
           
        print(f"Processing file: {file_path} (Provider: {cloud_provider})")
       
        # Create visitor and analyze
        visitor = ImprovedOutputMisinterpreterVisitor(file_path, cloud_provider)
        visitor.visit(tree)
       
        # Also analyze file content for additional patterns
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                file_content = f.read()
                visitor.analyze_file_content(file_content)
        except:
            pass
       
        # Determine result
        is_misuse, reason = visitor.determine_final_result()
       
        if is_misuse:
            misuse_message = f"Output misinterpretation in {file_path}: {reason}"
            all_misuses.append(misuse_message)
            total_misuse_count += 1
            print(f"MISUSE DETECTED: {misuse_message}")
        else:
            print(f"No misuse detected: {reason}")
   
    print(f"Total output misinterpretation occurrences: {total_misuse_count}")
    return total_misuse_count, all_misuses


def detect_output_misinterpretation(tree):
    """
    CORRECTED: This function now accepts a single tree (combined AST)
    and creates the trees structure internally to match other detectors.
    """
    # For consistency with other detectors, we need to handle the case
    # where we get a single combined tree instead of a list of (file_path, tree) tuples
    
    # Create a pseudo-trees structure for compatibility
    trees = [("combined_repo", tree)]
    
    misuse_count, misuses = analyze_output_misinterpretation_in_repo(trees)
   
    # Return in standardized MLMisfinder format
    return {
        "misuse_count_of_Output_Misinterpreter": misuse_count,
        "analysis_result": misuses
    }


def detect(repo_path):
    """Standard MLMisfinder entry point"""
    return process_repos([repo_path], detect_output_misinterpretation)