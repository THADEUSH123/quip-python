"""Template of a setup script for a python project."""

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

config = {
    'description': 'Client library for quip.com API in py3.',
    'author': 'Thadeus Hickman',
    'url': 'github.com/THADEUSH123/quip-python',
    'download_url': 'github.com/THADEUSH123/quip-python',
    'author_email': 'thadeus.hickman@gmail.com',
    'version': '2.0',
    'install_requires': ['nose'],
    'packages': ['quip'],
    'scripts': [],
    'name': 'quip'
}

setup(**config)
