#!/usr/bin/env python3

"""cylc [info] extract-resources [OPTIONS] DIR [RESOURCES]

Extract resources from the cylc.flow package and write them to DIR.

Options:
    --list      List available resources
Arguments:
    DIR         Target Directory
    [RESOURCES] Specific resources to extract (default all).
"""

import os
import sys

from cylc.flow.exceptions import UserInputError
from cylc.flow.resources import extract_resources, list_resources
from cylc.flow.terminal import cli_function


class ArgParser:
    """Lightweight standin for cylc.flow.option_parsers.CylcOptionParser."""

    @classmethod
    def parser(cls):
        return cls

    @staticmethod
    def parse_args():
        if {'help', '--help', "-h"} & set(sys.argv):
            print(__doc__)
        elif len(sys.argv) < 2:
            raise UserInputError(
                "wrong number of arguments, "
                f"see '{os.path.basename(sys.argv[0])} --help'."
            )
        elif '--list' in sys.argv:
            print('\n'.join(list_resources()))
        else:
            return (None, sys.argv[1:])
        sys.exit()


@cli_function(ArgParser.parser)
def main(parser, _, target_dir, *resources):
    extract_resources(target_dir, resources or None)


if __name__ == '__main__':
    main()
