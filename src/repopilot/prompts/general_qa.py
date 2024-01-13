example_qa = """Question: how to subclass and define a custom spherical coordinate frame?
Plan:
1. Finding related functions and classes related to spherical coordinate frame, possibly in some folders or files in the project, likely to be in astropy/coordinate/spherical.py 
2. Find its usage in the codebase and use it as a template to define a custom spherical coordinate frame with possible custom methods or fields
<END_OF_PLAN>
Question: What is the main difference between "modules_to_save" and "target_modules"? 
Plan:
1. Use the code_search tool to find the definitions of "modules_to_save" and "target_modules" in the codebase.
2. Use the find_all_references tool to find all the references of "modules_to_save" and "target_modules" in the codebase to understand their usages.
<END_OF_PLAN>
"""
