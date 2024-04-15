"""Integration of Dispatch functions with gRPC."""

from dispatch.function import Batch, Registry


class Dispatch(Registry):
    """A Dispatch instance to be serviced by a gRPC server."""
