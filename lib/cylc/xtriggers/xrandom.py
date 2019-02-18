#!/usr/bin/env python3

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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

"""xtrigger with a configurable random chance of success.

Used for testing xtriggers.

"""

from random import randint
from time import sleep


COLORS = ["red", "orange", "yellow", "green", "blue", "indigo", "violet"]
SIZES = ["tiny", "small", "medium", "large", "huge", "humongous"]


def xrandom(percent, secs=0, _=None, debug=False):
    """Random xtrigger, with configurable sleep and percent success.

    Sleep for <sec> seconds, and report satisfied with ~<percent> likelihood.
    If satisfied, return a random color and size as the result.
    The '_' argument is not used in the function code, but can be used to
    specialize the function signature to cycle point or task.

    """
    sleep(float(secs))
    results = {}
    satisfied = (1 == randint(1, 100 / int(percent)))
    if satisfied:
        results = {
            'COLOR': COLORS[randint(0, len(COLORS) - 1)],
            'SIZE': SIZES[randint(0, len(SIZES) - 1)]
        }
    return (satisfied, results)
