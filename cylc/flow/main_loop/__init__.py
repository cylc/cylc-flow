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
"""Plugins for running Python code inside of the Cylc scheduler.

.. _BuiltInPlugins:

Built In Plugins
----------------

Cylc Flow provides the following plugins:

.. autosummary::
   :toctree: built-in
   :template: main_loop_plugin.rst

   cylc.flow.main_loop.auto_restart
   cylc.flow.main_loop.health_check
   cylc.flow.main_loop.log_data_store
   cylc.flow.main_loop.log_main_loop
   cylc.flow.main_loop.log_memory
   cylc.flow.main_loop.reset_bad_hosts

.. Note: Autosummary generates files in this directory, these are cleaned
         up by `make clean`.


Configuring
-----------

Main loop plugins can be activated either by:

* Using the ``--main-loop`` option with ``cylc play`` e.g:

  .. code-block:: console

     $ # run a workflow using the "health check" and "auto restart" plugins:
     $ cylc play my-workflow --main-loop 'health check' \
--main-loop 'auto restart'

* Adding them to the default list of plugins in
  :cylc:conf:`global.cylc[scheduler][main loop]plugins` e.g:

  .. code-block:: cylc

     [scheduler]
         [[main loop]]
             plugins = health check, auto restart

Main loop plugins can be individually configured in their
:cylc:conf:`global.cylc[scheduler][main loop][<plugin name>]` section e.g:

.. code-block:: cylc

   [scheduler]
       [[main loop]]
           [[[health check]]]
               interval = PT5M  # perform check every 5 minutes


Developing Main Loop Plugins
----------------------------

Main loop plugins are Python modules containing asynchronous function(s)
(sometimes referred to as coroutines) which Cylc Flow executes within the
scheduler.

Hello World
^^^^^^^^^^^

Here is the "hello world" of main loop plugins:

.. code-block:: python
   :caption: my_plugin.py

   from cylc.flow import LOG
   from cylc.flow.main_loop import startup

   @startup
   async def my_startup_coroutine(schd, state):
      # write Hello <workflow name> to the Cylc log.
      LOG.info(f'Hello {schd.workflow}')

Plugins are registered by registering them with the ``cylc.main_loop``
entry point:

.. code-block:: python
   :caption: setup.py

   # plugins must be properly installed, in-place PYTHONPATH meddling will
   # not work.

   from setuptools import setup

   setup(
       name='my-plugin',
       version='1.0',
       py_modules=['my_plugin'],
       entry_points={
          # register this plugin with Cylc
          'cylc.main_loop': [
            # name = python.namespace.of.module
            'my_plugin=my_plugin.my_plugin'
          ]
       }
   )

Examples
^^^^^^^^

For examples see the built-in plugins in the :py:mod:`cylc.flow.main_loop`
module which are registered in the Cylc Flow ``setup.cfg`` file.

Coroutines
^^^^^^^^^^

.. _coroutines: https://docs.python.org/3/library/asyncio-task.html#coroutines

Plugins provide asynchronous functions (`coroutines`_) which Cylc will
then run inside the scheduler.

Coroutines should be fast running (read as gentle on the scheduler)
and perform IO asynchronously.

Coroutines shouldn't meddle with the state of the scheduler and should be
parallel-safe with other plugins.

Event Types
^^^^^^^^^^^

Coroutines must be decorated using one of the main loop decorators. The
choice of decorator effects when the coroutine is called and what
arguments are provided to it.

The available event types are:

.. autofunction:: cylc.flow.main_loop.startup

.. autofunction:: cylc.flow.main_loop.shutdown

.. autofunction:: cylc.flow.main_loop.periodic

"""
from collections import deque
from inspect import (
    getmembers,
    isfunction
)
from textwrap import indent
from time import time

from cylc.flow import LOG, iter_entry_points
from cylc.flow.exceptions import CylcError, InputError, PluginError


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
    """Decorates a coroutine which is run at workflow startup.

    The decorated coroutine should have the signature:

        ``async coroutine(scheduler, plugin_state) -> None``

    Exceptions:

        * Regular Exceptions are caught and logged.
        * Exceptions which subclass CylcError are re-raised as
          MainLoopPluginException

    """
    fcn.main_loop = CoroTypes.StartUp
    return fcn


def shutdown(fcn):
    """Decorates a coroutine which is run at workflow shutdown.

    Note shutdown refers to "clean" shutdown as opposed to workflow abort.

    The decorated coroutine should have the signature:

        ``async coroutine(scheduler, plugin_state) -> None``

    Exceptions:

        * Regular Exceptions are caught and logged.
        * Exceptions which subclass CylcError are re-raised as
          MainLoopPluginException

    """
    fcn.main_loop = CoroTypes.ShutDown
    return fcn


def periodic(fcn):
    """Decorates a coroutine which is run at a set interval.

    The decorated coroutine should have the signature:

        ``async coroutine(scheduler, plugin_state) -> None``

    Exceptions:

        * Regular Exceptions are caught and logged.
        * Exceptions which subclass CylcError are re-raised as
          MainLoopPluginException

    Configuration:

        * The interval of execution can be altered using
          :cylc:conf:`global.cylc[scheduler][main loop][<plugin name>]interval`

    """
    fcn.main_loop = CoroTypes.Periodic
    return fcn


class CoroTypes:
    """Different types of coroutine which can be used with the main loop."""

    StartUp = startup
    ShutDown = shutdown
    Periodic = periodic


def load(config, additional_plugins=None):
    additional_plugins = additional_plugins or []
    entry_points = {
        entry_point.name: entry_point
        for entry_point in
        iter_entry_points('cylc.main_loop')
    }
    plugins = {
        'state': {},
        'timings': {}
    }
    for plugin_name in set(config['plugins'] + additional_plugins):
        # get plugin
        try:
            entry_point = entry_points[plugin_name.replace(' ', '_')]
        except KeyError:
            raise InputError(
                f'No main-loop plugin: "{plugin_name}"\n'
                + '    Available plugins:\n'
                + indent('\n'.join(sorted(entry_points)), '        ')
            )
        # load plugin
        try:
            module = entry_point.load()
        except Exception as exc:
            raise PluginError(
                'cylc.main_loop', entry_point.name, exc
            )
        # load coroutines
        log = []
        for coro_name, coro in getmembers(module):
            if isfunction(coro) and hasattr(coro, 'main_loop'):
                log.append(coro_name)
                plugins.setdefault(
                    coro.main_loop, {}
                )[(plugin_name, coro_name)] = coro
                plugins['timings'][(plugin_name, coro_name)] = deque(maxlen=1)
        LOG.debug(
            'Loaded main loop plugin "%s":\n%s',
            plugin_name,
            '\n'.join(f'* {x}' for x in log)
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
