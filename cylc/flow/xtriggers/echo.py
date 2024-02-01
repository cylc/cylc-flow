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

"""A Cylc xtrigger function."""

from cylc.flow.exceptions import WorkflowConfigError

from typing import Tuple


def echo(*args, **kwargs) -> Tuple:
    """Print arguments to stdout, return kwargs['succeed'] and kwargs.

    This may be a useful aid to understanding how xtriggers work.

    Args:
        succeed: Set the succeess of failure of this xtrigger.
        *args: Print to stdout.
        **kwargs: Print to stdout, and return as output.

    Examples:

        >>> echo('Breakfast Time', succeed=True, egg='poached')
        True, {'succeed': True, 'egg': 'poached'}

    Returns
        (True/False, kwargs)

    """
    print("echo: ARGS:", args)
    print("echo: KWARGS:", kwargs)

    return kwargs["succeed"], kwargs


def validate(f_args, f_kwargs, f_signature):

    """
    Validate the xtrigger function arguments parsed from the workflow config.

    This is separate from the xtrigger to allow parse-time validation.

    """
    if "succeed" not in f_kwargs or not isinstance(f_kwargs["succeed"], bool):
        raise WorkflowConfigError(
            f"Requires 'succeed=True/False' arg: {f_signature}"
        )
