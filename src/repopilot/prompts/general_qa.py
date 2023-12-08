example_qa = """Question: how to subclass and define a custom spherical coordinate frame?\n"
"Plan:\n"
"1. Finding related functions and classes related to spherical coordinate frame, possibly in some folders or files in the project, likely to be in astropy/coordinate/spherical.py \n"
"2. Find its usage in the codebase and use it as a template to define a custom spherical coordinate frame with possible custom methods or fields\n"
"<END_OF_PLAN>\n"
"Example 2:\n"
"Question: how to use Kernel1D class\n"
"Plan:\n"
"1. Find the Kernel1D class in the codebase, use code search tool or explore directory and find that class among possible symbols.\n"
"2. When found, find its usage in the code and use it as a template to use the class. You can find the reference of the class in test cases using find_all_references tool\n"
"<END_OF_PLAN>\n"
"Example 3:\n"
"Question: What are the main components of the backend of danswer and how it works, be specific (roles of main classes and functions for each component). Describe the high level flow of the backend as well.\n"
"Plan:\n
"1. Identify where is backend components inside the repository. Then identify the main classes and functions. This could be done by looking at the files in each directory and understanding their purpose."
"2. Understand the role of each main class and functions. This could be done by reading the code and any associated documentation or comments."
"3. Choose the main classes and functions that relevant then find their usage crossover to find the high level flow of the backend. This can be used with go-to-definition and find_all_references\n"
<END_OF_PLAN>\n
Example 4:\n
Question: what is the purpose of the MPC.get_observations function?\n
Plan:\n
1. Find the MPC.get_observations function using Code Search tool, if the results are too vauge, consider using Semantic Code Search tool\n If the results are not cleared enough, you can navigate the directory using the tree structure tool to find the related files (possibly astroquery/mpc) then use get all symbols tool to find the function
<END_OF_PLAN>\n
Example 5:\n
Question: what does UnigramVisitor do in the textanalysis repo?\n
Plan:\n
1. Find the UnigramVisitor class using Code Search tool, if the results are too vauge, consider using Semantic Code Search tool\n If the results are not cleared enough, you can navigate the directory using the tree structure tool to find the related files (possibly textanalysis/visitor) then use get all symbols tool to find the class
<END_OF_PLAN>\n"""
