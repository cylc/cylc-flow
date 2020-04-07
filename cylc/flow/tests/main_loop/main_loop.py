import asyncio
from collections import deque
from functools import partial
import logging
from time import sleep

import pytest

from cylc.flow import CYLC_LOG
from cylc.flow.exceptions import CylcError
from cylc.flow.main_loop import (
    CoroTypes,
    MainLoopPluginException,
    _wrapper,
    get_runners,
    load,
)
from cylc.flow.main_loop.health_check import health_check as hc_during


def test_load_plugins_blank():
    """Test that log_plugins works when no plugins are requested."""
    conf = {
        'plugins': []
    }
    assert load(conf) == {
        'config': conf,
        'state': {},
        'timings': {}
    }


def test_load_plugins():
    """Test the loading of a built-in plugin."""
    conf = {
        'plugins': ['health check'],
        'health check': {
            'interval': 1234
        }
    }
    assert load(conf) == {
        CoroTypes.Periodic: {
            ('health check', 'health_check'): hc_during
        },
        'state': {
            'health check': {
            }
        },
        'config': conf,
        'timings': {
            ('health check', 'health_check'): deque([], maxlen=1)
        }
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
        'arg1',
        'arg2'
    )
    asyncio.run(coro)
    assert flag


def test_wrapper_logging(caplog):
    """Ensure the wrapper logs each coroutine call."""
    async def test_coro(*_):
        pass
    coro = _wrapper(
        test_coro,
        None,
        None
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
    async def test_coro(*_):
        raise Exception('foo')
    coro = _wrapper(
        test_coro,
        None,
        None
    )
    with caplog.at_level(logging.DEBUG, logger=CYLC_LOG):
        asyncio.run(coro)
    assert len(caplog.record_tuples) == 4
    run, error, traceback, completed = caplog.record_tuples
    assert 'run' in run[2]
    assert error[1] == logging.ERROR
    assert traceback[1] == logging.ERROR
    assert 'foo' in traceback[2]
    assert completed[1] == logging.DEBUG


def test_wrapper_passes_cylc_error():
    """Ensure the wrapper does not catch CylcError instances."""
    async def test_coro(*_):
        raise CylcError('foo')
    coro = _wrapper(
        test_coro,
        None,
        None
    )
    with pytest.raises(MainLoopPluginException):
        asyncio.run(coro)


@pytest.fixture
def basic_plugins():
    calls = []

    def capture(*args):
        nonlocal calls
        calls.append(args)

    plugins = {
        'config': {
            'periodic plugin': {
                'interval': 10
            }
        },
        'timings': {
            ('periodic plugin', 'periodic_coro'): [],
            ('startup plugin', 'startup_coro'): [],
        },
        'state': {
            'periodic plugin': {
                'a': 1
            },
            'startup plugin': {
                'b': 2
            }
        },
        CoroTypes.Periodic: {
            ('periodic plugin', 'periodic_coro'): capture
        },
        CoroTypes.StartUp: {
            ('startup plugin', 'startup_coro'): capture
        }
    }

    return (plugins, calls, capture)


def test_get_runners_startup(basic_plugins):
    """IT should return runners for startup functions."""
    plugins, calls, capture = basic_plugins
    runners = get_runners(
        plugins,
        CoroTypes.StartUp,
        'scheduler object'
    )
    assert len(runners) == 1
    asyncio.run(runners[0])
    assert calls == [('scheduler object', {'b': 2})]


def test_get_runners_periodic(basic_plugins):
    """It should return runners for periodic functions."""
    plugins, calls, capture = basic_plugins
    runners = get_runners(
        plugins,
        CoroTypes.Periodic,
        'scheduler object'
    )
    assert len(runners) == 1
    asyncio.run(runners[0])
    assert calls == [('scheduler object', {'a': 1})]


def test_get_runners_periodic_debounce(basic_plugins):
    """It should run periodic functions based on the configured interval."""
    plugins, calls, capture = basic_plugins

    # we should start with a blank timings object
    assert len(plugins['timings'][('periodic plugin', 'periodic_coro')]) == 0

    runners = get_runners(
        plugins,
        CoroTypes.Periodic,
        'scheduler object'
    )
    assert len(runners) == 1
    asyncio.run(runners[0])
    assert calls == [('scheduler object', {'a': 1})]

    # the timings object should now contain the previous run
    assert len(plugins['timings'][('periodic plugin', 'periodic_coro')]) == 1

    # the next run should be skipped because of the interval
    runners = get_runners(
        plugins,
        CoroTypes.Periodic,
        'scheduler object'
    )
    assert len(runners) == 0

    # if we remove the interval the next run will not get skipped
    plugins['config']['periodic plugin']['interval'] = 0
    runners = get_runners(
        plugins,
        CoroTypes.Periodic,
        'scheduler object'
    )
    assert len(runners) == 1
    assert calls[-1] == ('scheduler object', {'a': 1})


def test_state(basic_plugins):
    """It should pass the same state object with each function call.

    * Run the same plugin function twice.
    * Ensure that the state object recieved by each call is the same object.

    """
    plugins, calls, capture = basic_plugins
    runners = get_runners(
        plugins,
        CoroTypes.StartUp,
        'scheduler object'
    )
    assert len(runners) == 1
    asyncio.run(*runners)
    assert len(calls) == 1

    runners = get_runners(
        plugins,
        CoroTypes.StartUp,
        'scheduler object'
    )
    assert len(runners) == 1
    asyncio.run(*runners)
    assert len(calls) == 2

    (_, state1), (_, state2) = calls
    assert id(state1) == id(state2)
