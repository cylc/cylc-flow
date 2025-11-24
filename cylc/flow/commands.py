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
import itertools
from time import (
    sleep,
    time,
)
from typing import (
    TYPE_CHECKING,
    AsyncGenerator,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Set,
    TypeVar,
)

from metomi.isodatetime.parsers import TimePointParser

from cylc.flow import LOG
from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
import cylc.flow.command_validation as validate
from cylc.flow.cycling.loader import get_point
from cylc.flow.exceptions import (
    CommandFailedError,
    CyclingError,
    CylcConfigError,
)
import cylc.flow.flags
from cylc.flow.flow_mgr import FLOW_NONE, repr_flow_nums
from cylc.flow.id import TaskTokens
from cylc.flow.log_level import log_level_to_verbosity
from cylc.flow.parsec.exceptions import ParsecError
from cylc.flow.prerequisite import PrereqTuple
from cylc.flow.run_modes import RunMode
from cylc.flow.task_id import TaskID
from cylc.flow.task_state import (
    TASK_STATUS_PREPARING,
    TASK_STATUSES_ACTIVE,
)
from cylc.flow.taskdef import generate_graph_children
from cylc.flow.util import get_connected_groups
from cylc.flow.workflow_status import StopMode


if TYPE_CHECKING:
    from enum import Enum

    from cylc.flow.flow_mgr import FlowNums
    from cylc.flow.scheduler import Scheduler
    from cylc.flow.task_proxy import TaskProxy

    # define a type for command implementations
    Command = Callable[..., AsyncGenerator]
    # define a generic type needed for the @_command decorator
    _TCommand = TypeVar('_TCommand', bound=Command)

# a directory of registered commands (populated on module import)
COMMANDS: 'Dict[str, Command]' = {}


# BACK COMPAT: handle --flow=all from pre-8.5 clients.
def back_compat_flow_all(flow: List[str]) -> List[str]:
    """From 8.5 the old --flow=all is just the default.

    Examples:
        >>> back_compat_flow_all(['1', '2', '3'])
        ['1', '2', '3']

        >>> back_compat_flow_all(["all"])
        []

    """
    if flow == ["all"]:
        return []
    else:
        return flow


def _command(name: str):
    """Decorator to register a command."""
    def _command(fcn: '_TCommand') -> '_TCommand':
        COMMANDS[name] = fcn
        fcn.command_name = name  # type: ignore[attr-defined]
        return fcn
    return _command


def _report_unmatched(unmatched: Set[TaskTokens]):
    """Log unmatched IDs."""
    if len(unmatched) == 1:
        LOG.warning(
            'No tasks match'
            f' "{next(iter(unmatched)).relative_id_with_selectors}"'
        )
    elif len(unmatched) > 1:
        LOG.warning(
            'No tasks match the IDs:\n* '
            + '\n* '.join(
                sorted([id_.relative_id_with_selectors for id_ in unmatched])
            )
        )


def _remove_matched_tasks(
    schd: 'Scheduler',
    ids: Set[TaskTokens],
    flow_nums: 'FlowNums',
):
    """Remove matched tasks."""
    # Mapping of *relative* task IDs to removed flow numbers:
    removed: Dict[TaskTokens, FlowNums] = {}
    not_removed: Set[TaskTokens] = set()
    to_kill: List[TaskProxy] = []

    for id_ in ids:
        itask = schd.pool._get_task_by_id(id_.relative_id)

        if itask:
            # remove active task from the pool
            fnums_to_remove = itask.match_flows(flow_nums)
            if not fnums_to_remove:
                not_removed.add(itask.tokens.task)
                continue
            removed[itask.tokens.task] = fnums_to_remove
            if fnums_to_remove == itask.flow_nums:
                # Need to remove the task from the pool.
                # Spawn next occurrence of xtrigger sequential task (otherwise
                # this would not happen after removing this occurrence):
                schd.pool.check_spawn_psx_task(itask)
                schd.pool.remove(itask, 'request')
                to_kill.append(itask)
                itask.removed = True
            itask.flow_nums.difference_update(fnums_to_remove)

        # remove task from the DB
        tdef = schd.config.taskdefs[id_['task']]
        icycle = get_point(id_['cycle'])

        # Go through any tasks downstream of this matched task to see if
        # any need to stand down as a result of this task being removed:
        for child in set(itertools.chain.from_iterable(
            generate_graph_children(tdef, icycle).values()
        )):
            child_itask = schd.pool.get_task(child.point, child.name)
            if not child_itask:
                continue
            fnums_to_remove = child_itask.match_flows(flow_nums)
            if not fnums_to_remove:
                continue
            prereqs_changed = False
            for prereq in (
                *child_itask.state.prerequisites,
                *child_itask.state.suicide_prerequisites,
            ):
                # Unset any prereqs naturally satisfied by these tasks
                # (do not unset those satisfied by `cylc set --pre`):
                if prereq.unset_naturally_satisfied(id_.relative_id):
                    prereqs_changed = True
                    removed.setdefault(id_, set()).update(
                        fnums_to_remove
                    )
            if not prereqs_changed:
                continue
            schd.data_store_mgr.delta_task_prerequisite(child_itask)
            # Check if downstream task is still ready to run:
            if (
                child_itask.state.is_gte(TASK_STATUS_PREPARING)
                # Still ready if the task exists in other flows:
                or child_itask.flow_nums != fnums_to_remove
                or child_itask.state.prerequisites_all_satisfied()
            ):
                continue
            # No longer ready to run
            schd.pool.unqueue_task(child_itask)
            # Check if downstream task should remain spawned:
            if (
                # Ignoring tasks we are already dealing with:
                child_itask.tokens.task in ids
                or child_itask.state.any_satisfied_prerequisite_outputs()
            ):
                continue
            # No longer has reason to be in pool:
            schd.pool.remove(child_itask, schd.pool.REMOVED_BY_PREREQ)
            # Remove this downstream task from flows in DB tables to ensure
            # it is not skipped if it respawns in future:
            schd.workflow_db_mgr.remove_task_from_flows(
                str(child.point), child.name, fnums_to_remove
            )

        # Remove the matched tasks from the flows in the DB tables:
        db_removed_fnums = schd.workflow_db_mgr.remove_task_from_flows(
            id_['cycle'], id_['task'], flow_nums,
        )
        if db_removed_fnums:
            removed.setdefault(id_, set()).update(db_removed_fnums)

        if id_ not in removed:
            not_removed.add(id_)

    if to_kill:
        schd.kill_tasks(to_kill, warn=False)

    if removed:
        tasks_str_list = []
        for task, fnums in removed.items():
            schd.data_store_mgr.delta_remove_task_flow_nums(
                task.relative_id, fnums
            )
            tasks_str_list.append(
                f"{task.relative_id} {repr_flow_nums(fnums, full=True)}"
            )
        LOG.info(f"Removed tasks: {', '.join(sorted(tasks_str_list))}")

    if not_removed:
        fnums_str = (
            repr_flow_nums(flow_nums, full=True) if flow_nums else ''
        )
        tasks_str = ', '.join(
            sorted(tokens.relative_id for tokens in not_removed)
        )
        # This often does not indicate an error - e.g. for group trigger.
        LOG.debug(f"Task(s) not removable: {tasks_str} {fnums_str}")

    if removed and schd.pool.compute_runahead():
        schd.pool.release_runahead_tasks()


async def run_cmd(bound_fcn: AsyncGenerator):
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
    await bound_fcn.__anext__()  # validate
    with suppress(StopAsyncIteration):
        return await bound_fcn.__anext__()  # run


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
    flow = back_compat_flow_all(flow)  # BACK COMPAT (see func def)
    validate.consistency(outputs, prerequisites)
    outputs = validate.outputs(outputs)
    prerequisites = validate.prereqs(prerequisites)
    validate.flow_opts(flow, flow_wait)
    ids = validate.is_tasks(tasks)

    yield

    if outputs is None:
        outputs = []
    if prerequisites is None:
        prerequisites = []
    yield schd.pool.set_prereqs_and_outputs(
        ids,
        outputs,
        prerequisites,
        flow,
        flow_wait,
        flow_descr,
    )


@_command('stop')
async def stop(
    schd: 'Scheduler',
    mode: 'Optional[Enum]',
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
        try:
            # BACK COMPAT: mode=None
            #     the mode can be `None` for commands issued from older Cylc
            #     versions
            # From: 8.4
            # To: 8.5
            # Remove at: 8.x
            mode = StopMode(mode.value) if mode else StopMode.REQUEST_CLEAN
        except ValueError:
            raise CommandFailedError(f"Invalid stop mode: '{mode}'") from None
        schd._set_stop(mode)
        if mode is StopMode.REQUEST_KILL:
            schd.time_next_kill = time()


@_command('release')
async def release(schd: 'Scheduler', tasks: Iterable[str]):
    """Release held tasks."""
    ids = validate.is_tasks(tasks)
    yield
    yield schd.pool.release_held_tasks(ids)


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
    ids = validate.is_tasks(tasks)
    yield
    if schd.get_run_mode() == RunMode.SIMULATION:
        yield 0
    matched, unmatched = schd.pool.id_match(ids, only_match_pool=True)
    _report_unmatched(unmatched)
    itasks = schd.pool.get_itasks(matched)
    schd.task_job_mgr.poll_task_jobs(itasks)
    yield len(unmatched)


@_command('kill_tasks')
async def kill_tasks(schd: 'Scheduler', tasks: Iterable[str]):
    """Kill tasks.

    Args:
        tasks: Tasks/families/globs to kill.
    """
    ids = validate.is_tasks(tasks)
    yield
    matched, unmatched = schd.pool.id_match(ids, only_match_pool=True)
    _report_unmatched(unmatched)
    itasks = schd.pool.get_itasks(matched)
    num_unkillable = schd.kill_tasks(itasks)
    yield len(unmatched) + num_unkillable


@_command('hold')
async def hold(schd: 'Scheduler', tasks: Iterable[str]):
    """Hold specified tasks."""
    ids = validate.is_tasks(tasks)
    yield
    yield schd.pool.hold_tasks(ids)


@_command('set_hold_point')
async def set_hold_point(schd: 'Scheduler', point: str):
    """Hold all tasks after the specified cycle point."""
    cycle_point = TaskID.get_standardised_point(point)
    if cycle_point is None:
        raise CyclingError("Cannot set hold point to None")
    yield
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
async def set_verbosity(schd: 'Scheduler', level: 'Enum'):
    """Set workflow verbosity."""
    try:
        LOG.setLevel(level.value)
    except (TypeError, ValueError) as exc:
        raise CommandFailedError(exc) from None
    cylc.flow.flags.verbosity = log_level_to_verbosity(level.value)
    yield


@_command('remove_tasks')
async def remove_tasks(
    schd: 'Scheduler', tasks: Iterable[str], flow: List[str]
):
    """Match and remove tasks (`cylc remove` command).

    Args:
        tasks: Relative IDs or globs to match.
        flow: flows to remove the tasks from.
    """
    flow = back_compat_flow_all(flow)  # BACK COMPAT (see func def)
    ids = validate.is_tasks(tasks)
    validate.flow_opts(flow, flow_wait=False, allow_new_or_none=False)
    yield

    matched, unmatched = schd.pool.id_match(ids)
    _report_unmatched(unmatched)
    if matched:
        _remove_matched_tasks(
            schd,
            matched,
            schd.pool.flow_mgr.cli_to_flow_nums(flow)
        )


@_command('reload_workflow')
async def reload_workflow(schd: 'Scheduler', reload_global: bool = False):
    """Reload workflow configuration."""
    yield
    # pause the workflow if not already
    was_paused_before_reload = schd.is_paused
    if not was_paused_before_reload:
        schd.pause_workflow('Reloading workflow')
        schd.process_workflow_db_queue()  # see #5593

    # flush out preparing tasks before attempting reload
    schd.reload_pending = 'waiting for pending tasks to submit'
    while schd.release_tasks_to_run():
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

    try:
        # Back up the current config in case workflow reload errors
        global_cfg_old = glbl_cfg()

        if reload_global:
            # Reload global config if requested
            schd.reload_pending = 'reloading the global configuration'
            schd.update_data_store()  # update workflow status msg
            await schd.update_data_structure()
            LOG.info("Reloading the global configuration.")

            glbl_cfg(reload=True)

        # reload the workflow definition
        schd.reload_pending = 'loading the workflow definition'
        schd.update_data_store()  # update workflow status msg
        schd._update_workflow_state()
        # Things that can't change on workflow reload:
        schd._set_workflow_params(
            schd.workflow_db_mgr.pri_dao.select_workflow_params()
        )
        LOG.info("Reloading the workflow definition.")
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

        # Rollback global config
        glbl_cfg().set_cache(global_cfg_old)
    else:
        schd.reload_pending = 'applying the new config'
        old_tasks = set(schd.config.get_task_name_list())

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
            LOG.info(f"Added task: '{task}'")
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
        schd.pool.reload(config)
        schd.data_store_mgr.apply_task_proxy_db_history()
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
    # BACK COMPAT: on_resume
    #   Arg no longer used but retained for older clients.
    # From: 8.6
    # Remove at: 8.7
    on_resume: bool = False
):
    """Match and trigger a group of tasks (`cylc trigger` command).

    Satisfy any off-group prerequisites. Group start tasks (parentless,
    or only off-group prerequisites) will run immediately. In-group
    prerequisites will be respected.

    Implements the Group Trigger Proposal:
      cylc-admin/docs/proposal-group-trigger.md

    """
    flow = back_compat_flow_all(flow)  # BACK COMPAT (see func def)
    ids = validate.is_tasks(tasks)
    validate.flow_opts(flow, flow_wait)
    yield

    matched, unmatched = schd.pool.id_match(ids)
    _report_unmatched(unmatched)

    # split IDs into connected groups of tasks
    adjacency: Dict[TaskTokens, Set[TaskTokens]] = {}
    for id_ in matched:
        id_ = id_.duplicate(task_sel=None)  # strip the task selector
        icycle = get_point(id_['cycle'])
        prereqs = {
            prereq_id
            for prereq_id in (
                TaskTokens(str(trg.get_point(icycle)), trg.task_name)
                for trg in schd.config.taskdefs[id_['task']].get_triggers(
                    icycle
                )
            )
            if prereq_id in matched
        }
        adjacency.setdefault((id_), set()).update(prereqs)
        for prereq in prereqs:
            adjacency.setdefault(prereq, set()).add(id_)

    # trigger each group of tasks individually
    for group in get_connected_groups(adjacency):
        _force_trigger_tasks(
            schd,
            group,
            flow,
            flow_wait,
            flow_descr,
        )


def _force_trigger_tasks(
    schd: 'Scheduler',
    group_ids: Set[TaskTokens],
    flow: List[str],
    flow_wait: bool = False,
    flow_descr: Optional[str] = None,
):
    active = schd.pool.get_itasks(group_ids)
    if flow or not active:
        flow_nums = schd.pool.flow_mgr.cli_to_flow_nums(flow, flow_descr)
        if flow != [FLOW_NONE] and not flow_nums:
            # Here, empty flow_nums means either no-flow or all active flows.
            flow_nums = schd.pool._get_active_flow_nums()

    else:
        flow_nums = set()
        for itask in active:
            flow_nums.update(itask.flow_nums)

    # Record off-group prerequisites, and active tasks to be removed.
    active_to_remove: List[TaskTokens] = []
    active_to_resume: Set[TaskTokens] = set()

    warnings_flow_none = []
    warnings_has_job = []
    active_completed_outputs = {}
    inactive: Set[TaskTokens] = set(group_ids)
    for itask in active:
        # Find active group start tasks (parentless, or with only off-group
        # prerequisites) and set all prerequisites (to trigger them now).

        # Preparing, submitted, or running group start tasks are already
        # active, so leave them be (and merge the flows).

        # Compute prerequisites from the TaskDef in case active tasks were
        # spawned before a reload (which could alter prerequisites).

        # Remove non group start and final-status group start tasks, and
        # trigger them from scratch (so only the TaskDef matters).

        # Group start tasks are not removed, but a reload would
        # replace them, so using the TaskDef is fine.
        inactive.remove(itask.tokens.task)

        if not any(
            TaskTokens(str(trg.get_point(itask.point)), trg.task_name)
            in group_ids
            for trg in itask.tdef.get_triggers(itask.point)
        ):
            # This is a group start task (it has no in-group prerequisites).
            if flow == [FLOW_NONE] and itask.flow_nums:
                # Exclude --flow=none for flow-assigned active tasks.
                warnings_flow_none.append(
                    f"{itask.identity}: "
                    f"{repr_flow_nums(itask.flow_nums, full=True)}"
                )
                continue

            if itask.state(*TASK_STATUSES_ACTIVE):
                for (label, msg, completed) in itask.state.outputs:
                    if completed:
                        active_completed_outputs[
                            (str(itask.point), itask.tdef.name)] = (label, msg)

            if itask.state(TASK_STATUS_PREPARING, *TASK_STATUSES_ACTIVE):
                # This is a live active group start task
                warnings_has_job.append(str(itask))
                # Just merge the flows.
                schd.pool.merge_flows(itask, flow_nums)

            else:
                # This is a non-live active group start task...
                # ... satisfy off-group (i.e. all) prerequisites
                itask.state.set_all_task_prerequisites_satisfied()
                # ... and satisfy all xtrigger prerequisites.
                schd.pool.xtrigger_mgr.force_satisfy(itask, {"all": True})
                # ... and satisfy all push external triggers.
                itask.force_satisfy_external_triggers()

                schd.pool.merge_flows(itask, flow_nums)

                # Trigger group start task.
                schd.pool.queue_or_trigger(itask)

        else:
            active_to_remove.append(itask.tokens.task)
            active_to_resume.add(itask.tokens.task)

    if warnings_flow_none:
        msg = '\n  * '.join(warnings_flow_none)
        LOG.warning(f"Already active - ignoring no-flow trigger: \n  * {msg}")

    if warnings_has_job:
        msg = '\n  * '.join(warnings_has_job)
        LOG.warning(f"Job already in process - ignoring trigger:\n  * {msg}")

    # Remove all inactive and selected active group members.
    if flow != [FLOW_NONE]:
        # (No need to remove tasks if triggering with no-flow).
        _remove_matched_tasks(schd, {*active_to_remove, *inactive}, flow_nums)

        # trigger should override the held state, however, in-group tasks may
        # have previously been held and active in-group tasks will become
        # held as the result of removal
        schd.pool.release_held_tasks({*active_to_resume, *inactive})

        # Store removal results before moving on.
        schd.workflow_db_mgr.process_queued_ops()

    # Satisfy any off-group prerequisites in removed tasks.
    tasks_removed = inactive
    if active_to_remove:
        tasks_removed.update(active_to_remove)

    # for tdef, point in tasks_removed:
    for id_ in tasks_removed:
        tdef = schd.config.taskdefs[id_['task']]
        icycle = get_point(id_['cycle'])
        in_flow_prereqs = False
        jtask: Optional[TaskProxy] = None
        if tdef.is_parentless(icycle):
            # Parentless: set all prereqs to spawn the task.
            jtask = schd.pool._set_prereqs_tdef(
                icycle, tdef,
                [],  # prerequisites
                {"all": True},  # xtriggers
                flow_nums,
                flow_wait,
                set_all=True  # prerequisites
            )
        else:
            _prereqs = tdef.get_prereqs(icycle)
            # Off-flow prereqs to satisfy, for the triggered flow:
            prereqs_to_set = {
                PrereqTuple(str(key.point), str(key.task), key.output)
                for pre in _prereqs
                for key in pre.keys()
                if TaskTokens(cycle=key.point, task=key.task) not in group_ids
            }
            in_flow_prereqs = any(
                key
                for pre in _prereqs
                for key in pre.keys()
                if TaskTokens(cycle=key.point, task=key.task) in group_ids
            )
            # Prereqs to satisfy, from already-completed outputs of active
            # group start tasks, for the triggered flow.
            prereqs_to_set.update({
                PrereqTuple(str(key.point), str(key.task), key.output)
                for pre in _prereqs
                for key in pre.keys()
                if (str(key.point), key.task) in active_completed_outputs
            })

            if (
                prereqs_to_set
                or tdef.get_xtrigs(icycle)
                or tdef.external_triggers
            ):
                # Satisfy any off-group prereqs or ext/xtriggers to spawn task.
                jtask = schd.pool._set_prereqs_tdef(
                    icycle, tdef,
                    prereqs_to_set,
                    {"all": True},  # xtriggers
                    flow_nums,
                    flow_wait,
                    set_all=False
                )
                if jtask is not None and tdef.external_triggers:
                    jtask.force_satisfy_external_triggers()

        if jtask is not None and not in_flow_prereqs:
            # Trigger group start task.
            schd.pool.queue_or_trigger(jtask)

    schd.pool.release_runahead_tasks()
