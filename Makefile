.PHONY: install test typecheck unittest dev fmt fmt-check generate clean update-proto coverage

PYTHON := python

all: test

install:
	$(PYTHON) -m pip install -e .

dev:
	$(PYTHON) -m pip install -e .[dev]

fmt:
	$(PYTHON) -m isort .
	$(PYTHON) -m black .

fmt-check:
	@$(PYTHON) -m isort . --check --diff; isort_status=$$?; \
	$(PYTHON) -m black . --check --diff; black_status=$$?; \
    exit $$((isort_status + black_status))

typecheck:
	$(PYTHON) -m mypy src tests

unittest:
	$(PYTHON) -m unittest discover

coverage: typecheck
	coverage run -m unittest discover
	coverage html -d .coverage-html
	coverage report

test: typecheck unittest

.proto:
	mkdir -p $@

.proto/dispatch-sdk: .proto
	buf export buf.build/stealthrocket/dispatch-sdk --output=.proto/dispatch-sdk

update-proto:
	$(MAKE) clean
	find . -type f -name '*_pb2*.py*' -exec rm  {} \;
	$(MAKE) generate

generate: .proto/dispatch-sdk
	buf generate --template buf.gen.yaml
	cd src && find . -type d | while IFS= read -r dir; do touch $$dir/__init__.py; done
	rm src/__init__.py
	$(MAKE) fmt

clean:
	rm -rf .proto
	rm -rf .coverage
	rm -rf .coverage-html
	find . -type f -name '*.pyc' -exec rm {} \;
	find . -type d -name '__pycache__' -exec rm -r {} \;
