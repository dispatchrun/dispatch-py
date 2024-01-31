from setuptools import Extension, setup

setup(
    ext_modules=[
        Extension(
            name="dispatch.experimental.durable._frame",
            sources=["src/dispatch/experimental/durable/_frame.c"],
        ),
    ]
)
