# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
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
"""Automatically restart suites if they are running on bad servers.

Loads in the global configuration to check if the server a suite is running
on is listed in ``[suite hosts]condemned hosts``.

This is useful if a host needs to be taken off-line e.g. for scheduled
maintenance.

This functionality is configured via the following site configuration
settings:

- ``[run hosts][suite servers]auto restart delay``
- ``[run hosts][suite servers]condemned hosts``
- ``[run hosts][suite servers]run hosts``

The auto stop-restart feature has two modes:

- [Normal Mode]

  - When a host is added to the ``condemned hosts`` list, any suites
    running on that host will automatically shutdown then restart selecting a
    new host from ``run hosts``.
  - For safety, before attempting to stop the suite cylc will first wait
    for any jobs running locally (under background or at) to complete.
  - *In order for Cylc to be able to successfully restart suites the
    ``run hosts`` must all be on a shared filesystem.*

- [Force Mode]

  - If a host is suffixed with an exclamation mark then Cylc will not attempt
    to automatically restart the suite and any local jobs (running under
    background or at) will be left running.

For example in the following configuration any suites running on
``foo`` will attempt to restart on ``pub`` whereas any suites
running on ``bar`` will stop immediately, making no attempt to restart.

.. code-block:: cylc

   [suite servers]
       run hosts = pub
       condemned hosts = foo, bar!

.. warning::

   Cylc will reject hosts with ambiguous names such as ``localhost`` or
   ``127.0.0.1`` for this configuration as ``condemned hosts`` are evaluated
   on the suite host server.

To prevent large numbers of suites attempting to restart simultaneously the
``auto restart delay`` setting defines a period of time in seconds.
Suites will wait for a random period of time between zero and
``auto restart delay`` seconds before attempting to stop and restart.

Suites that are started up in no-detach mode cannot auto stop-restart on a
different host - as it will still end up attached to the condemned host.
Therefore, a suite in no-detach mode running on a condemned host will abort
with a non-zero return code. The parent process should manually handle the
restart of the suite if desired.

See the ``[suite servers]`` configuration section

(:ref:`global-suite-servers`) for more details.

"""
from random import random
from time import time
import traceback

from cylc.flow import LOG
from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.exceptions import HostSelectException
from cylc.flow.host_select import select_suite_host
from cylc.flow.hostuserutil import get_fqdn_by_host
from cylc.flow.main_loop import periodic
from cylc.flow.suite_status import AutoRestartMode
from cylc.flow.wallclock import (
    get_time_string_from_unix_time as time2str
)


@periodic
async def auto_restart(scheduler, _):
    """Automatically restart the suite if configured to do so."""
    current_glbl_cfg = glbl_cfg(cached=False)
    mode = _should_auto_restart(scheduler, current_glbl_cfg)

    if mode:
        LOG.info('The Cylc suite host will soon become un-available.')
        _set_auto_restart(
            scheduler,
            restart_delay=current_glbl_cfg.get(
                ['suite servers', 'auto restart delay']
            ),
            mode=mode
        )


def _should_auto_restart(scheduler, current_glbl_cfg):
    # check if suite host is condemned - if so auto restart
    if scheduler.stop_mode is None:
        for host in current_glbl_cfg.get(
                ['suite servers', 'condemned hosts']
        ):
            if host.endswith('!'):
                # host ends in an `!` -> force shutdown mode
                mode = AutoRestartMode.FORCE_STOP
                host = host[:-1]
            else:
                # normal mode (stop and restart the suite)
                mode = AutoRestartMode.RESTART_NORMAL
                if scheduler.auto_restart_time is not None:
                    # suite is already scheduled to stop-restart only
                    # AutoRestartMode.FORCE_STOP can override this.
                    continue

            if get_fqdn_by_host(host) == scheduler.host:
                # this host is condemned, take the appropriate action

                return mode
    return False


def _can_auto_restart():
    """Determine whether this suite can safely auto stop-restart."""
    # Check whether there is currently an available host to restart on.
    try:
        select_suite_host(cached=False)
    except HostSelectException:
        LOG.critical(
            'Suite cannot automatically restart because:\n' +
            'No alternative host to restart suite on.')
        return False
    except Exception:
        # Any unexpected error in host selection shouldn't be able to take
        # down the suite.
        LOG.critical(
            'Suite cannot automatically restart because:\n' +
            'Error in host selection:\n' +
            traceback.format_exc())
        return False
    else:
        return True


def _set_auto_restart(
        scheduler,
        restart_delay=None,
        mode=AutoRestartMode.RESTART_NORMAL
):
    """Configure the suite to automatically stop and restart.

    Restart handled by `suite_auto_restart`.

    Args:
        scheduler (cylc.flow.scheduler.Scheduler):
            Scheduler instance of the running suite.
        restart_delay (cylc.flow.parsec.DurationFloat):
            Suite will wait a random period between 0 and
            `restart_delay` seconds before attempting to stop/restart in
            order to avoid multiple suites restarting simultaneously.
        mode (str): Auto stop-restart mode.

    Return:
        bool: False if it is not possible to automatically stop/restart
        the suite due to its configuration/runtime state.
    """
    # Check that the suite isn't already shutting down.
    if scheduler.stop_mode:
        return True

    # Force mode, stop the suite now, don't restart it.
    if mode == AutoRestartMode.FORCE_STOP:
        LOG.critical(
            'This suite will be shutdown as the suite '
            'host is unable to continue running it.\n'
            'When another suite host becomes available '
            'the suite can be restarted by:\n'
            '    $ cylc restart %s', scheduler.suite)
        if scheduler.auto_restart_time:
            LOG.info('Scheduled automatic restart canceled')
        scheduler.auto_restart_time = time()
        scheduler.auto_restart_mode = mode
        return True

    # Check suite isn't already scheduled to auto-stop.
    if scheduler.auto_restart_time is not None:
        return True

    # Suite host is condemned and suite running in no detach mode.
    # Raise an error to cause the suite to abort.
    # This should raise an "abort" event and return a non-zero code to the
    # caller still attached to the suite process.
    if scheduler.options.no_detach:
        raise RuntimeError('Suite host condemned in no detach mode')

    # Check suite is able to be safely restarted.
    if not _can_auto_restart():
        return False

    LOG.info('Suite will automatically restart on a new host.')
    if restart_delay is not None and restart_delay != 0:
        if restart_delay > 0:
            # Delay shutdown by a random interval to avoid many
            # suites restarting simultaneously.
            shutdown_delay = int(random() * restart_delay)  # nosec
        else:
            # Un-documented feature, schedule exact restart interval for
            # testing purposes.
            shutdown_delay = abs(int(restart_delay))
        shutdown_time = time() + shutdown_delay
        LOG.info('Suite will restart in %ss (at %s)', shutdown_delay,
                 time2str(shutdown_time))
        scheduler.auto_restart_time = shutdown_time
    else:
        scheduler.auto_restart_time = time()

    scheduler.auto_restart_mode = AutoRestartMode.RESTART_NORMAL

    return True
