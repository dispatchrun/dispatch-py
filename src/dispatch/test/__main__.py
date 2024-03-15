"""Mock Dispatch server for use in test environments.

Usage:
  dispatch.test <endpoint> [--api-key=<key>] [--hostname=<name>] [--port=<port>] [-v | --verbose]
  dispatch.test -h | --help

Options:
     --api-key=<key>      API key to require when clients connect to the server [default: test].

     --hostname=<name>    Hostname to listen on [default: 127.0.0.1].
     --port=<port>        Port to listen on [default: 4450].

  -v --verbose            Show verbose details in the log.
  -h --help               Show this help information.
"""

import base64
import logging
import os
import sys

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from docopt import docopt

from dispatch.test import DispatchServer, DispatchService, EndpointClient


def main():
    args = docopt(__doc__)

    if args["--help"]:
        print(__doc__)
        exit(0)

    endpoint = args["<endpoint>"]
    api_key = args["--api-key"]
    hostname = args["--hostname"]
    port_str = args["--port"]

    try:
        port = int(port_str)
    except ValueError:
        print(f"error: invalid port: {port_str}", file=sys.stderr)
        exit(1)

    if not os.getenv("NO_COLOR"):
        logging.addLevelName(logging.WARNING, f"\033[1;33mWARN\033[1;0m")
        logging.addLevelName(logging.ERROR, "\033[1;31mERROR\033[1;0m")

    logger = logging.getLogger()
    if args["--verbose"]:
        logger.setLevel(logging.DEBUG)
        fmt = "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
    else:
        logger.setLevel(logging.INFO)
        fmt = "%(asctime)s [%(levelname)s] %(message)s"
        logging.getLogger("httpx").disabled = True

    log_formatter = logging.Formatter(fmt=fmt, datefmt="%Y-%m-%d %H:%M:%S")
    log_handler = logging.StreamHandler(sys.stderr)
    log_handler.setFormatter(log_formatter)
    logger.addHandler(log_handler)

    # This private key was generated randomly.
    signing_key = Ed25519PrivateKey.from_private_bytes(
        b"\x0e\xca\xfb\xc9\xa9Gc'fR\xe4\x97y\xf0\xae\x90\x01\xe8\xd9\x94\xa6\xd4@\xf6\xa7!\x90b\\!z!"
    )
    verification_key = base64.b64encode(
        signing_key.public_key().public_bytes_raw()
    ).decode()

    endpoint_client = EndpointClient.from_url(endpoint, signing_key=signing_key)

    with DispatchService(endpoint_client, api_key=api_key) as service:
        with DispatchServer(service, hostname=hostname, port=port) as server:
            print(f"Spawned a mock Dispatch server on {hostname}:{port}")
            print()
            print(f"Dispatching function calls to the endpoint at {endpoint}")
            print()
            print("The Dispatch SDK can be configured with:")
            print()
            print(f'  export DISPATCH_API_URL="http://{hostname}:{port}"')
            print(f'  export DISPATCH_API_KEY="{api_key}"')
            print(f'  export DISPATCH_ENDPOINT_URL="{endpoint}"')
            print(f'  export DISPATCH_VERIFICATION_KEY="{verification_key}"')
            print()

            server.wait()


if __name__ == "__main__":
    main()
