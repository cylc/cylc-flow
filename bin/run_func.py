#!/usr/bin/env python2

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2018 NIWA
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

import importlib
import json
import sys

from cylc.mp_func_context import get_func

"""

CYLC INTERNAL USE

Run a Python function in a subprocess, print its return value to stdout.

USAGE: cylc wrap-func <func-name> <'json-func-args'> <'json-func-kwargs'>

Run a Python function (given name, args, and kwargs) in the command process
pool. The function is expected to be defined in a module of the same name.

The return value is printed as a JSON string to stdout.

Anything written to stdout by the function will be redirected and printed to
suite stderr in debug mode.

"""


def run_func(func_name, func_args, func_kwargs):
    func = get_func(func_name)
    # Redirect stdout to stderr.
    orig_stdout = sys.stdout
    sys.stdout = sys.stderr
    res = func(*func_args, **func_kwargs)
    # Restore stdout.
    sys.stdout = orig_stdout
    # Write function return value as JSON to stdout.
    print json.dumps(res)


if __name__ == "__main__":
    func_name = sys.argv[1]
    func_args = json.loads(sys.argv[2])
    func_kwargs = json.loads(sys.argv[3])
    run_func(func_name, func_args, func_kwargs)
