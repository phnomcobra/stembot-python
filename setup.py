"""A setuptools based setup module."""
import pathlib
from setuptools import setup, find_packages

here = pathlib.Path(__file__).parent.resolve()

# Get the long description from the README file
long_description = (here / "README.md").read_text(encoding="utf-8")

setup(
    name="stembot",
    version="0.1.0",
    url="https://github.com/phnomcobra/stembot-python",
    author="Justin Dierking",
    author_email="phnomcobra@gmail.com",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    package_dir={"stembot": "stembot"},
    long_description=long_description,
    packages=find_packages(),
    install_requires=[
        "requests==2.32.4",
        "cherrypy==18.8.0",
        "pycryptodome==3.21.0",
        "pydantic==2.10.6",
        "devtools==0.12.2"
    ],
    extras_require={"build": ["pytest", "build"]},
    python_requires=">=3.10, <4",
    entry_points={
        "console_scripts": [
            "agt.configure=stembot.configure:main",
            "agt.server=stembot.server:main",
            "agt.control=stembot.control:main",
        ],
    },
    project_urls={
        "Bug Reports": "https://github.com/phnomcobra/stembot-python/issues",
        "Source": "https://github.com/phnomcobra/stembot-python"
    },
)