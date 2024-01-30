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
from cylc.flow.cycling.iso8601 import interval_parse
from cylc.flow.exceptions import WorkflowConfigError


def wall_clock(trigger_time=None):
    """Return True after the desired wall clock time, False.

    Args:
        trigger_time (int):
            Trigger time as seconds since Unix epoch.
    """
    return time() > trigger_time


def validate(f_args, f_kwargs, f_signature):
    """Validate and manipulate args parsed from the workflow config.

    wall_clock()  # infer zero interval
    wall_clock(PT1H)
    wall_clock(offset=PT1H)

    The offset must be a valid ISO 8601 interval.

    If f_args used, convert to f_kwargs for clarity.

    """

    n_args = len(f_args)
    n_kwargs = len(f_kwargs)

    if n_args + n_kwargs > 1:
        raise WorkflowConfigError(f"Too many args: {f_signature}")

    if n_kwargs:
        # sole kwarg must be "offset"
        kw = next(iter(f_kwargs))
        if kw != "offset":
            raise WorkflowConfigError(f"Illegal arg '{kw}': {f_signature}")

    elif n_args:
        # convert to kwarg
        f_kwargs["offset"] = f_args[0]
        del f_args[0]

    else:
        # no args, infer zero interval
        f_kwargs["offset"] = "P0Y"

    # must be a valid interval
    try:
        interval_parse(f_kwargs["offset"])
    except ValueError:
        raise WorkflowConfigError(f"Invalid offset: {f_signature}")
