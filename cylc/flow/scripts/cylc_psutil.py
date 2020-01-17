#!/usr/bin/env python3

# this file is part of the cylc suite engine.
# copyright (c) 2008-2019 niwa
#
# this program is free software: you can redistribute it and/or modify
# it under the terms of the gnu general public license as published by
# the free software foundation, either version 3 of the license, or
# (at your option) any later version.
#
# this program is distributed in the hope that it will be useful,
# but without any warranty; without even the implied warranty of
# merchantability or fitness for a particular purpose.  see the
# gnu general public license for more details.
#
# you should have received a copy of the gnu general public license
# along with this program.  if not, see <http://www.gnu.org/licenses/>.
"""Report system utilisation information.

For internal use with the `cylc.flow.host_select` module.
"""
from itertools import dropwhile
import json
import pickle
import sys

import psutil

# from cylc.flow.host_select import _simple_eval
from cylc.flow.option_parsers import OptionParser
from cylc.flow.terminal import cli_function


def get_option_parser():
    return OptionParser(__doc__)


@cli_function(get_option_parser)
def main(parser, options):
    # Users may have profile scripts that write to STDOUT.
    # Drop all output lines until the the first character of a
    # line is '['. Hopefully this is enough to find us the
    # first line that denotes the beginning of the expected
    # JSON data structure.
    stdin = '\n'.join(dropwhile(
        lambda s: not s.startswith('['),
        sys.stdin.readlines()
    ))

    metrics = json.loads(stdin)

    ret = [
        getattr(psutil, key[0])(*key[1:])
        for key in metrics
    ]

    # serialise
    for ind, item in enumerate(ret):
        if hasattr(item, '_todict'):
            ret[ind] = item._todict()
        elif hasattr(item, '_asdict'):
            ret[ind] = item._asdict()

    print(json.dumps(ret))
