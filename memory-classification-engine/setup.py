from setuptools import setup, find_packages

setup(
    name="memory-classification-engine",
    version="0.1.0",
    description="A lightweight memory classification engine for AI agents",
    author="lulin70",
    author_email="lulin70@example.com",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "PyYAML",
    ],
    extras_require={
        "api": ["Flask"],
        "llm": ["requests"],
        "testing": ["pytest", "pytest-benchmark"],
        "profiling": ["memory-profiler"],
    },
    entry_points={
        "console_scripts": [
            "memory-engine=memory_classification_engine.cli:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
)