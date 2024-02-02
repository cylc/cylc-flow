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
from typing import TYPE_CHECKING

from cylc.flow.exceptions import WorkflowConfigError


if TYPE_CHECKING:
    from typing import Any, Dict, Tuple


COLORS = ["red", "orange", "yellow", "green", "blue", "indigo", "violet"]
SIZES = ["tiny", "small", "medium", "large", "huge", "humongous"]


def xrandom(
    percent: float, secs: int = 0, _: 'Any' = None
) -> 'Tuple[bool, Dict]':
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

    Returns:
        Tuple, containing:

        satisfied:
            True if ``satisfied`` else ``False``.
        results:
            A dictionary containing the following keys:

            ``COLOR``
                A random colour (e.g. red, orange, ...).
            ``SIZE``
                A random size (e.g. small, medium, ...).

    """
    sleep(float(secs))
    results = {}
    satisfied = random() < float(percent) / 100  # nosec
    if satisfied:
        results = {
            'COLOR': COLORS[randint(0, len(COLORS) - 1)],  # nosec
            'SIZE': SIZES[randint(0, len(SIZES) - 1)]  # nosec
        }
    return satisfied, results


def validate(f_args, f_kwargs, f_signature):
    """Validate and manipulate args parsed from the workflow config.

    percent: - 0 ≤ x ≤ 100
    secs: An int.

    If f_args used, convert to f_kwargs for clarity.

    """
    n_args = len(f_args)
    n_kwargs = len(f_kwargs)

    if n_args + n_kwargs > 3:
        raise WorkflowConfigError(f"Too many args: {f_signature}")

    if n_args + n_kwargs < 1:
        raise WorkflowConfigError(f"Wrong number of args: {f_signature}")

    if n_kwargs:
        # kwargs must be "secs" and "_"
        kw = next(iter(f_kwargs))
        if kw not in ("secs", "_"):
            raise WorkflowConfigError(f"Illegal arg '{kw}': {f_signature}")

    # convert to kwarg
    f_kwargs["percent"] = f_args[0]
    del f_args[0]

    should_raise = False

    try:
        percent = f_kwargs['percent']
        percent = float(percent)
    except ValueError:
        should_raise = True
    else:
        if (
            not isinstance(percent, (float, int))
            or percent < 0
            or percent > 100
        ):
            should_raise = True
    if should_raise:
        raise WorkflowConfigError(
            f"'percent' should be a float between 0 and 100: {f_signature}")

    try:
        secs = f_kwargs.get('secs', 0)
    except ValueError:
        should_raise = True
    else:
        if not isinstance(secs, int):
            should_raise = True

    if should_raise:
        raise WorkflowConfigError(
            f"'secs' should be an integer: {f_signature}")
