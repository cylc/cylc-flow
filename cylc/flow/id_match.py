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

"""Utilities for matching IDs which may reference families or include globs."""

from copy import deepcopy
from fnmatch import fnmatchcase
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Iterable,
    Set,
    Tuple,
)

from cylc.flow import LOG
from cylc.flow.cycling.loader import get_point
from cylc.flow.id import TaskTokens
from cylc.flow.id_cli import contains_fnmatch


if TYPE_CHECKING:
    from cylc.flow.config import WorkflowConfig


def id_match(
    config: 'WorkflowConfig',
    pool: Set[TaskTokens],
    ids: Set[TaskTokens],
    only_match_pool: bool = False,
) -> Tuple[Set[TaskTokens], Set[TaskTokens]]:
    """New Cylc 8.6.0 task matching interface.

    Args:
        config:
            The workflow config.
        pool:
            The IDs in the pool of active tasks to match as a set of tokens.
            The Tokens should include the task state using `task_sel` to
            support task state matching.
        ids:
            The provided IDs to match.
        only_match_pool:
            If True, tasks outside of the provided pool will not be matched.

    Returns:
        (matched, unmatched)

    """
    unmatched: Set[TaskTokens] = set()

    # mapping of family name to all contained tasks
    family_lookup: Dict[str, Set[str]] = _get_family_lookup(config)

    # set of all active cycles
    all_cycles: Set[str] = {tokens['cycle'] for tokens in pool}

    # set of all possible namespaces (tasks + families)
    all_namespaces: Dict[str, Any] = config.get_namespace_list(
        'all namespaces'
    )

    # separate IDs targeting active tasks ONLY from the remainder
    active_only_ids = {
        id_
        for id_ in ids
        if id_.get('task_sel') or id_.get('cycle_sel')
    }
    plain_ids = ids - active_only_ids

    # match active-only IDs
    active_only_ids, _unmatched = _match(
        config,
        pool,
        active_only_ids,
        family_lookup,
        all_cycles,
        all_namespaces,
        only_match_pool=True,
        match_selectors=True,
    )
    unmatched.update(_unmatched)

    # match IDs
    plain_ids, _unmatched = _match(
        config,
        pool,
        plain_ids,
        family_lookup,
        all_cycles,
        all_namespaces,
        only_match_pool=only_match_pool,
    )
    unmatched.update(_unmatched)

    return {*active_only_ids, *plain_ids}, unmatched


def _match(
    config: 'WorkflowConfig',
    pool: Set[TaskTokens],
    ids: Set[TaskTokens],
    family_lookup: Dict[str, Set[str]],
    all_cycles: Set[str],
    all_namespaces: Dict[str, Any],
    only_match_pool: bool = False,
    match_selectors: bool = False,
) -> Tuple[Set[TaskTokens], Set[TaskTokens]]:
    # results
    unmatched: Set[TaskTokens] = set()
    matched: Set[TaskTokens] = set()

    for id_ in ids:
        # replace the "^" token with the initial cycle point
        if id_['cycle'] == '^':
            id_ = id_.duplicate(cycle=str(config.initial_point))

        # replace the "$" token with the final cycle point
        elif id_['cycle'] == '$':
            if config.final_point:
                id_ = id_.duplicate(cycle=str(config.final_point))
            else:
                LOG.warning(
                    'ID references final cycle point, but none is set:'
                    f' {id_.relative_id}'
                )
                unmatched.add(id_)
                continue

        # match cycles
        if contains_fnmatch(id_['cycle']):
            _cycles = _fnmatchcase_glob(id_['cycle'], all_cycles)
        else:
            _cycles = {id_['cycle']}

        # match tasks
        _namespace = id_.get('task', '*') or 'root'
        _tasks = {
            task
            for namespace in _fnmatchcase_glob(_namespace, all_namespaces)
            for task in family_lookup.get(namespace, {namespace})
        }

        # expand matched IDs
        _matched = {
            TaskTokens(
                cycle=_cycle,
                task=_task,
                task_sel=id_.get('task_sel') or id_.get('cycle_sel'),
            )
            for _cycle in _cycles
            for _task in _tasks
        }

        if only_match_pool and match_selectors:
            # filter against active tasks
            _matched = _matched.intersection(pool)
        elif only_match_pool:
            _matched = _matched.intersection({
                pool_task_id.duplicate(task_sel=None)
                for pool_task_id in pool
            })
        else:
            # filter for on-sequence task instances
            for id__ in list(_matched):
                try:
                    taskdef = config.taskdefs[id__['task']]
                    if not taskdef.is_valid_point(get_point(id__['cycle'])):
                        _matched.remove(id__)
                        if (
                            # was the specified ID a pattern?
                            not contains_fnmatch(id_['task'])
                            and not contains_fnmatch(id_['cycle'])
                        ):
                            # the cycle point is not valid for this task
                            # NOTE: only log this if the user asked for a
                            # specific cycle/task
                            LOG.warning(
                                'Invalid cycle point for task:'
                                f' {id__["task"]}, {id__["cycle"]}'
                            )
                except (ValueError, KeyError):
                    _matched.remove(id__)

        if _matched:
            matched = matched.union(_matched)
        else:
            unmatched.add(id_)

    return matched, unmatched


def _fnmatchcase_glob(pattern: str, values: Iterable[str]) -> Set[str]:
    """Convenience function for globbing over a list of values.

    This uses the "fnmatchcase" function which is shell glob like.

    Args:
        Pattern: The glob.
        Values: The things to evaluate the glob over.

    Examples:
        >>> sorted(_fnmatchcase_glob('*', {'a', 'b', 'c'}))
        ['a', 'b', 'c']

        >>> sorted(_fnmatchcase_glob('a*', {'a1', 'a2', 'b1'}))
        ['a1', 'a2']

    """
    return {
        value
        for value in values
        if fnmatchcase(value, pattern)
    }


def _get_family_lookup(config: 'WorkflowConfig') -> Dict[str, Set[str]]:
    """Return a dict mapping families to all contained tasks.

    This recursively expands families avoiding the need to do so later.
    """
    lookup = deepcopy(config.runtime['descendants'])

    def _iter():
        ret = False
        for namespaces in lookup.values():
            for namespace in list(namespaces):
                if namespace in config.runtime['descendants']:
                    ret = True
                    namespaces.remove(namespace)
                    namespaces.update(config.runtime['descendants'][namespace])
        return ret

    while _iter():
        pass

    return lookup
