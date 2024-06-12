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
"""USAGE: cylc function-run <name> <json-args> <json-kwargs> <src-dir>

(This command is for internal use.)

Run a Python xtrigger function "<name>(*args, **kwargs)" in the process pool.
It must be in a module of the same name. Positional and keyword arguments must
be passed in as JSON strings.

Python entry points are the preferred way to make xtriggers available to the
scheduler, but local xtriggers can be stored in <src-dir>.

"""
import sys

from cylc.flow.subprocpool import run_function

INTERNAL = True


def main(*api_args):
    if api_args:
        args = [None] + list(api_args)
    else:
        args = sys.argv
    if args[1] in ["help", "--help"] or len(args) != 5:
        print(__doc__)
        sys.exit(0)
    run_function(args[1], args[2], args[3], args[4])
