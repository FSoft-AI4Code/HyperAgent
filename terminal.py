import subprocess
import selectors
import os
import sys
from repopilot.tools.exec_tools import InteractiveShellSession

ISS = InteractiveShellSession()
ISS.initialize()
ISS.command("echo 'Hello, World!'")
ISS.command(f"source ~/.zshrc")

while True:
    # Read input from the user
    user_input = input("> ")

    # Exit the loop if the user types 'exit'
    if user_input.strip().lower() == 'exit':
        break
    
    output = ISS.command(user_input)
    print(output)