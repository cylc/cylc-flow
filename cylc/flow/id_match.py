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

from fnmatch import fnmatchcase
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    TYPE_CHECKING,
)

from metomi.isodatetime.exceptions import ISO8601SyntaxError

from cylc.flow import LOG
from cylc.flow.id import IDTokens, Tokens
from cylc.flow.id_cli import contains_fnmatch
from cylc.flow.cycling.loader import get_point

if TYPE_CHECKING:
    from cylc.flow.task_pool import Pool
    from cylc.flow.task_proxy import TaskProxy
    from cylc.flow.cycling import PointBase


# @overload
# def filter_ids(
#     pool: 'Pool',
#     ids: 'Iterable[str]',
#     *,
#     warn: 'bool' = True,
#     out: 'Literal[IDTokens.Task]' = IDTokens.Task,
#     pattern_match: 'bool' = True,
# ) -> 'Tuple[List[TaskProxy], List[str]]':
#     ...
#
#
# @overload
# def filter_ids(
#     pool: 'Pool',
#     ids: 'Iterable[str]',
#     *,
#     warn: 'bool' = True,
#     out: 'Literal[IDTokens.Cycle]' = IDTokens.Cycle,
#     pattern_match: 'bool' = True,
# ) -> 'Tuple[List[PointBase], List[str]]':
#     ...


# _RET = (
#     'Union['
#     'Tuple[List[TaskProxy], List[str]]'
#     ', '
#     'Tuple[List[PointBase], List[str]]'
#     ']'
# )


def filter_ids(
    pool: 'Pool',
    ids: 'Iterable[str]',
    *,
    warn: 'bool' = True,
    out: 'IDTokens' = IDTokens.Task,
    pattern_match: 'bool' = True,
    # ) -> _RET:
):
    """Filter IDs against a pool of tasks.

    Args:
        pool:
            The pool to match against.
        ids:
            List of IDs to match against the pool.
        out:
            The type of object to match:

            * If IDTokens.Task all matching TaskProxies will be returned.
            * If IDTokens.Cycle all CyclePoints with any matching tasks will
              be returned.
        warn:
            Whether to log a warning if no matching tasks are found in the
            pool.

    TODO:
        Consider using wcmatch which would add support for
        extglobs, namely brace syntax e.g. {foo,bar}.

    """
    if out not in {IDTokens.Cycle, IDTokens.Task}:
        raise ValueError(f'Invalid output format: {out}')

    _cycles: 'List[PointBase]' = []
    _tasks: 'List[TaskProxy]' = []
    _not_matched: 'List[str]' = []

    # enable / disable pattern matching
    match: Callable[[Any, Any], bool]
    if pattern_match:
        match = fnmatchcase
    else:
        match = str.__eq__
        pattern_ids = [
            id_
            for id_ in ids
            if contains_fnmatch(id_)
        ]
        if pattern_ids:
            LOG.warning(f'IDs cannot contain globs: {", ".join(pattern_ids)}')
            ids = [
                id_
                for id_ in ids
                if id_ not in pattern_ids
            ]
            _not_matched.extend(pattern_ids)

    id_tokens_map: Dict[str, Tokens] = {}
    for id_ in ids:
        try:
            id_tokens_map[id_] = Tokens(id_, relative=True)
        except ValueError:
            _not_matched.append(id_)
            LOG.warning(f'Invalid ID: {id_}')

    for id_, tokens in id_tokens_map.items():
        for lowest_token in reversed(IDTokens):
            if tokens.get(lowest_token.value):
                break

        cycles = set()
        tasks = []

        # filter by cycle
        if lowest_token == IDTokens.Cycle:
            cycle = tokens[IDTokens.Cycle.value]
            cycle_sel = tokens.get(IDTokens.Cycle.value + '_sel') or '*'
            for icycle, itasks in pool.items():
                if not itasks:
                    continue
                if not point_match(icycle, cycle, pattern_match):
                    continue
                if cycle_sel == '*':
                    cycles.add(icycle)
                    continue
                for itask in itasks.values():
                    if match(itask.state.status, cycle_sel):
                        cycles.add(icycle)
                        break

        # filter by task
        elif lowest_token == IDTokens.Task:   # noqa SIM106
            cycle = tokens[IDTokens.Cycle.value]
            cycle_sel_raw = tokens.get(IDTokens.Cycle.value + '_sel')
            cycle_sel = cycle_sel_raw or '*'
            task = tokens[IDTokens.Task.value]
            task_sel_raw = tokens.get(IDTokens.Task.value + '_sel')
            task_sel = task_sel_raw or '*'
            for icycle, itasks in pool.items():
                if not point_match(icycle, cycle, pattern_match):
                    continue
                for itask in itasks.values():
                    if (
                        # check cycle selector
                        (
                            (
                                # disable cycle_sel if not defined if
                                # pattern matching is turned off
                                pattern_match is False
                                and cycle_sel_raw is None
                            )
                            or match(itask.state.status, cycle_sel)
                        )
                        # check namespace name
                        and itask.name_match(task, match_func=match)
                        # check task selector
                        and (
                            (
                                # disable task_sel if not defined if
                                # pattern matching is turned off
                                pattern_match is False
                                and task_sel_raw is None
                            )
                            or match(itask.state.status, task_sel)
                        )
                    ):
                        tasks.append(itask)

        else:
            raise NotImplementedError

        if not (cycles or tasks):
            _not_matched.append(id_)
            if warn:
                LOG.warning(f"No active tasks matching: {id_}")
        else:
            _cycles.extend(list(cycles))
            _tasks.extend(tasks)

    ret: List[Any] = []
    if out == IDTokens.Cycle:
        _cycles.extend({
            itask.point
            for itask in _tasks
        })
        ret = _cycles
    elif out == IDTokens.Task:
        for icycle in _cycles:
            if icycle in pool:
                _tasks.extend(pool[icycle].values())
        ret = _tasks
    return ret, _not_matched


def point_match(
    point: 'PointBase', value: str, pattern_match: bool = True
) -> bool:
    """Return whether a cycle point matches a string/pattern.

    Args:
        point: Cycle point to compare against.
        value: String/pattern to test.
        pattern_match: Whether to allow glob patterns in the value.
    """
    try:
        return point == get_point(value)
    except (ValueError, ISO8601SyntaxError):
        # Could be glob pattern
        if pattern_match:
            return fnmatchcase(str(point), value)
        return False
