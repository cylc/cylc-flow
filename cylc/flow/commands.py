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

"""Cylc scheduler commands.

These are the scripts which are actioned on the Scheduler instance when you
call a mutation.

Each is an async generator providing functionalities for:

* Validation:
  * The generator is executed up to the first "yield" before the command is
    queued.
  * Validation and argument parsing can be performed at this stage.
  * If the generator raises an Exception then the error message will be
    communicated back to the user and the command will not be queued.
  * If the execution string is not obvious to a user, catch the exception and
    re-raise it as an InputError with a more obvious string.
  * Any other exceptions will be treated as genuine errors.
* Execution:
  * The generator is executed up to the second "yield" when the command is run
    by the Scheduler's main-loop:
  * The execution may also stop at a return or the end of the generator code.
  * If the generator raises a CommandFailedError at this stage, the error will
    be caught and logged.
  * Any other exceptions will be treated as genuine errors.

In the future we may change this interface to allow generators to "yield" any
arbitrary number of strings to serve the function of communicating command
progress back to the user. For example, the generator might yield the messages:

* Command queued.
* Done 1/3 things
* Done 2/3 things
* Done 3/3 things
* Done

For more info see: https://github.com/cylc/cylc-flow/issues/3329

"""

from contextlib import suppress
from time import sleep, time
from typing import (
    AsyncGenerator,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    TYPE_CHECKING,
    Union,
)

from cylc.flow import LOG
import cylc.flow.command_validation as validate
from cylc.flow.exceptions import (
    CommandFailedError,
    CyclingError,
    CylcConfigError,
)
import cylc.flow.flags
from cylc.flow.log_level import log_level_to_verbosity
from cylc.flow.network.schema import WorkflowStopMode
from cylc.flow.parsec.exceptions import ParsecError
from cylc.flow.task_id import TaskID
from cylc.flow.task_state import TASK_STATUSES_ACTIVE, TASK_STATUS_FAILED
from cylc.flow.workflow_status import RunMode, StopMode

from metomi.isodatetime.parsers import TimePointParser

if TYPE_CHECKING:
    from cylc.flow.scheduler import Scheduler

    # define a type for command implementations
    Command = Callable[
        ...,
        AsyncGenerator,
    ]

# a directory of registered commands (populated on module import)
COMMANDS: 'Dict[str, Command]' = {}


def _command(name: str):
    """Decorator to register a command."""
    def _command(fcn: 'Command'):
        nonlocal name
        COMMANDS[name] = fcn
        fcn.command_name = name  # type: ignore
        return fcn
    return _command


async def run_cmd(fcn, *args, **kwargs):
    """Run a command outside of the scheduler's main loop.

    Normally commands are run via the Scheduler's command_queue (which is
    correct), however, there are some use cases for running commands outside of
    the loop:

    * Running synchronous commands within the scheduler itself (e.g. on
      shutdown).
    * Integration tests (where you may want to cut out the main loop and
      command queueing mechanism for simplicity).

    For these purposes use "run_cmd", otherwise, queue commands via the
    scheduler as normal.
    """
    cmd = fcn(*args, **kwargs)
    await cmd.__anext__()  # validate
    with suppress(StopAsyncIteration):
        return await cmd.__anext__()  # run


@_command('set')
async def set_prereqs_and_outputs(
    schd: 'Scheduler',
    tasks: List[str],
    flow: List[str],
    outputs: Optional[List[str]] = None,
    prerequisites: Optional[List[str]] = None,
    flow_wait: bool = False,
    flow_descr: Optional[str] = None,
) -> AsyncGenerator:
    """Force spawn task successors.

    Note, the "outputs" and "prerequisites" arguments might not be
    populated in the mutation arguments so must provide defaults here.
    """
    validate.consistency(outputs, prerequisites)
    outputs = validate.outputs(outputs)
    prerequisites = validate.prereqs(prerequisites)
    validate.flow_opts(flow, flow_wait)
    validate.is_tasks(tasks)

    yield

    if outputs is None:
        outputs = []
    if prerequisites is None:
        prerequisites = []
    yield schd.pool.set_prereqs_and_outputs(
        tasks,
        outputs,
        prerequisites,
        flow,
        flow_wait,
        flow_descr,
    )


@_command('stop')
async def stop(
    schd: 'Scheduler',
    mode: Union[str, 'StopMode'],
    cycle_point: Optional[str] = None,
    # NOTE clock_time YYYY/MM/DD-HH:mm back-compat removed
    clock_time: Optional[str] = None,
    task: Optional[str] = None,
    flow_num: Optional[int] = None,
):
    if task:
        validate.is_tasks([task])
    yield
    if flow_num:
        schd.pool.stop_flow(flow_num)
        return

    if cycle_point is not None:
        # schedule shutdown after tasks pass provided cycle point
        point = TaskID.get_standardised_point(cycle_point)
        if point is not None and schd.pool.set_stop_point(point):
            schd.options.stopcp = str(point)
            schd.config.stop_point = point
            schd.workflow_db_mgr.put_workflow_stop_cycle_point(
                schd.options.stopcp
            )
        schd._update_workflow_state()
    elif clock_time is not None:
        # schedule shutdown after wallclock time passes provided time
        parser = TimePointParser()
        schd.set_stop_clock(
            int(parser.parse(clock_time).seconds_since_unix_epoch)
        )
        schd._update_workflow_state()
    elif task is not None:
        # schedule shutdown after task succeeds
        task_id = TaskID.get_standardised_taskid(task)
        schd.pool.set_stop_task(task_id)
        schd._update_workflow_state()
    else:
        # immediate shutdown
        with suppress(KeyError):
            # By default, mode from mutation is a name from the
            # WorkflowStopMode graphene.Enum, but we need the value
            mode = WorkflowStopMode[mode]  # type: ignore[misc]
        try:
            mode = StopMode(mode)
        except ValueError:
            raise CommandFailedError(f"Invalid stop mode: '{mode}'")
        schd._set_stop(mode)
        if mode is StopMode.REQUEST_KILL:
            schd.time_next_kill = time()


@_command('release')
async def release(schd: 'Scheduler', tasks: Iterable[str]):
    """Release held tasks."""
    validate.is_tasks(tasks)
    yield
    yield schd.pool.release_held_tasks(tasks)


@_command('release_hold_point')
async def release_hold_point(schd: 'Scheduler'):
    """Release all held tasks and unset workflow hold after cycle point,
    if set."""
    yield
    LOG.info("Releasing all tasks and removing hold cycle point.")
    schd.pool.release_hold_point()
    schd._update_workflow_state()


@_command('resume')
async def resume(schd: 'Scheduler'):
    """Resume paused workflow."""
    yield
    schd.resume_workflow()


@_command('poll_tasks')
async def poll_tasks(schd: 'Scheduler', tasks: Iterable[str]):
    """Poll pollable tasks or a task or family if options are provided."""
    validate.is_tasks(tasks)
    yield
    if schd.get_run_mode() == RunMode.SIMULATION:
        yield 0
    itasks, _, bad_items = schd.pool.filter_task_proxies(tasks)
    schd.task_job_mgr.poll_task_jobs(schd.workflow, itasks)
    yield len(bad_items)


@_command('kill_tasks')
async def kill_tasks(schd: 'Scheduler', tasks: Iterable[str]):
    """Kill all tasks or a task/family if options are provided."""
    validate.is_tasks(tasks)
    yield
    itasks, _, bad_items = schd.pool.filter_task_proxies(tasks)
    if schd.get_run_mode() == RunMode.SIMULATION:
        for itask in itasks:
            if itask.state(*TASK_STATUSES_ACTIVE):
                itask.state_reset(TASK_STATUS_FAILED)
                schd.data_store_mgr.delta_task_state(itask)
        yield len(bad_items)
    else:
        schd.task_job_mgr.kill_task_jobs(schd.workflow, itasks)
        yield len(bad_items)


@_command('hold')
async def hold(schd: 'Scheduler', tasks: Iterable[str]):
    """Hold specified tasks."""
    validate.is_tasks(tasks)
    yield
    yield schd.pool.hold_tasks(tasks)


@_command('set_hold_point')
async def set_hold_point(schd: 'Scheduler', point: str):
    """Hold all tasks after the specified cycle point."""
    yield
    cycle_point = TaskID.get_standardised_point(point)
    if cycle_point is None:
        raise CyclingError("Cannot set hold point to None")
    LOG.info(
        f"Setting hold cycle point: {cycle_point}\n"
        "All tasks after this point will be held."
    )
    schd.pool.set_hold_point(cycle_point)
    schd._update_workflow_state()


@_command('pause')
async def pause(schd: 'Scheduler'):
    """Pause the workflow."""
    yield
    schd.pause_workflow()


@_command('set_verbosity')
async def set_verbosity(schd: 'Scheduler', level: Union[int, str]):
    """Set workflow verbosity."""
    yield
    try:
        lvl = int(level)
        LOG.setLevel(lvl)
    except (TypeError, ValueError) as exc:
        raise CommandFailedError(exc)
    cylc.flow.flags.verbosity = log_level_to_verbosity(lvl)


@_command('remove_tasks')
async def remove_tasks(schd: 'Scheduler', tasks: Iterable[str]):
    """Remove tasks."""
    validate.is_tasks(tasks)
    yield
    yield schd.pool.remove_tasks(tasks)


@_command('reload_workflow')
async def reload_workflow(schd: 'Scheduler'):
    """Reload workflow configuration."""
    yield
    # pause the workflow if not already
    was_paused_before_reload = schd.is_paused
    if not was_paused_before_reload:
        schd.pause_workflow('Reloading workflow')
        schd.process_workflow_db_queue()  # see #5593

    # flush out preparing tasks before attempting reload
    schd.reload_pending = 'waiting for pending tasks to submit'
    while schd.release_queued_tasks():
        # Run the subset of main-loop functionality required to push
        # preparing through the submission pipeline and keep the workflow
        # responsive (e.g. to the `cylc stop` command).

        # NOTE: this reload method was called by process_command_queue
        # which is called synchronously in the main loop so this call is
        # blocking to other main loop functions

        # subproc pool - for issueing/tracking remote-init commands
        schd.proc_pool.process()
        # task messages - for tracking task status changes
        schd.process_queued_task_messages()
        # command queue - keeps the scheduler responsive
        await schd.process_command_queue()
        # allows the scheduler to shutdown --now
        await schd.workflow_shutdown()
        # keep the data store up to date with what's going on
        await schd.update_data_structure()
        schd.update_data_store()
        # give commands time to complete
        sleep(1)  # give any remove-init's time to complete

    # reload the workflow definition
    schd.reload_pending = 'loading the workflow definition'
    schd.update_data_store()  # update workflow status msg
    schd._update_workflow_state()
    LOG.info("Reloading the workflow definition.")
    try:
        config = schd.load_flow_file(is_reload=True)
    except (ParsecError, CylcConfigError) as exc:
        if cylc.flow.flags.verbosity > 1:
            # log full traceback in debug mode
            LOG.exception(exc)
        LOG.critical(
            f'Reload failed - {exc.__class__.__name__}: {exc}'
            '\nThis is probably due to an issue with the new'
            ' configuration.'
            '\nTo continue with the pre-reload config, un-pause the'
            ' workflow.'
            '\nOtherwise, fix the configuration and attempt to reload'
            ' again.'
        )
    else:
        schd.reload_pending = 'applying the new config'
        old_tasks = set(schd.config.get_task_name_list())
        # Things that can't change on workflow reload:
        schd._set_workflow_params(
            schd.workflow_db_mgr.pri_dao.select_workflow_params()
        )
        schd.apply_new_config(config, is_reload=True)
        schd.broadcast_mgr.linearized_ancestors = (
            schd.config.get_linearized_ancestors()
        )

        schd.task_events_mgr.mail_interval = schd.cylc_config['mail'][
            'task event batch interval'
        ]
        schd.task_events_mgr.mail_smtp = schd._get_events_conf("smtp")
        schd.task_events_mgr.mail_footer = schd._get_events_conf("footer")

        # Log tasks that have been added by the reload, removed tasks are
        # logged by the TaskPool.
        add = set(schd.config.get_task_name_list()) - old_tasks
        for task in add:
            LOG.warning(f"Added task: '{task}'")
        schd.workflow_db_mgr.put_workflow_template_vars(schd.template_vars)
        schd.workflow_db_mgr.put_runtime_inheritance(schd.config)
        schd.workflow_db_mgr.put_workflow_params(schd)
        schd.process_workflow_db_queue()  # see #5593
        schd.is_updated = True
        schd.is_reloaded = True
        schd._update_workflow_state()

        # Re-initialise data model on reload
        schd.data_store_mgr.initiate_data_model(schd.is_reloaded)

        # Reset the remote init map to trigger fresh file installation
        schd.task_job_mgr.task_remote_mgr.remote_init_map.clear()
        schd.task_job_mgr.task_remote_mgr.is_reload = True
        schd.pool.reload_taskdefs(config)
        # Load jobs from DB
        schd.workflow_db_mgr.pri_dao.select_jobs_for_restart(
            schd.data_store_mgr.insert_db_job
        )
        if schd.pool.compute_runahead(force=True):
            schd.pool.release_runahead_tasks()
        schd.is_reloaded = True
        schd.is_updated = True

        LOG.info("Reload completed.")

    # resume the workflow if previously paused
    schd.reload_pending = False
    schd.update_data_store()  # update workflow status msg
    schd._update_workflow_state()
    if not was_paused_before_reload:
        schd.resume_workflow()
        schd.process_workflow_db_queue()  # see #5593


@_command('force_trigger_tasks')
async def force_trigger_tasks(
    schd: 'Scheduler',
    tasks: Iterable[str],
    flow: List[str],
    flow_wait: bool = False,
    flow_descr: Optional[str] = None,
):
    """Manual task trigger."""
    validate.is_tasks(tasks)
    yield
    yield schd.pool.force_trigger_tasks(tasks, flow, flow_wait, flow_descr)
