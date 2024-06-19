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

"""xtrigger function to trigger off of a wall clock time."""

from time import time
from typing import Any, Dict
from cylc.flow.cycling.iso8601 import interval_parse
from cylc.flow.exceptions import WorkflowConfigError


def wall_clock(offset: str = 'PT0S', sequential: bool = True):
    """Trigger at a specific real "wall clock" time relative to the cycle point
    in the graph.

    Clock triggers, unlike other trigger functions, are executed synchronously
    in the main process.

    Args:
        offset:
            ISO 8601 interval to wait after the cycle point is reached in real
            time before triggering. May be negative, in which case it will
            trigger before the real time reaches the cycle point.
        sequential:
            Wall-clock xtriggers are run sequentially by default.
            See :ref:`Sequential Xtriggers` for more details.

    .. versionchanged:: 8.3.0

       The ``sequential`` argument was added.
    """
    # NOTE: This is just a placeholder for the actual implementation.
    # This is only used for validating the signature and for autodocs.
    ...


def _wall_clock(trigger_time: int) -> bool:
    """Actual implementation of wall_clock.

    Return True after the desired wall clock time, or False before.

    Args:
        trigger_time:
            Trigger time as seconds since Unix epoch.
        sequential (bool):
            Used by the workflow to flag corresponding xtriggers as sequential.
    """
    return time() > trigger_time


def validate(args: Dict[str, Any]):
    """Validate and manipulate args parsed from the workflow config.

    NOTE: the xtrigger signature is different to the function signature above

    wall_clock()  # infer zero interval
    wall_clock(PT1H)
    wall_clock(offset=PT1H)

    The offset must be a valid ISO 8601 interval.
    """
    try:
        interval_parse(args["offset"])
    except (ValueError, AttributeError):
        raise WorkflowConfigError(
            f"Invalid offset: {args['offset']}"
        ) from None
