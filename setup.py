from setuptools import setup, find_packages
import os

with open('requirements.txt') as f:
    required = f.read().splitlines()

VERSION = '0.0.1' 
# Setting up
setup(
        name="hyperagent", 
        version=VERSION,
        author="Huy Phan Nhat",
        author_email="HuyPN16@fpt.com",
        packages=find_packages(where="src"),
        package_dir={'': 'src'},
        install_reqs = required,
        # needs to be installed along with your package. Eg: 'caer'
        entry_points={"console_scripts": ['hyperagent = hyperagent.cli.cli:app',],},
)