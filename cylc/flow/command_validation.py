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
    TYPE_CHECKING,
    Dict,
    Iterable,
    List,
    Optional,
    Set,
    cast,
)

from cylc.flow.cycling.loader import standardise_point_string
from cylc.flow.exceptions import InputError, PointParsingError
from cylc.flow.flow_mgr import (
    FLOW_NEW,
    FLOW_NONE,
)
from cylc.flow.id import (
    IDTokens,
    Tokens,
)
from cylc.flow.id_cli import contains_fnmatch
from cylc.flow.scripts.set import XTRIGGER_PREREQ_PREFIX
from cylc.flow.task_outputs import TASK_OUTPUT_SUCCEEDED


if TYPE_CHECKING:
    from cylc.flow.id import TaskTokens


ERR_OPT_FLOW_VAL_INT_NEW_NONE = (  # for set and trigger commands
    f"Flow values must be integers, or '{FLOW_NEW}', or '{FLOW_NONE}'"
)
ERR_OPT_FLOW_VAL_INT = "Flow values must be integers"  # for remove command
ERR_OPT_FLOW_COMBINE = "Cannot combine --flow={0} with other flow values"
ERR_OPT_FLOW_WAIT = (
    f"--wait is not compatible with --flow={FLOW_NEW} or --flow={FLOW_NONE}"
)


def flow_opts(
    flows: List[str],
    flow_wait: bool,
    allow_new_or_none: bool = True,
) -> None:
    """Check validity of flow-related CLI options.

    Note the schema defaults flows to [].

    Examples:
        Good:
        >>> flow_opts([], False)
        >>> flow_opts(["new"], False)
        >>> flow_opts(["1", "2"], False)
        >>> flow_opts(["1", "2"], True)

        Bad:
        >>> flow_opts(["none", "1"], False)
        Traceback (most recent call last):
        cylc.flow.exceptions.InputError: Cannot combine --flow=none with other
        flow values

        >>> flow_opts(["cheese", "2"], True)
        Traceback (most recent call last):
        cylc.flow.exceptions.InputError: ... or 'new', or 'none'

        >>> flow_opts(["new"], True)
        Traceback (most recent call last):
        cylc.flow.exceptions.InputError: --wait is not compatible with
        --flow=new or --flow=none

        >>> flow_opts(["new"], False, allow_new_or_none=False)
        Traceback (most recent call last):
        cylc.flow.exceptions.InputError: ... must be integers

        >>> flow_opts([''], False, allow_new_or_none=False)
        Traceback (most recent call last):
        cylc.flow.exceptions.InputError: ... must be integers

    """
    if not flows:
        return

    flows = [val.strip() for val in flows]

    for val in flows:
        val = val.strip()
        if val in {FLOW_NONE, FLOW_NEW}:
            if len(flows) != 1:
                raise InputError(ERR_OPT_FLOW_COMBINE.format(val))
            if not allow_new_or_none and val in {FLOW_NEW, FLOW_NONE}:
                raise InputError(ERR_OPT_FLOW_VAL_INT)
        else:
            try:
                int(val)
            except ValueError:
                if allow_new_or_none:
                    raise InputError(ERR_OPT_FLOW_VAL_INT_NEW_NONE) from None
                raise InputError(ERR_OPT_FLOW_VAL_INT) from None

    if flow_wait and flows[0] in {FLOW_NEW, FLOW_NONE}:
        raise InputError(ERR_OPT_FLOW_WAIT)


def prereqs(prereqs: Optional[List[str]]):
    """Validate prerequisites, add implicit ":succeeded".

    Comma-separated lists should be split already, client-side.

    Examples:
        # Set multiple at once, prereq and xtriggers:
        >>> prereqs(['1/foo:bar', '2/foo:baz', 'xtrigger/x1'])
        ['1/foo:bar', '2/foo:baz', 'xtrigger/x1:succeeded']

        # --pre=all
        >>> prereqs(["all"])
        ['all']

        # implicit ":succeeded"
        >>> prereqs(["1/foo"])
        ['1/foo:succeeded']

        # implicit ":satisifed"
        >>> prereqs(["xtrigger/foo"])
        ['xtrigger/foo:succeeded']

        # Error: invalid format:
        >>> prereqs(["fish", "dog"])
        Traceback (most recent call last):
        cylc.flow.exceptions.InputError: ...
          * fish
          * dog

        # Error: invalid format:
        >>> prereqs(["1/foo::bar"])
        Traceback (most recent call last):
        cylc.flow.exceptions.InputError: ...
          * 1/foo::bar

        # Error: invalid format:
        >>> prereqs(["xtrigger/x1::bar"])
        Traceback (most recent call last):
        cylc.flow.exceptions.InputError: ...
          * xtrigger/x1::bar

        # Error: "all" must be used alone:
        >>> prereqs(["all", "2/foo:baz"])
        Traceback (most recent call last):
        cylc.flow.exceptions.InputError: --pre=all must be used alone

    """
    if prereqs is None:
        return []

    prereqs2 = []
    bad: List[str] = []
    for pre in prereqs:
        p = prereq(pre)
        if p is not None:
            prereqs2.append(p)
        else:
            bad.append(pre)
    if bad:
        raise InputError(
            "Bad prerequisite format, see command help:\n * "
            + "\n * ".join(bad)
        )
    if len(prereqs2) > 1:  # noqa SIM102 (anticipates "cylc set --pre=cycle")
        if "all" in prereqs:
            raise InputError("--pre=all must be used alone")

    return prereqs2


def prereq(prereq: str) -> Optional[str]:
    """Return standardised task and xtrigger prerequisites if valid, else None.

    Default to suffix ":succeeded" (task and xtrigger prerequisites).

    (Standardisation of "start" -> "started" etc. is done later).

    Format: cycle/task[:output]
      (xtriggers: cycle is "xtrigger", task is xtrigger label)

    Examples:
        >>> prereq('1/foo:succeeded')
        '1/foo:succeeded'

        >>> prereq('1/foo:succeed')
        '1/foo:succeed'

        >>> prereq('1/foo')
        '1/foo:succeeded'

        >>> prereq('1/foo:other_output')
        '1/foo:other_output'

        >>> prereq('all')
        'all'

        >>> prereq('xtrigger/wall_clock')
        'xtrigger/wall_clock:succeeded'

        >>> prereq('xtrigger/wall_clock:succeeded')
        'xtrigger/wall_clock:succeeded'

        >>> prereq('xtrigger/all')
        'xtrigger/all:succeeded'

        >>> prereq('xtrigger/all:succeeded')
        'xtrigger/all:succeeded'

        # Error, xtrigger state must be succeeded or waiting:
        >>> prereq('xtrigger/wall_clock:other')

        # Error, just a task name:
        >>> prereq('fish')

    """
    try:
        tokens = Tokens(prereq, relative=True)
    except ValueError:
        return None

    if tokens["cycle"] == prereq and prereq != "all":
        # Error: --pre=<word> other than "all"
        return None

    if tokens["cycle"] == XTRIGGER_PREREQ_PREFIX:
        if tokens["task_sel"] not in {None, TASK_OUTPUT_SUCCEEDED}:
            # Error: xtrigger status must be default or succeeded.
            return None
        if tokens["task_sel"] is None:
            # Default to succeeded
            prereq += f":{TASK_OUTPUT_SUCCEEDED}"
    else:
        if prereq != "all" and tokens["task_sel"] is None:
            # Default to succeeded
            prereq += f":{TASK_OUTPUT_SUCCEEDED}"

    return prereq


def outputs(outputs: Optional[List[str]]):
    """Validate outputs.

    Comma-separated lists should be split already, client-side.

    Examples:
        Good:
        >>> outputs(['a', 'b'])
        ['a', 'b']

        >>> outputs(["required"])  # "required" is explicit default
        []

        Bad:
        >>> outputs(["required", "a"])
        Traceback (most recent call last):
        cylc.flow.exceptions.InputError: --out=required must be used alone

        >>> outputs(["waiting"])
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


def consistency(
    outputs: Optional[List[str]],
    prereqs: Optional[List[str]],
) -> None:
    """Check global option consistency

    Examples:
        >>> consistency(["a"], None)  # OK

        >>> consistency(None, ["1/a:failed"])  #OK

        >>> consistency(["a"], ["1/a:failed"])
        Traceback (most recent call last):
        cylc.flow.exceptions.InputError: ...

    """
    if outputs and prereqs:
        raise InputError("Use --prerequisite or --output, not both.")


def is_tasks(ids: Iterable[str]) -> 'Set[TaskTokens]':
    """Ensure all IDs are task IDs and standardise them.

    * Parses IDs.
    * Filters out job ids and ensures at least the cycle point is provided.
    * Standardises the cycle point format.
    * Defaults the namespace to "root" unless provided.

    Args:
        ids: The strings to parse.

    Returns:
        The parsed IDs as TaskTokens objects.

    Raises:
        InputError: If any of the IDs cannot be parsed or formatted.

    """
    if not ids:
        raise InputError("No tasks specified")
    ret: 'Set[TaskTokens]' = set()
    errors: Dict[str, List[str]] = {}

    for id_ in ids:
        # parse id
        try:
            tokens = Tokens(id_, relative=True)
        except ValueError:
            errors.setdefault('Invalid ID', []).append(id_)
            continue

        # filter out job IDs
        if tokens.lowest_token == IDTokens.Job.value:
            errors.setdefault('This command does not take job IDs', []).append(
                id_
            )
            continue

        # if the task is not specified, default to "root"
        if tokens['task'] is None:
            tokens = tokens.duplicate(task='root')

        # if the cycle is not a glob or reference, standardise it
        if (
            # cycle point is a glob
            not contains_fnmatch(cast('str', tokens['cycle']))
            # cycle point is a reference to the ICP/FCP
            and tokens['cycle'] not in {'^', '$'}
        ):
            try:
                cycle = standardise_point_string(tokens['cycle'])
            except PointParsingError:
                errors.setdefault('Invalid cycle point', []).append(id_)
                continue
            else:
                if cycle != tokens['cycle']:
                    tokens = tokens.duplicate(cycle=cycle)

        # we have confirmed that both cycle and task have been provided
        ret.add(cast('TaskTokens', tokens))

    if errors:
        raise InputError(
            '\n'.join(
                f'{message}: {", ".join(sorted(_ids))}'
                for message, _ids in sorted(errors.items())
            )
        )

    return ret
