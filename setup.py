"""Template of a setup script for a python project."""

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

config = {
    'description': 'Interact with the Quip.com API.',
    'author': 'Thadeus Hickman',
    'url': 'URL to get it at.',
    'download_url': 'Where to download it.',
    'author_email': 'thadeus.hickman@gmail.com',
    'version': '0.1',
    'install_requires': ['nose'],
    'packages': ['quip'],
    'scripts': [],
    'name': 'quip'
}

setup(**config)
