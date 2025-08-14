from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="risklive",
    version="0.1.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="A live risk analysis dashboard for the nuclear industry",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/risklive",
    packages=find_packages(exclude=["tests", "notebooks"]),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.9",
    install_requires=[
        "altair>=5.3.0",
        "APScheduler>=3.10.4",
        "beautifulsoup4>=4.12.3",
        "bertopic>=0.16.3",
        "Flask>=3.0.3",
        "httpx>=0.27.0",
        "matplotlib>=3.9.1",
        "nltk>=3.8.1",
        "numpy>=1.26.4",
        "openai>=1.36.1",
        "pandas>=2.2.2",
        "plotly==5.22.0",
        "python-dotenv>=1.0.1",
        "PyYAML>=6.0.1",
        "requests>=2.32.3",
        "scikit-learn>=1.5.1",
        "scipy>=1.14.0",
        "seaborn>=0.13.2",
        "sentence-transformers>=3.0.1",
        "streamlit>=1.36.0",
        "torch>=2.3.1",
        "transformers>=4.42.4",
        "streamlit-analytics2"
    ],
    extras_require={
        "dev": [
            "pytest",
            "pytest-cov",
            "flake8",
            "black",
            "mypy",
        ],
    },
    entry_points={
        "console_scripts": [
            "risklive=risklive.server.app:main",
        ],
    },
)