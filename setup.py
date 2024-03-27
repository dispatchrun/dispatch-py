from setuptools import Extension, setup

setup(
    ext_modules=[
        Extension(
            name="dispatch.experimental.durable.frame",
            sources=["src/dispatch/experimental/durable/frame.c"],
            include_dirs=["src/dispatch/experimental/durable"],
        ),
    ]
)
