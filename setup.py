"""Setup the module.
Resources to build this:
    https://packaging.python.org/en/latest/distributing.html
    https://github.com/pypa/sampleproject
"""
from setuptools import setup, find_packages


setup_args = {
    'name': 'easylogger',
    'version': '0.1.0',
    'cmdclass': '',
    'license': 'MIT',
    'description': 'A relatively simple logging configuration with just enough customization '
                   'for my projects\' needs.',
    'url': 'https://github.com/barretobrock/easylogger',
    'author': 'Barret Obrock',
    'author_email': 'bobrock@tuta.io',
    'packages': find_packages(exclude=['tests'])
}

setup(**setup_args)
