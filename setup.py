"""Setup the module.
Resources to build this:
    https://packaging.python.org/en/latest/distributing.html
    https://github.com/pypa/sampleproject
"""
from setuptools import setup, find_packages
import versioneer
from config import config_dict


setup_args = {
    'version': versioneer.get_version(),
    'cmdclass': versioneer.get_cmdclass(),
    'packages': find_packages(exclude=['tests'])
}
setup_args.update(config_dict)

setup(**setup_args)
