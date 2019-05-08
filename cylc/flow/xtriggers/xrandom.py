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

from random import random, randint
from time import sleep


COLORS = ["red", "orange", "yellow", "green", "blue", "indigo", "violet"]
SIZES = ["tiny", "small", "medium", "large", "huge", "humongous"]


def xrandom(percent, secs=0, _=None, debug=False):
    """Random xtrigger, with configurable sleep and percent success.

    Sleep for <sec> seconds, and report satisfied with ~<percent> likelihood.
    If satisfied, return a random color and size as the result.
    The '_' argument is not used in the function code, but can be used to
    specialize the function signature to cycle point or task.

    If the percent is zero, it returns that the trigger condition was
    not satisfied, and an empty dictionary.
    >>> xrandom(0, 0)
    (False, {})

    If the percent is not zero, but the random percent success is not met,
    then it also returns that the trigger condition was not satisfied,
    and an empty dictionary.
    >>> import sys
    >>> mocked_random = lambda: 0.3
    >>> sys.modules[__name__].random = mocked_random
    >>> xrandom(15.5, 0)
    (False, {})

    Finally, if the percent is not zero, and the random percent success is
    met, then it returns that the trigger condition was satisfied, and a
    dictionary containing random color and size as result.
    >>> import sys
    >>> mocked_random = lambda: 0.9
    >>> sys.modules[__name__].random = mocked_random
    >>> mocked_randint = lambda x, y: 1
    >>> sys.modules[__name__].randint = mocked_randint
    >>> xrandom(99.99, 0)
    (True, {'COLOR': 'orange', 'SIZE': 'small'})

    Args:
        percent (float): percent likelihood.
        secs (int): seconds to sleep before starting the trigger.
        _ (object): used to allow users to specialize the trigger
                    with extra parameters.
        debug (bool): flag to enable debug information.
    Returns:
        A tuple with the trigger flag (bool) which is set to True if the
        trigger was evaluated successful, False otherwise, and a random
        color and size (dict).
    """
    sleep(float(secs))
    results = {}
    satisfied = random() < float(percent) / 100  # nosec
    if satisfied:
        results = {
            'COLOR': COLORS[randint(0, len(COLORS) - 1)],  # nosec
            'SIZE': SIZES[randint(0, len(SIZES) - 1)]  # nosec
        }
    return (satisfied, results)
