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

"""Cylc command argument validation logic."""


from typing import (
    Callable,
    List,
    Optional,
)

from cylc.flow.exceptions import InputError
from cylc.flow.id import Tokens
from cylc.flow.task_outputs import TASK_OUTPUT_SUCCEEDED
from cylc.flow.flow_mgr import FLOW_ALL, FLOW_NEW, FLOW_NONE


ERR_OPT_FLOW_VAL = "Flow values must be an integer, or 'all', 'new', or 'none'"
ERR_OPT_FLOW_INT = "Multiple flow options must all be integer valued"
ERR_OPT_FLOW_WAIT = (
    f"--wait is not compatible with --flow={FLOW_NEW} or --flow={FLOW_NONE}"
)


def validate(func: Callable):
    """Decorate scheduler commands with a callable .validate attribute.

    """
    # TODO: properly handle "Callable has no attribute validate"?
    func.validate = globals()[  # type: ignore
        func.__name__.replace("command", "validate")
    ]
    return func


def validate_flow_opts(flows: List[str], flow_wait: bool) -> None:
    """Check validity of flow-related CLI options.

    Note the schema defaults flows to ["all"].

    Examples:
        Good:
        >>> validate_flow_opts(["new"], False)
        >>> validate_flow_opts(["1", "2"], False)
        >>> validate_flow_opts(["1", "2"], True)

        Bad:
        >>> validate_flow_opts(["none", "1"], False)
        Traceback (most recent call last):
        cylc.flow.exceptions.InputError: ... must all be integer valued

        >>> validate_flow_opts(["cheese", "2"], True)
        Traceback (most recent call last):
        cylc.flow.exceptions.InputError: ... or 'all', 'new', or 'none'

        >>> validate_flow_opts(["new"], True)
        Traceback (most recent call last):
        cylc.flow.exceptions.InputError: ...

    """
    for val in flows:
        val = val.strip()
        if val in [FLOW_NONE, FLOW_NEW, FLOW_ALL]:
            if len(flows) != 1:
                raise InputError(ERR_OPT_FLOW_INT)
        else:
            try:
                int(val)
            except ValueError:
                raise InputError(ERR_OPT_FLOW_VAL.format(val))

    if flow_wait and flows[0] in [FLOW_NEW, FLOW_NONE]:
        raise InputError(ERR_OPT_FLOW_WAIT)


def validate_prereqs(prereqs: Optional[List[str]]):
    """Validate a list of prerequisites, add implicit ":succeeded".

    Comma-separated lists should be split already, client-side.

    Examples:
        # Set multiple at once:
        >>> validate_prereqs(['1/foo:bar', '2/foo:baz'])
        ['1/foo:bar', '2/foo:baz']

        # --pre=all
        >>> validate_prereqs(["all"])
        ['all']

        # implicit ":succeeded"
        >>> validate_prereqs(["1/foo"])
        ['1/foo:succeeded']

        # Error: invalid format:
        >>> validate_prereqs(["fish"])
        Traceback (most recent call last):
        cylc.flow.exceptions.InputError: ...

        # Error: invalid format:
        >>> validate_prereqs(["1/foo::bar"])
        Traceback (most recent call last):
        cylc.flow.exceptions.InputError: ...

        # Error: "all" must be used alone:
        >>> validate_prereqs(["all", "2/foo:baz"])
        Traceback (most recent call last):
        cylc.flow.exceptions.InputError: ...

    """
    if prereqs is None:
        return []

    prereqs2 = []
    bad: List[str] = []
    for pre in prereqs:
        p = validate_prereq(pre)
        if p is not None:
            prereqs2.append(p)
        else:
            bad.append(pre)
    if bad:
        raise InputError(
            "Use prerequisite format <cycle-point>/<task>:output\n"
            "\n  ".join(bad)
        )

    if len(prereqs2) > 1:  # noqa SIM102 (anticipates "cylc set --pre=cycle")
        if "all" in prereqs:
            raise InputError("--pre=all must be used alone")

    return prereqs2


def validate_prereq(prereq: str) -> Optional[str]:
    """Return prereq (with :succeeded) if valid, else None.

    Format: cycle/task[:output]

    Examples:
        >>> validate_prereq('1/foo:succeeded')
        '1/foo:succeeded'

        >>> validate_prereq('1/foo')
        '1/foo:succeeded'

        >>> validate_prereq('all')
        'all'

        # Error:
        >>> validate_prereq('fish')

    """
    try:
        tokens = Tokens(prereq, relative=True)
    except ValueError:
        return None
    if (
        tokens["cycle"] == prereq
        and prereq != "all"
    ):
        # Error: --pre=<word> other than "all"
        return None

    if prereq != "all" and tokens["task_sel"] is None:
        prereq += f":{TASK_OUTPUT_SUCCEEDED}"

    return prereq


def validate_outputs(outputs: Optional[List[str]]):
    """Validate outputs.

    Comma-separated lists should be split already, client-side.

    Examples:
        Good:
        >>> validate_outputs(['a', 'b'])
        ['a', 'b']

        >>> validate_outputs(["required"])  # "required" is explicit default
        []

        Bad:
        >>> validate_outputs(["required", "a"])
        Traceback (most recent call last):
        cylc.flow.exceptions.InputError: --out=required must be used alone

        >>> validate_outputs(["waiting"])
        Traceback (most recent call last):
        cylc.flow.exceptions.InputError: Tasks cannot be set to waiting...

    """
    # If "required" is explicit just ditch it (same as the default)
    if not outputs or outputs == ["required"]:
        return []

    if "required" in outputs:
        raise InputError("--out=required must be used alone")

    if "waiting" in outputs:
        raise InputError(
            "Tasks cannot be set to waiting. Use trigger to re-run tasks."
        )

    return outputs


def validate_consistency(
    outputs: Optional[List[str]],
    prereqs: Optional[List[str]]
) -> None:
    """Check global option consistency

    Examples:
        >>> validate_consistency(["a"], None)  # OK

        >>> validate_consistency(None, ["1/a:failed"])  #OK

        >>> validate_consistency(["a"], ["1/a:failed"])
        Traceback (most recent call last):
        cylc.flow.exceptions.InputError: ...

    """
    if outputs and prereqs:
        raise InputError("Use --prerequisite or --output, not both.")


def validate_set(
    tasks: List[str],
    flow: List[str],
    outputs: Optional[List[str]] = None,
    prerequisites: Optional[List[str]] = None,
    flow_wait: bool = False,
    flow_descr: Optional[str] = None
) -> None:
    """Validate args of the scheduler "command_set" method.

    Raise InputError if validation fails.
    """
    validate_consistency(outputs, prerequisites)
    outputs = validate_outputs(outputs)
    prerequisites = validate_prereqs(prerequisites)
    validate_flow_opts(flow, flow_wait)
