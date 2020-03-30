# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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
"""Periodic functions which run in Cylc's main scheduling loop.

For health check, diagnostic and devlopment purposes.

Plugins are modules which provide one or more of the following functions:

``async before(scheduler: Scheduler, state: dict) -> None``
   Called before entring the main loop, use this function set the initial
   state.
``async during(scheduler: Scheduler, state: dict) -> None``
   Called with each main loop iteration.
``async on_change(scheduler, state) -> None``
   Called with main loop iterations when changes have occurred in the task
   pool during the current iteration.
``async after(scheduler: Scheduler, state: dict) -> None``
   Called after the main loop has completed in the event of a controlled
   shutdown (e.g. ``cylc stop <suite>``).

The ``during`` and ``on_change`` functions should be fast running. To
reduce the impact on the running suite specify the minimum interval
between calls using the ``[cylc][main loop][PLUGIN]interval`` setting.

Plugins are registered using the `main_loop` entry point, for examples see
the built-in plugins in the :py:mod:`cylc.flow.main_loop` module which
are registered in the Cylc Flow ``setup.cfg`` file.

Plugins shouldn't meddle with the state of the scheduler and should be
parallel-safe with other plugins.

"""
import asyncio
from collections import deque
from inspect import (
    getmembers,
    isfunction
)
from time import time

import pkg_resources

from cylc.flow import LOG
from cylc.flow.exceptions import CylcError, UserInputError


class MainLoopPluginException(Exception):
    """Raised in-place of CylcError exceptions.

    Note:
        * Not an instace of CylcError as that is used for controlled
          shutdown e.g. SchedulerStop.

    """


async def _wrapper(fcn, scheduler, state, timings=None):
    """Wrapper for all plugin functions.

    * Logs the function's execution.
    * Times the function.
    * Catches any exceptions which aren't subclasses of CylcError.

    """
    sig = f'{fcn.__module__}:{fcn.__name__}'
    LOG.debug(f'main_loop [run] {sig}')
    start_time = time()
    try:
        await fcn(scheduler, state)
    except CylcError as exc:
        # allow CylcErrors through (e.g. SchedulerStop)
        # NOTE: the `from None` bit gets rid of this gunk:
        # > During handling of the above exception another exception
        raise MainLoopPluginException(exc) from None
    except Exception as exc:
        LOG.error(f'Error in main loop plugin {sig}')
        LOG.exception(exc)
    duration = time() - start_time
    LOG.debug(f'main_loop [end] {sig} ({duration:.3f}s)')
    if timings is not None:
        timings.append((start_time, duration))


def _debounce(interval, timings):
    """Rate limiter, returns True if the interval has elapsed.

    Arguments:
        interval (float):
            Time interval in seconds as a float-type object.
        timings (list):
            List-list object of the timings of previous runs in the form
            ``(completion_wallclock_time, run_duration)``.
            Wallclock times are unix epoch times in seconds.

    Examples:
        >>> from time import time

        No previous run (should always return True):
        >>> _debounce(1., [(0, 0)])
        True

        Interval not yet elapsed since previous run:
        >>> _debounce(1., [(time(), 0)])
        False

        Interval has elapsed since previous run:
        >>> _debounce(1., [(time() - 2, 0)])
        True

    """
    if not interval:
        return True
    try:
        last_run_at = timings[-1][0]
    except IndexError:
        last_run_at = 0
    if (time() - last_run_at) > interval:
        return True
    return False


def startup(fcn):
    fcn.main_loop = CoroTypes.StartUp
    return fcn


def shutdown(fcn):
    fcn.main_loop = CoroTypes.ShutDown
    return fcn


def periodic(fcn):
    fcn.main_loop = CoroTypes.Periodic
    return fcn


class CoroTypes:
    StartUp = startup
    ShutDown = shutdown
    Periodic = periodic


def load(config, additional_plugins=None):
    additional_plugins = additional_plugins or []
    entry_points = pkg_resources.get_entry_map(
        'cylc-flow'
    ).get('main_loop', {})
    plugins = {
        'state': {},
        'timings': {}
    }
    for plugin_name in config['plugins'] + additional_plugins:
        # get plugin
        try:
            module_name = entry_points[plugin_name.replace(' ', '_')]
        except KeyError:
            raise UserInputError(f'No main-loop plugin: "{plugin_name}"')
        # load plugin
        try:
            module = module_name.load()
        except Exception:
            raise CylcError(f'Could not load plugin: "{plugin_name}"')
        # load coroutines
        log = []
        for coro_name, coro in (
                (coro_name, coro)
                for coro_name, coro in getmembers(module)
                if isfunction(coro)
                if hasattr(coro, 'main_loop')
        ):
            log.append(coro_name)
            plugins.setdefault(
                coro.main_loop, {}
            )[(plugin_name, coro_name)] = coro
            plugins['timings'][(plugin_name, coro_name)] = deque(maxlen=1)
        LOG.debug(
            'Loaded main loop plugin "%s": %s',
            plugin_name + '\n',
            '\n'.join((f'* {x}' for x in log))
        )
        # set the initial state of the plugin
        plugins['state'][plugin_name] = {}
    # make a note of the config here for ease of reference
    plugins['config'] = config
    return plugins


def get_runners(plugins, coro_type, scheduler):
    return [
        _wrapper(
            coro,
            scheduler,
            plugins['state'][plugin_name],
            timings=plugins['timings'][(plugin_name, coro_name)]
        )
        for (plugin_name, coro_name), coro
        in plugins.get(coro_type, {}).items()
        if coro_type != CoroTypes.Periodic
        or _debounce(
            plugins['config'].get(plugin_name, {}).get('interval', None),
            plugins['timings'][(plugin_name, coro_name)]
        )
    ]
