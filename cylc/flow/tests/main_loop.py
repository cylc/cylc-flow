import asyncio
from functools import partial
import logging
from time import sleep

import pytest

from cylc.flow import CYLC_LOG
from cylc.flow.exceptions import CylcError
from cylc.flow.main_loop import (
    load_plugins,
    _wrapper,
    before,
    during,
    after
)
from cylc.flow.main_loop.health_check import during as hc_during


def test_load_plugins_blank():
    """Test that log_plugins works when no plugins are requested."""
    conf = {
        'plugins': []
    }
    assert load_plugins(conf) == {
        'before': {},
        'during': {},
        'on_change': {},
        'after': {},
        'state': {},
        'config': conf
    }


def test_load_plugins():
    """Test the loading of a built-in plugin."""
    conf = {
        'plugins': ['health check'],
        'health check': {
            'interval': 1234
        }
    }
    assert load_plugins(conf) == {
        'before': {},
        'during': {
            'health check': hc_during
        },
        'on_change': {},
        'after': {},
        'state': {
            'health check': {
                'last run at': 0
            }
        },
        'config': conf
    }


def test_wrapper_calls_function():
    """Ensure the wrapper calls coroutines."""
    flag = False
    async def test_coro(arg1, arg2):
        assert arg1 == 'arg1'
        assert arg2 == 'arg2'
        nonlocal flag
        flag = True
    coro = _wrapper(
        test_coro,
        ('arg1', 'arg2')
    )
    asyncio.run(coro)
    assert flag


def test_wrapper_logging(caplog):
    """Ensure the wrapper logs each coroutine call."""
    async def test_coro():
        pass
    coro = _wrapper(
        test_coro,
        tuple()
    )
    with caplog.at_level(logging.DEBUG, logger=CYLC_LOG):
        asyncio.run(coro)
    assert len(caplog.record_tuples) == 2
    (
        (run_log, run_level, run_msg),
        (end_log, end_level, end_msg)
    ) = caplog.record_tuples
    # we should have two messages, one sent before and one after
    # the function
    assert 'run' in run_msg
    assert 'end' in end_msg
    # both should contain the name of the function
    assert 'test_coro' in run_msg
    assert 'test_coro' in end_msg
    # and should be sent to the cylc logger at the debug level
    assert run_log == end_log == CYLC_LOG
    assert run_level == end_level == logging.DEBUG


def test_wrapper_catches_exceptions(caplog):
    """Ensure the wrapper catches Exception instances and logs them."""
    async def test_coro():
        raise Exception('foo')
    coro = _wrapper(
        test_coro,
        tuple()
    )
    with caplog.at_level(logging.DEBUG, logger=CYLC_LOG):
        asyncio.run(coro)
    assert len(caplog.record_tuples) == 3
    run, error, traceback = caplog.record_tuples
    assert 'run' in run[2]
    assert error[1] == logging.ERROR
    assert traceback[1] == logging.ERROR
    assert 'foo' in traceback[2]


def test_wrapper_passes_cylc_error():
    """Ensure the wrapper does not catch CylcError instances."""
    async def test_coro():
        raise CylcError('foo')
    coro = _wrapper(
        test_coro,
        tuple()
    )
    with pytest.raises(CylcError):
        asyncio.run(coro)


def test_before():
    """Ensure the before function calls all before coros."""
    calls = []
    def capture(*stuff):
        nonlocal calls
        calls.append(stuff)
    plugins = {
        'before': {
            'foo': capture,
            'bar': capture,
            'baz': capture
        },
        'state': {
            'foo': {'a': 1},
            'bar': {'b': 2},
            'baz': {'c': 3}
        }
    }
    asyncio.run(before(plugins, 42))
    assert calls == [
        (42, {'a': 1}),
        (42, {'b': 2}),
        (42, {'c': 3}),
    ]

@pytest.fixture
def test_plugins():
    return {
        'state': {
            'foo': {
                'calls': [],
                'name': 'foo',
                'last run at': 0
            },
            'bar': {
                'calls': [],
                'name': 'bar',
                'last run at': 0
            },
            'baz': {
                'calls': [],
                'name': 'baz',
                'last run at': 0
            }
        },
        'config': {
            'foo': {
                'interval': 1
            },
            'bar': {
                'interval': 1
            },
            'baz': {
                'interval': 1
            },
        }
    }


def test_during(test_plugins):
    """Ensure the during function calls all during and on_change coros."""
    calls = []
    def capture_during(_, state):
        nonlocal calls
        state['calls'].append(f'during_{state["name"]}')
        calls.append(list(state['calls']))
    def capture_on_change(_, state):
        nonlocal calls
        state['calls'].append(f'on_change_{state["name"]}')
        calls.append(list(state['calls']))
    test_plugins.update({
        'during': {
            'foo': capture_during,
            'bar': capture_during,
            'baz': capture_during
        },
        'on_change': {
            'bar': capture_on_change,
        }
    })
    asyncio.run(during(test_plugins, 42, True))
    assert len(calls) == 4
    assert calls == [
        # ensure the functions were called in the correct order
        ['during_foo'],
        ['during_bar'],
        ['during_baz'],
        ['during_bar', 'on_change_bar']
    ]


def test_during_interval(test_plugins):
    def capture_during(_, state):
        state['calls'].append(f'during_{state["name"]}')
    def capture_on_change(_, state):
        state['calls'].append(f'on_change_{state["name"]}')
    test_plugins.update({
        'during': {
            'foo': capture_during,
            'bar': capture_during
        },
        'on_change': {
            'foo': capture_on_change,
            'baz': capture_on_change
        }
    })

    calls = {
        'bar': ['during_bar'],
        'baz': ['on_change_baz'],
        'foo': ['during_foo', 'on_change_foo']
    }

    # run the handlers for the first time
    asyncio.run(during(test_plugins, 42, True))
    assert {
        name: state['calls']
        for name, state in sorted(test_plugins['state'].items())
    } == calls

    # now re-wind the clock 0.5 seconds
    for state in test_plugins['state'].values():
        state['last run at'] = state['last run at'] - 0.5

    # the config runs the plugins every 1 second so they shouldn't run
    asyncio.run(during(test_plugins, 42, True))
    assert {
        name: state['calls']
        for name, state in sorted(test_plugins['state'].items())
    } == calls

    # now re-wind the clock another 0.5 seconds
    for state in test_plugins['state'].values():
        state['last run at'] = state['last run at'] - 0.6

    # the config runs the plugins every 1 second so they should now run
    for lst in calls.values():
        # the second run should be the same as the first
        lst.extend(lst)
    asyncio.run(during(test_plugins, 42, True))
    assert {
        name: state['calls']
        for name, state in sorted(test_plugins['state'].items())
    } == calls


def test_after():
    """Ensure the after function calls all after coros."""
    calls = []
    def capture(*stuff):
        nonlocal calls
        calls.append(stuff)
    plugins = {
        'after': {
            'foo': capture,
            'bar': capture,
            'baz': capture
        },
        'state': {
            'foo': {'a': 1},
            'bar': {'b': 2},
            'baz': {'c': 3}
        }
    }
    asyncio.run(after(plugins, 42))
    assert calls == [
        (42, {'a': 1}),
        (42, {'b': 2}),
        (42, {'c': 3}),
    ]
