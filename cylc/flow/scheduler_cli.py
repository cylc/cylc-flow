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
"""Common logic for "cylc play" CLI."""

from ansimarkup import parse as cparse
import asyncio
from copy import deepcopy
from functools import lru_cache
from itertools import zip_longest
from pathlib import Path
from shlex import quote
import sys
from typing import TYPE_CHECKING, Tuple

from packaging.version import Version

from cylc.flow import LOG, __version__
from cylc.flow.exceptions import (
    ContactFileExists,
    CylcError,
    ServiceFileError,
)
import cylc.flow.flags
from cylc.flow.id import upgrade_legacy_ids
from cylc.flow.host_select import select_workflow_host
from cylc.flow.hostuserutil import is_remote_host
from cylc.flow.id_cli import parse_ids_async
from cylc.flow.loggingutil import (
    close_log,
    RotatingLogFileHandler,
)
from cylc.flow.network.client import WorkflowRuntimeClient
from cylc.flow.option_parsers import (
    WORKFLOW_ID_ARG_DOC,
    CylcOptionParser as COP,
    OptionSettings,
    Options,
    ICP_OPTION,
)
from cylc.flow.pathutil import get_workflow_run_scheduler_log_path
from cylc.flow.remote import cylc_server_cmd
from cylc.flow.scheduler import Scheduler, SchedulerError
from cylc.flow.scripts.common import cylc_header
from cylc.flow.run_modes import WORKFLOW_RUN_MODES
from cylc.flow.workflow_db_mgr import WorkflowDatabaseManager
from cylc.flow.workflow_files import (
    SUITERC_DEPR_MSG,
    detect_old_contact_file,
    get_workflow_srv_dir,
)
from cylc.flow.terminal import (
    cli_function,
    is_terminal,
    prompt,
)

if TYPE_CHECKING:
    from optparse import Values


PLAY_DOC = r"""cylc play [OPTIONS] ARGS

Start, resume, or restart a workflow.

The scheduler will run as a daemon unless you specify --no-detach.

To avoid overwriting existing run directories, workflows that already ran can
only be restarted from prior state. To start again, "cylc install" a new copy
or "cylc clean" the existing run directory.

By default, new runs begin at the start of the graph, determined by the initial
cycle point. You can also begin at a later cycle point (--start-cycle-point),
or at specified tasks (--start-task) within the graph.

For convenience, any dependence on tasks prior to the start cycle point (or to
the cycle point of the earliest task specified by --start-task) will be taken
as satisfied.

Examples:
    # Start (at the initial cycle point), restart, or resume workflow WORKFLOW
    $ cylc play WORKFLOW

    # Start a new run from a cycle point after the initial cycle point
    # (integer cycling)
    $ cylc play --start-cycle-point=3 WORKFLOW
    # (datetime cycling):
    $ cylc play --start-cycle-point=20250101T0000Z WORKFLOW

    # Start a new run from specified tasks in the graph
    $ cylc play --start-task=3/foo WORKFLOW
    $ cylc play -t 3/foo -t 3/bar WORKFLOW

    # Start, restart or resume the second installed run of the workflow
    # "dogs/fido"
    $ cylc play dogs/fido/run2

At restart, tasks recorded as submitted or running are polled to determine what
happened to them while the workflow was down.
"""


RESUME_MUTATION = '''
mutation (
  $wFlows: [WorkflowID]!
) {
  resume (
    workflows: $wFlows
  ) {
    result
  }
}
'''

PLAY_ICP_OPTION = deepcopy(ICP_OPTION)
PLAY_ICP_OPTION.sources = {'play'}

RUN_MODE = OptionSettings(
    ["-m", "--mode"],
    help=(
        f"Run mode: {sorted(WORKFLOW_RUN_MODES)} (default live)."
        " Live mode executes the tasks as defined in the runtime"
        " section."
        " Simulation and dummy modes ignore part of tasks'"
        " runtime configurations. Simulation and dummy modes are"
        " designed for testing."
    ),
    metavar="STRING", action='store', dest="run_mode",
    choices=list(WORKFLOW_RUN_MODES),
)

PLAY_RUN_MODE = deepcopy(RUN_MODE)
PLAY_RUN_MODE.sources = {'play'}

PLAY_OPTIONS = [
    OptionSettings(
        ["-N", "--no-detach", "--non-daemon"],
        help="Do not daemonize the scheduler (infers --format=plain)",
        action='store_true', dest="no_detach", sources={'play'}),
    OptionSettings(
        ["--profile"],
        help="Output profiling (performance) information",
        action='store_true',
        default=False,
        dest="profile_mode",
        sources={'play'},
    ),
    OptionSettings(
        ["--start-cycle-point", "--startcp"],
        help=(
            "Set the start cycle point, which may be after"
            " the initial cycle point. If the specified start point is"
            " not in the sequence, the next on-sequence point will"
            " be used. (Not to be confused with the initial cycle point)"),
        metavar="CYCLE_POINT",
        action='store',
        dest="startcp",
        sources={'play'},
    ),
    OptionSettings(
        ["--final-cycle-point", "--fcp"],
        help=(
            "Set the final cycle point. This command line option overrides"
            " the workflow config option"
            " '[scheduling]final cycle point'. "),
        metavar="CYCLE_POINT",
        action='store',
        dest="fcp",
        sources={'play'},
    ),
    OptionSettings(
        ["--stop-cycle-point", "--stopcp"],
        help=(
            "Set the stop cycle point. Shut down after all"
            " have PASSED this cycle point. (Not to be confused"
            " the final cycle point.) This command line option overrides"
            " the workflow config option"
            " '[scheduling]stop after cycle point'."),
        metavar="CYCLE_POINT",
        action='store',
        dest="stopcp",
        sources={'play'},
    ),
    OptionSettings(
        ["--start-task", "--starttask", "-t"],
        help=(
            "Start from this task instance, given by '<cycle>/<name>'."
            " This can be used multiple times to start from multiple"
            " tasks at once. Dependence on tasks with cycle points earlier"
            " than the earliest start-task will be ignored. A"
            " sub-graph of the workflow will run if selected tasks do"
            " not lead on to the full graph."),
        metavar="TASK_ID",
        action='append',
        dest="starttask",
        sources={'play'},
    ),
    OptionSettings(
        ["--pause"],
        help="Pause the workflow immediately on start up.",
        action='store_true',
        default=False,
        dest="paused_start",
        sources={'play'},
    ),
    OptionSettings(
        ["--hold-after", "--hold-cycle-point", "--holdcp"],
        help="Hold all tasks after this cycle point.",
        metavar="CYCLE_POINT",
        action='store',
        dest="holdcp",
        sources={'play'},
    ),
    OptionSettings(
        ["--reference-log"],
        help="Generate a reference log for use in reference ",
        action='store_true',
        default=False,
        dest="genref",
        sources={'play'},
    ),
    OptionSettings(
        ["--reference-test"],
        help="Do a test run against a previously generated reference.",
        action='store_true',
        default=False,
        dest="reftest",
        sources={'play'},
    ),
    OptionSettings(
        ["--host"],
        help=(
            "Specify the host on which to start-up the workflow."
            " If not specified, a host will be selected using"
            " the '[scheduler]run hosts' global config."),
        metavar="HOST",
        action='store',
        dest="host",
        sources={'play'},
    ),
    OptionSettings(
        ["--format"],
        help="The format of the output: 'plain'=human readable, 'json'",
        choices=('plain', 'json'),
        default="plain",
        dest='format',
        sources={'play'},
    ),
    OptionSettings(
        ["--main-loop"],
        help=(
            "Specify an additional plugin to run in the main"
            " These are used in combination with those specified"
            " [scheduler][main loop]plugins. Can be used multiple times."),
        metavar="PLUGIN_NAME",
        action='append',
        dest="main_loop",
        sources={'play'},
    ),
    OptionSettings(
        ["--abort-if-any-task-fails"],
        help="If set workflow will abort with status 1 if any task fails.",
        action='store_true',
        default=False,
        dest="abort_if_any_task_fails",
        sources={'play'},
    ),
    PLAY_ICP_OPTION,
    PLAY_RUN_MODE,
    OptionSettings(
        ['--downgrade'],
        help=(
            'Allow the workflow to be restarted with an'
            ' older version of Cylc, NOT RECOMMENDED.'
            ' By default Cylc prevents you from restarting'
            ' a workflow with an older version of Cylc than'
            ' it was previously run with. Use this flag'
            ' to disable this check.'
        ),
        action='store_true',
        default=False,
        sources={'play'}
    ),
    OptionSettings(
        ['--upgrade'],
        help=(
            'Allow the workflow to be restarted with'
            ' a newer version of Cylc.'
        ),
        action='store_true',
        default=False,
        sources={'play'}
    ),
]


@lru_cache()
def get_option_parser(add_std_opts: bool = False) -> COP:
    """Parse CLI for "cylc play"."""
    parser = COP(
        PLAY_DOC,
        jset=True,
        comms=True,
        argdoc=[WORKFLOW_ID_ARG_DOC]
    )

    for option in PLAY_OPTIONS:
        parser.add_option(*option.args, **option.kwargs)

    if add_std_opts:
        # This is for the API wrapper for integration tests. Otherwise (CLI
        # use) "standard options" are added later in options.parse_args().
        # They should really be added in options.__init__() but that requires a
        # bit of refactoring because option clashes are handled bass-ackwards
        # ("overrides" are added before standard options).
        parser.add_std_options()

    return parser


# options we cannot simply extract from the parser
DEFAULT_OPTS = {
    'debug': False,
    'verbose': False,
    'templatevars': None,
    'templatevars_file': None
}


RunOptions = Options(get_option_parser(add_std_opts=True), DEFAULT_OPTS)


def _open_logs(id_: str, no_detach: bool, restart_num: int) -> None:
    """Open Cylc log handlers for a flow run."""
    if not no_detach:
        while LOG.handlers:
            LOG.handlers[0].close()
            LOG.removeHandler(LOG.handlers[0])
    log_path = get_workflow_run_scheduler_log_path(id_)
    LOG.addHandler(
        RotatingLogFileHandler(
            log_path,
            no_detach,
            restart_num=restart_num
        )
    )


async def _scheduler_cli_1(
    options: 'Values',
    workflow_id_raw: str,
    parse_workflow_id: bool = True
) -> Tuple[Scheduler, str]:
    """Run the workflow (part 1 - async).

    This function should contain all of the command line facing
    functionality of the Scheduler, exit codes, logging, etc.

    The Scheduler itself should be a Python object you can import and
    run in a regular Python session so cannot contain this kind of
    functionality.

    """
    if options.starttask:
        options.starttask = upgrade_legacy_ids(
            *options.starttask,
            relative=True,
        )

    # Parse workflow name but delay Cylc 7 suite.rc deprecation warning
    # until after the start-up splash is printed.
    # TODO: singleton
    if parse_workflow_id:
        (workflow_id,), _ = await parse_ids_async(
            workflow_id_raw,
            constraint='workflows',
            max_workflows=1,
            # warn_depr=False,  # TODO
        )
    else:
        workflow_id = workflow_id_raw

    # resume the workflow if it is already running
    await _resume(workflow_id, options)

    # check the workflow can be safely restarted with this version of Cylc
    db_file = Path(get_workflow_srv_dir(workflow_id), 'db')
    if not _version_check(db_file, options):
        sys.exit(1)

    # upgrade the workflow DB (after user has confirmed upgrade)
    _upgrade_database(db_file)

    # print the start message
    _print_startup_message(options)

    # re-execute on another host if required
    _distribute(workflow_id_raw, workflow_id, options)

    # setup the scheduler
    # NOTE: asyncio.run opens an event loop, runs your coro,
    #       then shutdown async generators and closes the event loop
    scheduler = Scheduler(workflow_id, options)
    await _setup(scheduler)

    return scheduler, workflow_id


def _scheduler_cli_2(
    options: 'Values',
    scheduler: Scheduler,
) -> None:
    """Run the workflow (part 2 - sync)."""
    # daemonize if requested
    # NOTE: asyncio event loops cannot persist across daemonization
    #       ensure you have tidied up all threads etc before daemonizing
    if not options.no_detach:
        from cylc.flow.daemonize import daemonize
        daemonize(scheduler)


async def _scheduler_cli_3(
    options: 'Values',
    workflow_id: str,
    scheduler: Scheduler,
) -> None:
    """Run the workflow (part 3 - async)."""
    # setup loggers
    _open_logs(
        workflow_id,
        options.no_detach,
        restart_num=scheduler.get_restart_num()
    )

    # run the workflow
    ret = await _run(scheduler)

    # exit
    # NOTE: we must clean up all asyncio / threading stuff before exiting
    # NOTE: any threads which include sleep statements could cause
    #       sys.exit to hang if not shutdown properly
    LOG.info("DONE")
    close_log(LOG)
    sys.exit(ret)


async def _resume(workflow_id, options):
    """Resume the workflow if it is already running."""
    try:
        detect_old_contact_file(workflow_id)
    except ContactFileExists as exc:
        print(f"Resuming already-running workflow\n\n{exc}")
        pclient = WorkflowRuntimeClient(
            workflow_id,
            timeout=options.comms_timeout,
        )
        mutation_kwargs = {
            'request_string': RESUME_MUTATION,
            'variables': {
                'wFlows': [workflow_id]
            }
        }
        await pclient.async_request('graphql', mutation_kwargs)
        sys.exit(0)
    except CylcError as exc:
        LOG.error(exc)
        LOG.critical(
            'Cannot tell if the workflow is running'
            '\nNote, Cylc 8 cannot restart Cylc 7 workflows.'
        )
        sys.exit(1)


def _version_check(
    db_file: Path,
    options: 'Values',
) -> bool:
    """Check the workflow can be safely restarted with this version of Cylc."""
    if not db_file.is_file():
        # not a restart
        return True
    this_version = Version(__version__)
    last_run_version = WorkflowDatabaseManager.check_db_compatibility(db_file)

    for itt, (this, that) in enumerate(zip_longest(
        this_version.release,
        last_run_version.release,
        fillvalue=-1,
    )):
        if this < that:
            # restart would REDUCE the Cylc version
            if options.downgrade:
                # permission to downgrade given in CLI flags
                LOG.warning(
                    'Restarting with an older version of Cylc'
                    f' ({last_run_version} -> {__version__})'
                )
                return True
            print(cparse(
                '<red>'
                'It is not advisible to restart a workflow with an older'
                ' version of Cylc than it was previously run with.'
                '</red>'

                '\n* This workflow was previously run with'
                f' <green>{last_run_version}</green>.'
                f'\n* This version of Cylc is <red>{__version__}</red>.'

                '\nUse --downgrade to disable this check (NOT RECOMMENDED!) or'
                ' use a more recent version e.g:'
                '<blue>'
                f'\n$ CYLC_VERSION={last_run_version} {" ".join(sys.argv[1:])}'
                '</blue>'
            ), file=sys.stderr)
            return False
        elif itt < 2 and this > that:
            # restart would INCREASE the Cylc version in a big way
            if options.upgrade:
                # permission to upgrade given in CLI flags
                LOG.warning(
                    'Restarting with a newer version of Cylc'
                    f' ({last_run_version} -> {__version__})'
                )
                return True
            print(cparse(
                'This workflow was previously run with'
                f' <yellow>{last_run_version}</yellow>.'
                f'\nThis version of Cylc is <green>{__version__}</green>.'
            ))
            if is_terminal():
                # we are in interactive mode, ask the user if this is ok
                options.upgrade = prompt(
                    cparse(
                        'Are you sure you want to upgrade from'
                        f' <yellow>{last_run_version}</yellow>'
                        f' to <green>{__version__}</green>?'
                    ),
                    {'y': True, 'n': False},
                    process=str.lower,
                )
                return options.upgrade
            # we are in non-interactive mode, abort abort abort
            print('Use "--upgrade" to upgrade the workflow.', file=sys.stderr)
            return False
        elif itt > 2 and this > that:
            # restart would INCREASE the Cylc version in a little way
            return True
    return True


def _upgrade_database(db_file: Path) -> None:
    """Upgrade the workflow database if needed.

    Note:
        Do this after the user has confirmed that they want to upgrade!

    """
    if db_file.is_file():
        WorkflowDatabaseManager.upgrade(db_file)


def _print_startup_message(options):
    """Print the Cylc header including the CLI logo to the user's terminal."""
    if (
        cylc.flow.flags.verbosity > -1
        and (options.no_detach or options.format == 'plain')
        # don't print the startup message on reinvocation (note
        # --host=localhost is the best indication we have that reinvokation has
        # happened)
        and options.host != 'localhost'
    ):
        print(
            cparse(
                cylc_header()
            )
        )

    if cylc.flow.flags.cylc7_back_compat:
        LOG.warning(SUITERC_DEPR_MSG)


def _distribute(
    workflow_id_raw: str, workflow_id: str, options: 'Values'
) -> None:
    """Re-invoke this command on a different host if requested.

    Args:
        workflow_id_raw:
            The workflow ID as it appears in the CLI arguments.
        workflow_id:
            The workflow ID after it has gone through the CLI.
            This may be different (i.e. the run name may have been inferred).
        options:
            The CLI options.

    """
    # Check whether a run host is explicitly specified, else select one.
    host = options.host or select_workflow_host()[0]
    if is_remote_host(host):
        # Protect command args from second shell interpretation
        cmd = list(map(quote, sys.argv[1:]))

        # Ensure the whole workflow ID is used
        if workflow_id_raw != workflow_id:
            # The CLI can infer run names but when we re-invoke the command
            # we would prefer it to use the full workflow ID to better
            # support monitoring systems.
            for ind, item in enumerate(cmd):
                if item == workflow_id_raw:
                    cmd[ind] = workflow_id

        # Prevent recursive host selection
        cmd.append("--host=localhost")

        # Ensure interactive upgrade carries over:
        if options.upgrade and '--upgrade' not in cmd:
            cmd.append('--upgrade')

        # Preserve CLI colour
        if is_terminal() and options.color != 'never':
            # the detached process doesn't pass the is_terminal test
            # so we have to explicitly tell Cylc to use color
            cmd.append('--color=always')
        else:
            # otherwise set --color=never to make testing easier
            cmd.append('--color=never')

        # Re-invoke the command
        # NOTE: has the potential to raise NoHostsError, however, this will
        # most likely have been raised during host-selection
        cylc_server_cmd(cmd, host=host)
        sys.exit(0)


async def _setup(scheduler: Scheduler) -> None:
    """Initialise the scheduler."""
    try:
        await scheduler.install()
    except ServiceFileError as exc:
        sys.exit(str(exc))


async def _run(scheduler: Scheduler) -> int:
    """Run the workflow and handle exceptions."""
    # run cylc run
    ret = 0
    try:
        await scheduler.run()

    # stop cylc stop
    except SchedulerError:
        ret = 1
    except Exception:
        ret = 3

    # kthxbye
    return ret


@cli_function(get_option_parser)
def play(parser: COP, options: 'Values', id_: str):
    cylc_play(options, id_)


def cylc_play(options: 'Values', id_: str, parse_workflow_id=True) -> None:
    """Implement cylc play.

    Raises:
        CylcError:
            If this function is called whilst an asyncio event loop is running.

            Because the scheduler process can be daemonised, this must not be
            called whilst an asyncio event loop is active as memory associated
            with this event loop will also exist in the new fork leading to
            potentially strange problems.

            See https://github.com/cylc/cylc-flow/issues/6291

    """
    try:
        # try opening an event loop to make sure there isn't one already open
        asyncio.get_running_loop()
    except RuntimeError:
        # start/restart/resume the workflow
        scheduler, workflow_id = asyncio.run(
            _scheduler_cli_1(options, id_, parse_workflow_id=parse_workflow_id)
        )
        _scheduler_cli_2(options, scheduler)
        asyncio.run(_scheduler_cli_3(options, workflow_id, scheduler))
    else:
        # if this line every gets hit then there is a bug within Cylc
        raise CylcError(
            'cylc_play called whilst asyncio event loop is running'
        ) from None
