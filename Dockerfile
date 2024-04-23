FROM python:3.12
WORKDIR /usr/src/dispatch-py

COPY pyproject.toml .
RUN python -m pip install -e .[dev]

COPY . .
RUN python -m pip install -e .[dev]

ENTRYPOINT ["python"]
