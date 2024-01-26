.PHONY: install test

PYTHON := python

all: test

install:
	export PIP_EXTRA_INDEX_URL=https://buf.build/gen/python
	$(PYTHON) -m pip install -e .

dev:
	export PIP_EXTRA_INDEX_URL=https://buf.build/gen/python
	$(PYTHON) -m pip install -e .[dev]

fmt:
	$(PYTHON) -m black .

test:
	$(PYTHON) -m unittest discover
