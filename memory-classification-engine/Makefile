# Makefile for Memory Classification Engine

# Python version
PYTHON ?= python3

# Directories
SRC_DIR = src
TEST_DIR = tests

# Targets
.PHONY: all install test lint format clean build

all: install test lint

install:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e .

install-dev:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e "[dev]"

install-test:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e .
	$(PYTHON) -m pip install pytest pytest-benchmark

install-lint:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install flake8 black isort

install-build:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install build twine

test:
	$(PYTHON) -m pytest $(TEST_DIR)/ -v

test-coverage:
	$(PYTHON) -m pytest $(TEST_DIR)/ --cov=$(SRC_DIR) --cov-report=html

lint:
	$(PYTHON) -m flake8 $(SRC_DIR)/ $(TEST_DIR)/ --count --select=E9,F63,F7,F82 --show-source --statistics
	$(PYTHON) -m flake8 $(SRC_DIR)/ $(TEST_DIR)/ --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics

format:
	$(PYTHON) -m black $(SRC_DIR)/ $(TEST_DIR)/
	$(PYTHON) -m isort $(SRC_DIR)/ $(TEST_DIR)/

format-check:
	$(PYTHON) -m black --check $(SRC_DIR)/ $(TEST_DIR)/
	$(PYTHON) -m isort --check-only $(SRC_DIR)/ $(TEST_DIR)/

build:
	$(PYTHON) -m build

check-package:
	$(PYTHON) -m twine check dist/*

clean:
	rm -rf dist/
	rm -rf build/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	find . -name "__pycache__" -type d -exec rm -rf {} \;
