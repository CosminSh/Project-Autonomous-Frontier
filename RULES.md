# Project Rules & Coding Standards

## 1. Modular and Maintainable Code
- **Small, Focused Files:** Keep logic separated into many small, distinct files. This significantly improves maintainability and readability.
- **File Size Limits:** Avoid creating code files that exceed 500 lines. Whenever possible, strive to keep files under 200 lines. 
- **DRY Principle (Don't Repeat Yourself):** Do not duplicate code. If you find yourself writing the same logic in multiple places, extract it into a separate helper or utility function.
- **Helper Functions & Utilities:** Create dedicated helper files for shared functions. Call these extracted functions from the appropriate modules instead of rewriting the same logic.
