from setuptools import setup, find_packages
import dirrepl as package

setup(
    name='DirectoryReplication',
    version=package.__version__,
    description=package.__description__,
    packages=find_packages(include=['dirrepl', 'dirrepl.*']),
    install_requires=[
        'dirsync==2.2.5',
        'watchdog>=2.1.6',
    ]
)
