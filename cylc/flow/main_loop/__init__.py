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


def load_plugins(config, additional_plugins=None):
    """Load main loop plugins from the suite/global configuration.

    Args:
        config (dict):
            The ``[cylc][main loop]`` section of the configuration.

    Returns:
        dict

    """
    if not additional_plugins:
        additional_plugins = []
    plugins = {
        'before': {},
        'during': {},
        'on_change': {},
        'after': {},
        'state': {}
    }
    entry_points = pkg_resources.get_entry_map(
        'cylc-flow').get('main_loop', {})
    for name in config['plugins'] + additional_plugins:
        mod_name = name.replace(' ', '_')
        # get plugin
        try:
            module_name = entry_points[mod_name]
        except KeyError:
            raise UserInputError(f'No main-loop plugin: "{name}"')
        # load plugin
        try:
            module = module_name.load()
        except Exception:
            raise CylcError(f'Could not load plugin: "{name}"')
        # load coroutines
        for key in plugins:
            coro = getattr(module, key, None)
            if coro:
                plugins[key][name] = coro
        # set initial conditions
        plugins['state'][name] = {'timings': deque(maxlen=1)}
    # make a note of the config here for ease of reference
    plugins['config'] = config
    return plugins


async def _wrapper(fcn, scheduler, state, timings=False):
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
    else:
        duration = time() - start_time
        LOG.debug(f'main_loop [end] {sig} ({duration:.3f}s)')
        if timings:
            state['timings'].append((start_time, duration))


async def before(plugins, scheduler):
    """Call all ``before`` plugin functions.

    Args:
        plugins (dict):
            Plugins dictionary as returned by
            :py:meth:`cylc.flow.main_loop.load_plugins`
        scheduler (cylc.flow.scheduler.Scheduler):
            Cylc Scheduler instance.

    """
    await asyncio.gather(
        *[
            _wrapper(
                coro,
                scheduler,
                plugins['state'][name],
                timings=False
            )
            for name, coro in plugins['before'].items()
        ]
    )


async def during(plugins, scheduler, has_changed):
    """Call all ``during`` and ``on_changed`` plugin functions.

    Args:
        plugins (dict):
            Plugins dictionary as returned by
            :py:meth:`cylc.flow.main_loop.load_plugins`
        scheduler (cylc.flow.scheduler.Scheduler):
            Cylc Scheduler instance.

    """
    coros = []
    now = time()
    items = list(plugins['during'].items())
    if has_changed:
        items.extend(plugins['on_change'].items())
    to_run = []
    for name, coro in items:
        interval = plugins['config'].get(name, {}).get('interval', None)
        state = plugins['state'][name]
        last_run_at = 0
        if state['timings']:
            last_run_at = state['timings'][-1][0]
        if (
                name in to_run  # allow both on_change and during to run
                or (
                    not interval
                    or now - last_run_at > interval
                )
        ):
            to_run.append(name)
            coros.append(
                _wrapper(
                    coro,
                    scheduler,
                    state,
                    timings=True
                )
            )
    await asyncio.gather(*coros)


async def after(plugins, scheduler):
    """Call all ``before`` plugin functions.

    Args:
        plugins (dict):
            Plugins dictionary as returned by
            :py:meth:`cylc.flow.main_loop.load_plugins`
        scheduler (cylc.flow.scheduler.Scheduler):
            Cylc Scheduler instance.

    """
    await asyncio.gather(
        *[
            _wrapper(
                coro,
                scheduler,
                plugins['state'][name],
                timings=False
            )
            for name, coro in plugins['after'].items()
        ]
    )
