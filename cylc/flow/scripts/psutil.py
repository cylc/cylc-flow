#!/usr/bin/env python3
# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
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

This is for use in situations where Cylc needs to extract information from
the `psutil` on remote platforms.

Exits:
    0 - If successful.
    2 - For errors in extracting results from psutil
    1 - For all other errors.
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


def _call_psutil_interface(interface, *args):
    """Call a psutil interface with the provided arguments.

    Args:
        interface:
            The psutil method we want to call, e.g. "cpu_percent".

            In the case of objects, this may include attribures, e.g.
            "Process.cmdline".
        args:
            The arguments to provide to the psutil method.

    Returns:
        The result of the psutil method call.

    """
    result = psutil
    is_first = True
    for fcn in interface.split('.'):
        try:
            method = getattr(result, fcn)
        except AttributeError as exc:
            # error obtaining interfaces from psutil e.g:
            # * requesting a method which does not exist
            print(exc, file=sys.stderr)
            sys.exit(2)

        if is_first:
            args = args
            is_first = False
        else:
            args = ()

        result = method(*args)
    return result


def _psutil(metrics_json):
    metrics = parse_dirty_json(metrics_json)

    try:
        ret = [_call_psutil_interface(*key) for key in metrics]
    except Exception as exc:
        # error extracting metrics from psutil e.g:
        # * requesting information on a resource which does not exist
        print(exc, file=sys.stderr)
        sys.exit(2)

    # serialise
    for ind, item in enumerate(ret):
        if hasattr(item, '_asdict'):
            ret[ind] = item._asdict()
        elif hasattr(item, 'as_dict'):
            ret[ind] = item.as_dict()

    return ret


@cli_function(get_option_parser)
def main(*_):
    print(
        json.dumps(
            _psutil(sys.stdin.read())
        )
    )
