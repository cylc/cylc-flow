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

from random import random, randint
from time import sleep
from typing import Any, Dict, Tuple

from cylc.flow.exceptions import WorkflowConfigError


COLORS = ["red", "orange", "yellow", "green", "blue", "indigo", "violet"]
SIZES = ["tiny", "small", "medium", "large", "huge", "humongous"]


def xrandom(
    percent: float, secs: int = 0, _: Any = None
) -> Tuple[bool, Dict[str, str]]:
    """Random xtrigger, with configurable sleep and percent success.

    Sleep for ``sec`` seconds, and report satisfied with ``percent``
    likelihood.

    The ``_`` argument is not used in the function code, but can be used to
    specialize the function signature to cycle point or task.

    Args:
        percent:
            Percent likelihood of passing.
        secs:
            Seconds to sleep before starting the trigger.
        _:
            Used to allow users to specialize the trigger with extra
            parameters.

    Returns:
        tuple: (satisfied, results)

        satisfied:
            True if ``satisfied`` else ``False``.
        results:
            A dictionary containing the following keys:

            ``COLOR``
                A random colour (e.g. red, orange, ...).
            ``SIZE``
                A random size (e.g. small, medium, ...).

    Examples:
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
        dictionary containing random colour and size as result.

        >>> import sys
        >>> mocked_random = lambda: 0.9
        >>> sys.modules[__name__].random = mocked_random
        >>> mocked_randint = lambda x, y: 1
        >>> sys.modules[__name__].randint = mocked_randint
        >>> xrandom(99.99, 0)
        (True, {'COLOR': 'orange', 'SIZE': 'small'})

    """
    sleep(float(secs))
    results = {}
    satisfied = random() < float(percent) / 100  # nosec: B311
    if satisfied:
        results = {
            'COLOR': COLORS[randint(0, len(COLORS) - 1)],  # nosec: B311
            'SIZE': SIZES[randint(0, len(SIZES) - 1)]  # nosec: B311
        }
    return satisfied, results


def validate(args: Dict[str, Any]):
    """Validate and manipulate args parsed from the workflow config.

    The rules for args are:
    * percent: Must be 0 ≤ x ≤ 100
    * secs: Must be an integer.
    """
    percent = args['percent']
    if (
        not isinstance(percent, (float, int))
        or not (0 <= percent <= 100)
    ):
        raise WorkflowConfigError(
            "'percent' should be a float between 0 and 100"
        )

    secs = args['secs']
    if not isinstance(secs, int):
        raise WorkflowConfigError("'secs' should be an integer")
