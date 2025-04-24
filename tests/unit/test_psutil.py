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

import json
import os

from psutil import Process

from cylc.flow.scripts.psutil import _psutil


def test_psutil_basic():
    """It should return measurements."""
    # obtain memory reading
    ret = _psutil('[["virtual_memory"]]')

    # we asked for one thing so we should get one response
    assert len(ret) == 1

    # the result should be dict-like and serialise to json
    mem = ret[0]
    dict(mem)
    json.dumps(mem)

    for key in ('total', 'available', 'used', 'free'):
        # it should have multiple fields
        assert key in mem
        # all of which should be integers
        assert isinstance(mem[key], int)


def test_psutil_object():
    """It should call object methods."""
    # obtain the commandline for this test process
    ret = _psutil(f'[["Process.cmdline", {os.getpid()}]]')

    assert ret[0] == Process().cmdline()
