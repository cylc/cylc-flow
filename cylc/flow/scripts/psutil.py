#!/usr/bin/env python3
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) NIWA & British Crown (Met Office) & Contributors.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Report system utilisation information.

(This command is for internal use.)

For internal use with the `cylc.flow.host_select` module.
"""

import json
import sys

import psutil

# from cylc.flow.host_select import _simple_eval
from cylc.flow.option_parsers import OptionParser
from cylc.flow.terminal import (
    cli_function,
    parse_dirty_json
)

INTERNAL = True


def get_option_parser():
    return OptionParser(__doc__)


def _psutil(metrics_json):
    metrics = parse_dirty_json(metrics_json)

    ret = [
        getattr(psutil, key[0])(*key[1:])
        for key in metrics
    ]

    # serialise
    for ind, item in enumerate(ret):
        if hasattr(item, '_asdict'):
            ret[ind] = item._asdict()

    return ret


@cli_function(get_option_parser)
def main(*_):
    print(
        json.dumps(
            _psutil(sys.stdin.read())
        )
    )
