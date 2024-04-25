.PHONY: install test typecheck unittest dev fmt fmt-check generate clean update-proto coverage build check push push-test

PYTHON := python

ifdef PROTO_VERSION
PROTO_TARGET := buf.build/stealthrocket/dispatch-proto:$(PROTO_VERSION)
else
PROTO_TARGET := buf.build/stealthrocket/dispatch-proto
endif


all: test

install:
	$(PYTHON) -m pip install -e .

dev:
	$(PYTHON) -m pip install -e .[dev]

lambda:
	$(PYTHON) -m pip install -e .[lambda]

fmt:
	$(PYTHON) -m isort .
	$(PYTHON) -m black .

fmt-check:
	@$(PYTHON) -m isort . --check --diff; isort_status=$$?; \
	$(PYTHON) -m black . --check --diff; black_status=$$?; \
    exit $$((isort_status + black_status))

typecheck:
	$(PYTHON) -m mypy --check-untyped-defs src tests examples

unittest:
	$(PYTHON) -m pytest tests

exampletest:
	$(PYTHON) -m pytest examples

coverage: typecheck
	coverage run -m unittest discover
	coverage html -d .coverage-html
	coverage report

test: typecheck unittest

.proto:
	mkdir -p $@

.proto/dispatch-proto: .proto
	buf export $(PROTO_TARGET) --output=.proto/dispatch-proto

update-proto:
	$(MAKE) clean
	find . -type f -name '*_pb2*.py*' -exec rm  {} \;
	$(MAKE) generate

generate: .proto/dispatch-proto
	buf generate --template buf.gen.yaml
	cd src && find . -type d | while IFS= read -r dir; do touch $$dir/__init__.py; done
	rm src/__init__.py
	$(MAKE) fmt

clean:
	$(RM) -r dist .proto .coverage .coverage-html
	find . -type f -name '*.pyc' | xargs $(RM) -r
	find . -type d -name '__pycache__' | xargs $(RM) -r

build:
	$(PYTHON) -m build

check:
	twine check dist/*

push:
	twine upload dist/*

push-test:
	twine upload -r testpypi dist/*


docs-deps: dev
	$(PYTHON) -m pip install .[docs]

local-docs: docs-deps
	mkdocs serve
