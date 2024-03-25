#!/usr/bin/env python3

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

"""Common functionality related to the loading and calling of plugins."""

import os
from time import time

from cylc.flow import LOG, iter_entry_points
from cylc.flow.async_util import async_block as _async_block
from cylc.flow.exceptions import PluginError
import cylc.flow.flags


async def run_plugins_async(
    plugin_namespace,
    *args,
    async_block=False,
    **kwargs
):
    """Run all installed plugins for the given namespace.

    This runs plugins in series, yielding the results one by one.

    Args:
        plugin_namespace:
            The entry point namespace for the plugins to run,
            e.g. "cylc.post_install".
        args:
            Any arguments to call plugins with.
        async_block:
            If True, this will wait for any async tasks started by the plugin
            to complete before moving on to the next plugin.
        kwargs:
            Any kwargs to call plugins with.

    Yields:
        (entry_point, plugin_result)

        See https://github.com/cylc/cylc-rose/issues/274

    """
    startpoint = os.getcwd()
    for entry_point in iter_entry_points(plugin_namespace):
        try:
            # measure the import+run time for the plugin (debug mode)
            start_time = time()

            # load the plugin
            meth = entry_point.load()

            # run the plugin
            if async_block:
                # wait for any async tasks started by the plugin to complete
                async with _async_block():
                    plugin_result = meth(*args, **kwargs)
            else:
                plugin_result = meth(*args, **kwargs)

            # log the import+run time (debug mode)
            if cylc.flow.flags.verbosity > 1:
                LOG.debug(
                    f'ran {entry_point.name} in {time() - start_time:0.05f}s'
                )

            # yield the result to the caller
            yield entry_point, plugin_result

        except Exception as exc:  # NOTE: except Exception (purposefully vague)
            _raise_plugin_exception(exc, plugin_namespace, entry_point)

        finally:
            # ensure the plugin does not change the CWD
            os.chdir(startpoint)


def run_plugins(plugin_namespace, *args, **kwargs):
    """Run all installed plugins for the given namespace.

    This runs plugins in series, yielding the results one by one.

    Warning:
        Use run_plugins_async for "cylc.post_install" plugins.
        See https://github.com/cylc/cylc-rose/issues/274

    Args:
        plugin_namespace:
            The entry point namespace for the plugins to run,
            e.g. "cylc.post_install".
        args:
            Any arguments to call plugins with.
        kwargs:
            Any kwargs to call plugins with.

    Yields:
        (entry_point, plugin_result)

    """
    startpoint = os.getcwd()
    for entry_point in iter_entry_points(plugin_namespace):
        try:
            # measure the import+run time for the plugin (debug mode)
            start_time = time()

            # load the plugin
            meth = entry_point.load()

            # run the plugin
            plugin_result = meth(*args, **kwargs)

            # log the import+run time (debug mode)
            if cylc.flow.flags.verbosity > 1:
                LOG.debug(
                    f'ran {entry_point.name} in {time() - start_time:0.05f}s'
                )

            # yield the result to the caller
            yield entry_point, plugin_result

        except Exception as exc:  # NOTE: except Exception (purposefully vague)
            _raise_plugin_exception(exc, plugin_namespace, entry_point)

        finally:
            # ensure the plugin does not change the CWD
            os.chdir(startpoint)


def _raise_plugin_exception(exc, plugin_namespace, entry_point):
    """Re-Raise an exception captured from a plugin."""
    if cylc.flow.flags.verbosity > 1:
        # raise the full exception in debug mode
        # (this helps plugin developers locate the error in their code)
        raise
    # raise a user-friendly exception
    raise PluginError(
        plugin_namespace,
        entry_point.name,
        exc
    ) from None
