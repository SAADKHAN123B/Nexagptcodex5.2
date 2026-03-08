"""NexaCode — AI-Powered Terminal Coding Assistant"""
from setuptools import setup, find_packages

setup(
    name="nexacode",
    version="3.3.0",
    description="AI-Powered Terminal Coding Assistant — Like Claude Code for your terminal",
    long_description=open("README.md").read() if __import__("os").path.exists("README.md") else "",
    long_description_content_type="text/markdown",
    author="NexaCode Team",
    python_requires=">=3.9",
    packages=find_packages(),
    install_requires=[
        "rich>=13.7.0",
        "prompt_toolkit>=3.0.43",
        "httpx>=0.27.0",
        "aiosqlite>=0.19.0",
        "pyyaml>=6.0.1",
        "python-dotenv>=1.0.0",
        "pygments>=2.17.0",
    ],
    entry_points={
        "console_scripts": [
            "nexacode=nexacode:entry_point",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Code Generators",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
