.PHONY: install test

PYTHON := python

all: test

install:
	export PIP_EXTRA_INDEX_URL=https://buf.build/gen/python
	$(PYTHON) -m pip install -e .

test:
	$(PYTHON) -m unittest discover
