from fnmatch import fnmatchcase
from typing import (
    Any,
    Callable,
    Iterable,
    List,
    TYPE_CHECKING,
    # Tuple,
    # Union,
    # overload,
)

from cylc.flow import LOG
from cylc.flow.id import Tokens
from cylc.flow.id_cli import contains_fnmatch

if TYPE_CHECKING:
    # from typing_extensions import Literal

    from cylc.flow.task_pool import Pool
    from cylc.flow.task_proxy import TaskProxy
    from cylc.flow.cycling import PointBase


# @overload
# def filter_ids(
#     pool: 'Pool',
#     ids: 'Iterable[str]',
#     *,
#     warn: 'bool' = True,
#     out: 'Literal[Tokens.Task]' = Tokens.Task,
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
#     out: 'Literal[Tokens.Cycle]' = Tokens.Cycle,
#     pattern_match: 'bool' = True,
# ) -> 'Tuple[List[PointBase], List[str]]':
#     ...


_RET = (
    'Union['
    'Tuple[List[TaskProxy], List[str]]'
    ', '
    'Tuple[List[PointBase], List[str]]'
    ']'
)


def filter_ids(
    pools: 'List[Pool]',
    ids: 'Iterable[str]',
    *,
    warn: 'bool' = True,
    out: 'Tokens' = Tokens.Task,
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

            * If Tokens.Task all matching TaskProxies will be returned.
            * If Tokens.Cycle all CyclePoints with any matching tasks will
              be returned.
        warn:
            Whether to log a warning if no matching tasks are found.

    TODO:
        Consider using wcmatch which would add support for
        extglobs, namely brace syntax e.g. {foo,bar}.

    """
    if out not in {Tokens.Cycle, Tokens.Task}:
        raise ValueError(f'Invalid output format: {out}')

    _cycles: 'List[PointBase]' = []
    _tasks: 'List[TaskProxy]' = []
    _not_matched: 'List[str]' = []

    # enable / disable pattern matching
    match: 'Callable[[Any, Any], bool]'
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

    id_tokens_map = {}
    for id_ in ids:
        try:
            id_tokens_map[id_] = tokenise(id_, relative=True)
        except ValueError:
            _not_matched.append(id_)
            if warn:
                LOG.warning(f'Invalid ID: {id_}')

    for id_, tokens in id_tokens_map.items():
        for lowest_token in reversed(Tokens):
            if tokens.get(lowest_token.value):
                break

        cycles = []
        tasks = []

        # filter by cycle
        if lowest_token == Tokens.Cycle:
            cycle = tokens[Tokens.Cycle.value]
            cycle_sel = tokens.get(Tokens.Cycle.value + '_sel') or '*'
            for pool in pools:
                for icycle, itasks in pool.items():
                    if not itasks:
                        continue
                    str_cycle = str(icycle)
                    if not match(str_cycle, cycle):
                        continue
                    if cycle_sel == '*':
                        cycles.append(icycle)
                        continue
                    for itask in itasks.values():
                        if match(itask.state.status, cycle_sel):
                            cycles.append(icycle)
                            break

        # filter by task
        elif lowest_token == Tokens.Task:  # noqa: SIM106
            cycle = tokens[Tokens.Cycle.value]
            cycle_sel_raw = tokens.get(Tokens.Cycle.value + '_sel')
            cycle_sel = cycle_sel_raw or '*'
            task = tokens[Tokens.Task.value]
            task_sel_raw = tokens.get(Tokens.Task.value + '_sel')
            task_sel = task_sel_raw or '*'
            for pool in pools:
                for icycle, itasks in pool.items():
                    str_cycle = str(icycle)
                    if not match(str_cycle, cycle):
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
                            and (
                                # task name
                                match(itask.tdef.name, task)
                                # family name
                                or any(
                                    match(ns, task)
                                    for ns in itask.tdef.namespace_hierarchy
                                )
                            )
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
            _cycles.extend(cycles)
            _tasks.extend(tasks)

    ret: 'List[Any]' = []
    if out == Tokens.Cycle:
        _cycles.extend({
            itask.point
            for itask in _tasks
        })
        ret = _cycles
    elif out == Tokens.Task:
        for pool in pools:
            for icycle in _cycles:
                if icycle in pool:
                    _tasks.extend(pool[icycle].values())
        ret = _tasks
    return ret, _not_matched


from types import SimpleNamespace

import pytest

from cylc.flow.id import tokenise


@pytest.fixture
def task_pool():
    def _task_proxy(id_, hier):
        tokens = tokenise(id_, relative=True)
        itask = SimpleNamespace()
        itask.id_ = id_
        itask.point = int(tokens['cycle'])
        itask.state = SimpleNamespace()
        itask.state.status = tokens['task_sel']
        itask.tdef = SimpleNamespace()
        itask.tdef.name = tokens['task']
        if tokens['task'] in hier:
            hier = hier[tokens['task']]
        else:
            hier = []
        hier.append('root')
        itask.tdef.namespace_hierarchy = hier
        return itask

    def _task_pool(pool, hier) -> 'Pool':
        return {
            cycle: {
                id_.split(':')[0]: _task_proxy(id_, hier)
                for id_ in ids
            }
            for cycle, ids in pool.items()
        }

    return _task_pool


@pytest.mark.parametrize(
    'ids,matched,not_matched',
    [
        (
            ['1'],
            ['1/a:x', '1/b:x', '1/c:x'],
            []
        ),
        (
            ['2'],
            [],
            ['2']
        ),
        (
            ['*'],
            ['1/a:x', '1/b:x', '1/c:x'],
            []
        ),
        (
            ['1/*'],
            ['1/a:x', '1/b:x', '1/c:x'],
            []
        ),
        (
            ['2/*'],
            [],
            ['2/*']
        ),
        (
            ['*/*'],
            ['1/a:x', '1/b:x', '1/c:x'],
            []
        ),
        (
            ['*/a'],
            ['1/a:x'],
            []
        ),
        (
            ['*/z'],
            [],
            ['*/z']
        ),
        (
            ['*/*:x'],
            ['1/a:x', '1/b:x', '1/c:x'],
            [],
        ),
        (
            ['*/*:y'],
            [],
            ['*/*:y'],
        ),
    ]
)
def test_filter_ids_task_mode(task_pool, ids, matched, not_matched):
    """Ensure tasks are returned in task mode."""
    pool = task_pool(
        {
            1: ['1/a:x', '1/b:x', '1/c:x']
        },
        {}
    )

    _matched, _not_matched = filter_ids([pool], ids)
    assert [itask.id_ for itask in _matched] == matched
    assert _not_matched == not_matched


@pytest.mark.parametrize(
    'ids,matched,not_matched',
    [
        (
            ['1/a'],
            [1],
            [],
        ),
        (
            ['1/*'],
            [1],
            [],
        ),
        (
            ['1/*:x'],
            [1],
            [],
        ),
        (
            ['1/*:y'],
            [],
            ['1/*:y'],
        ),
        (
            ['*/*:x'],
            [1],
            [],
        ),
        (
            ['1/z'],
            [],
            ['1/z'],
        ),
        (
            ['1'],
            [1],
            [],
        ),
        (
            ['3'],
            [],
            ['3'],
        ),
    ]
)
def test_filter_ids_cycle_mode(task_pool, ids, matched, not_matched):
    """Ensure cycle poinds are returned in cycle mode."""
    pool = task_pool(
        {
            1: ['1/a:x', '1/b:x'],
            2: ['1/a:x'],
            3: [],
        },
        {}
    )

    _matched, _not_matched = filter_ids([pool], ids, out=Tokens.Cycle)
    assert _matched == matched
    assert _not_matched == not_matched


def test_filter_ids_invalid(caplog):
    """Ensure invalid IDs are handled elegantly."""
    matched, not_matched = filter_ids([{}], ['#'])
    assert matched == []
    assert not_matched == ['#']
    assert caplog.record_tuples == [
        ('cylc', 30, 'No active tasks matching: #'),
    ]
    caplog.clear()
    matched, not_matched = filter_ids([{}], ['#'], warn=False)
    assert caplog.record_tuples == []


def test_filter_ids_pattern_match_off(task_pool):
    """Ensure filtering works when pattern matching is turned off."""
    pool = task_pool(
        {
            1: ['1/a:x'],
        },
        {}
    )

    _matched, _not_matched = filter_ids(
        [pool],
        ['1/a'],
        out=Tokens.Task,
        pattern_match=True,
    )
    assert [itask.id_ for itask in _matched] == ['1/a:x']
    assert _not_matched == []


def test_filter_ids_toggle_pattern_matching(task_pool, caplog):
    """Ensure pattern matching can be toggled on and off."""
    pool = task_pool(
        {
            1: ['1/a:x'],
        },
        {}
    )

    ids = ['*/*']

    # ensure pattern matching works
    _matched, _not_matched = filter_ids(
        [pool],
        ids,
        out=Tokens.Task,
        pattern_match=True,
    )
    assert [itask.id_ for itask in _matched] == ['1/a:x']
    assert _not_matched == []

    # ensure pattern matching can be disabled
    caplog.clear()
    _matched, _not_matched = filter_ids(
        [pool],
        ids,
        out=Tokens.Task,
        pattern_match=False,
    )
    assert [itask.id_ for itask in _matched] == []
    assert _not_matched == ['*/*']

    # ensure the ID is logged
    assert len(caplog.record_tuples) == 1
    assert '*/*' in caplog.record_tuples[0][2]


@pytest.mark.parametrize(
    'ids,matched,not_matched',
    [
        (['1/A'], ['1/a:x'], []),
        (['1/B'], ['1/b1:x', '1/b2:x'], []),
        (['1/C'], [], ['1/C']),
        (['1/root'], ['1/a:x', '1/b1:x', '1/b2:x'], []),
    ]
)
def test_filter_ids_namespace_hierarchy(task_pool, ids, matched, not_matched):
    """Ensure matching includes namespaces."""
    pool = task_pool(
        {
            1: ['1/a:x', '1/b1:x', '1/b2:x']
        },
        {
            'a': ['A'],
            'b1': ['B'],
            'b2': ['B'],
        },
    )

    _matched, _not_matched = filter_ids(
        [pool],
        ids,
        pattern_match=False,
    )

    assert [itask.id_ for itask in _matched] == matched
    assert _not_matched == not_matched
