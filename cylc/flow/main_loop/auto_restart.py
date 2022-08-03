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
"""Automatically restart workflows if they are running on bad servers.

Loads in the global configuration to check if the server a workflow is running
on is listed in :cylc:conf:`global.cylc[scheduler][run hosts]condemned`.

This is useful if a host needs to be taken off-line e.g. for scheduled
maintenance.

This functionality is configured via the following site configuration
settings:

.. cylc-scope:: global.cylc

- :cylc:conf:`[scheduler]auto restart delay`
- :cylc:conf:`[scheduler][run hosts]condemned`
- :cylc:conf:`[scheduler][run hosts]available`



The auto stop-restart feature has two modes:

Normal Mode
   When a host is added to the
   :cylc:conf:`[scheduler][run hosts]condemned` list, any workflows
   running on that host will automatically shutdown then restart selecting a
   new host from :cylc:conf:`[scheduler][run hosts]available`.

   For safety, before attempting to stop the workflow Cylc will first wait
   for any jobs running locally (under background or at) to complete.

   In order for Cylc to be able to restart workflows the
   :cylc:conf:`[scheduler][run hosts]available` hosts must all be on a
   shared filesystem.
Force Mode
   If a host is suffixed with an exclamation mark then Cylc will not attempt
   to automatically restart the workflow and any local jobs (running under
   background or at) will be left running.

For example in the following configuration any workflows running on
``foo`` will attempt to restart on ``pub`` whereas any workflows
running on ``bar`` will stop immediately, making no attempt to restart.

.. code-block:: cylc

   [scheduler]
        [[run hosts]]
            available = pub
            condemned = foo, bar!

.. warning::

   Cylc will reject hosts with ambiguous names such as ``localhost`` or
   ``127.0.0.1`` for this configuration as
   :cylc:conf:`[scheduler][run hosts]condemned`
   are evaluated on the workflow host server.

To prevent large numbers of workflows attempting to restart simultaneously the
:cylc:conf:`[scheduler]auto restart delay` setting defines a period
of time in seconds.
Workflows will wait for a random period of time between zero and
:cylc:conf:`[scheduler]auto restart delay` seconds before
attempting to stop and restart.

Workflows that are started up in no-detach mode cannot auto stop-restart on a
different host - as it will still end up attached to the condemned host.
Therefore, a workflow in no-detach mode running on a condemned host will abort
with a non-zero return code. The parent process should manually handle the
restart of the workflow if desired.

.. cylc-scope::

"""
from random import random
from time import time
import traceback

from cylc.flow import LOG
from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.exceptions import CylcConfigError, HostSelectException
from cylc.flow.host_select import select_workflow_host
from cylc.flow.hostuserutil import get_fqdn_by_host
from cylc.flow.main_loop import periodic
from cylc.flow.parsec.exceptions import ParsecError
from cylc.flow.scheduler import SchedulerError
from cylc.flow.workflow_status import AutoRestartMode
from cylc.flow.wallclock import (
    get_time_string_from_unix_time as time2str
)


@periodic
async def auto_restart(scheduler, _):
    """Automatically restart the workflow if configured to do so."""
    try:
        current_glbl_cfg = glbl_cfg(cached=False)
    except (CylcConfigError, ParsecError) as exc:
        LOG.error(
            'auto restart: an error in the global config is preventing it from'
            f' being reloaded:\n{exc}'
        )
        # skip check - we can't do anything until the global config has been
        # fixed
        return False  # return False to make testing easier
    mode = _should_auto_restart(scheduler, current_glbl_cfg)

    if mode:
        LOG.info('The Cylc workflow host will soon become un-available.')
        _set_auto_restart(
            scheduler,
            restart_delay=current_glbl_cfg.get(
                ['scheduler', 'auto restart delay']
            ),
            mode=mode
        )


def _should_auto_restart(scheduler, current_glbl_cfg):
    # check if workflow host is condemned - if so auto restart
    if scheduler.stop_mode is None:
        for host in current_glbl_cfg.get(
                ['scheduler', 'run hosts', 'condemned']
        ):
            if host.endswith('!'):
                # host ends in an `!` -> force shutdown mode
                mode = AutoRestartMode.FORCE_STOP
                host = host[:-1]
            else:
                # normal mode (stop and restart the workflow)
                mode = AutoRestartMode.RESTART_NORMAL
                if scheduler.auto_restart_time is not None:
                    # workflow is already scheduled to stop-restart only
                    # AutoRestartMode.FORCE_STOP can override this.
                    continue

            if get_fqdn_by_host(host) == scheduler.host:
                # this host is condemned, take the appropriate action

                return mode
    return False


def _can_auto_restart():
    """Determine whether this workflow can safely auto stop-restart."""
    # Check whether there is currently an available host to restart on.
    try:
        select_workflow_host(cached=False)
    except HostSelectException:
        LOG.critical(
            'Workflow cannot automatically restart because:\n' +
            'No alternative host to restart workflow on.')
        return False
    except Exception:
        # Any unexpected error in host selection shouldn't be able to take
        # down the workflow.
        LOG.critical(
            'Workflow cannot automatically restart because:\n' +
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
    """Configure the workflow to automatically stop and restart.

    Restart handled by `workflow_auto_restart`.

    Args:
        scheduler (cylc.flow.scheduler.Scheduler):
            Scheduler instance of the running workflow.
        restart_delay (cylc.flow.parsec.DurationFloat):
            Workflow will wait a random period between 0 and
            `restart_delay` seconds before attempting to stop/restart in
            order to avoid multiple workflows restarting simultaneously.
        mode (str): Auto stop-restart mode.

    Return:
        bool: False if it is not possible to automatically stop/restart
        the workflow due to its configuration/runtime state.
    """
    # Check that the workflow isn't already shutting down.
    if scheduler.stop_mode:
        return True

    # Force mode, stop the workflow now, don't restart it.
    if mode == AutoRestartMode.FORCE_STOP:
        LOG.critical(
            'This workflow will be shutdown as the workflow '
            'host is unable to continue running it.\n'
            'When another workflow host becomes available '
            'the workflow can be restarted by:\n'
            f'    $ cylc play {scheduler.workflow}')
        if scheduler.auto_restart_time:
            LOG.info('Scheduled automatic restart canceled')
        scheduler.auto_restart_time = time()
        scheduler.auto_restart_mode = mode
        return True

    # Check workflow isn't already scheduled to auto-stop.
    if scheduler.auto_restart_time is not None:
        return True

    # Workflow host is condemned and workflow running in no detach mode.
    # Raise an error to cause the workflow to abort.
    # This should raise an "abort" event and return a non-zero code to the
    # caller still attached to the workflow process.
    if scheduler.options.no_detach:
        raise SchedulerError('Workflow host condemned in no detach mode')

    # Check workflow is able to be safely restarted.
    if not _can_auto_restart():
        return False

    LOG.info('Workflow will automatically restart on a new host.')
    if restart_delay is not None and restart_delay != 0:
        if restart_delay > 0:
            # Delay shutdown by a random interval to avoid many
            # workflows restarting simultaneously.
            shutdown_delay = int(random() * restart_delay)  # nosec
        else:
            # Un-documented feature, schedule exact restart interval for
            # testing purposes.
            shutdown_delay = abs(int(restart_delay))
        shutdown_time = time() + shutdown_delay
        LOG.info('Workflow will restart in %ss (at %s)', shutdown_delay,
                 time2str(shutdown_time))
        scheduler.auto_restart_time = shutdown_time
    else:
        scheduler.auto_restart_time = time()

    scheduler.auto_restart_mode = AutoRestartMode.RESTART_NORMAL

    return True
