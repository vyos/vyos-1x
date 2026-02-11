#!/usr/bin/env python3
"""
Safe Refactoring Framework for WWAN State Machine
Provides comparison testing and rollback capabilities
"""

import logging
import functools
import traceback
from typing import Any, Callable, Dict, List, Optional
import json

logger = logging.getLogger(__name__)

class RefactoringFramework:
    """Framework for safe method extraction with comparison testing"""

    def __init__(self):
        self.comparison_results = []
        self.enable_comparisons = True
        self.enable_new_methods = True

    def safe_extract(self, original_method_name: str, log_differences: bool = True):
        """Decorator for safe method extraction with comparison"""
        def decorator(new_method: Callable):
            @functools.wraps(new_method)
            def wrapper(*args, **kwargs):
                if not self.enable_new_methods:
                    # Fallback to original method
                    original_method = getattr(args[0], f"{original_method_name}_original")
                    return original_method(*args[1:], **kwargs)

                try:
                    # Call new method
                    new_result = new_method(*args, **kwargs)

                    if self.enable_comparisons:
                        try:
                            # Call original method for comparison
                            original_method = getattr(args[0], f"{original_method_name}_original")
                            old_result = original_method(*args[1:], **kwargs)

                            # Compare results
                            if self._compare_results(new_result, old_result):
                                if log_differences:
                                    logger.info(f"✅ {original_method_name}: Results match")
                            else:
                                logger.warning(f"⚠️ {original_method_name}: Results differ!")
                                if log_differences:
                                    self._log_difference(original_method_name, old_result, new_result)

                        except Exception as e:
                            logger.error(f"Comparison failed for {original_method_name}: {e}")

                    return new_result

                except Exception as e:
                    logger.error(f"New method {original_method_name} failed: {e}")
                    if self.enable_comparisons:
                        # Fallback to original
                        logger.info(f"Falling back to original {original_method_name}")
                        original_method = getattr(args[0], f"{original_method_name}_original")
                        return original_method(*args[1:], **kwargs)
                    raise

            return wrapper
        return decorator

    def _compare_results(self, new_result: Any, old_result: Any) -> bool:
        """Compare two results for equality"""
        try:
            if type(new_result) != type(old_result):
                return False

            if isinstance(new_result, (dict, list)):
                return json.dumps(new_result, sort_keys=True) == json.dumps(old_result, sort_keys=True)
            else:
                return new_result == old_result
        except:
            return False

    def _log_difference(self, method_name: str, old_result: Any, new_result: Any):
        """Log differences between old and new results"""
        logger.warning(f"Difference in {method_name}:")
        logger.warning(f"  Old: {old_result}")
        logger.warning(f"  New: {new_result}")

        self.comparison_results.append({
            'method': method_name,
            'old_result': old_result,
            'new_result': new_result,
            'timestamp': logger.handlers[0].format(logging.LogRecord(
                name=logger.name, level=logging.INFO, pathname='', lineno=0,
                msg='', args=(), exc_info=None
            ))
        })

    def get_comparison_report(self) -> Dict:
        """Get summary of all comparison results"""
        return {
            'total_comparisons': len(self.comparison_results),
            'differences_found': len([r for r in self.comparison_results if r['old_result'] != r['new_result']]),
            'results': self.comparison_results
        }

    def disable_comparisons(self):
        """Disable comparison testing (performance mode)"""
        self.enable_comparisons = False

    def enable_new_methods_only(self):
        """Use only new methods (after validation)"""
        self.enable_comparisons = False
        self.enable_new_methods = True

    def rollback_to_original(self):
        """Emergency rollback to original methods"""
        self.enable_new_methods = False
        logger.critical("🚨 ROLLBACK: Using original methods only")

# Global refactoring framework instance
refactoring_framework = RefactoringFramework()

def safe_extraction(original_method_name: str):
    """Decorator for safe method extraction"""
    return refactoring_framework.safe_extract(original_method_name)

if __name__ == "__main__":
    print("=== WWAN Refactoring Framework ===")
    print("Features:")
    print("- Safe method extraction with comparison")
    print("- Automatic fallback on errors")
    print("- Rollback capabilities")
    print("- Comparison reporting")