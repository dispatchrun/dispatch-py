.PHONY: install test

PYTHON := python

all: test

install:
	$(PYTHON) -m pip install -e .

test:
	$(PYTHON) -m unittest discover
