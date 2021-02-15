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
"""Common logic for "cylc play" CLI."""

import asyncio
from functools import lru_cache
import os
import sys

from ansimarkup import parse as cparse
from pathlib import Path

from cylc.flow import LOG, RSYNC_LOG
from cylc.flow.exceptions import SuiteServiceFileError
from cylc.flow.host_select import select_suite_host
from cylc.flow.hostuserutil import is_remote_host
from cylc.flow.loggingutil import TimestampRotatingFileHandler
from cylc.flow.option_parsers import (
    CylcOptionParser as COP,
    Options
)
from cylc.flow.pathutil import (
    get_workflow_run_dir,
    get_suite_run_log_name,
    get_suite_file_install_log_name)
from cylc.flow.remote import _remote_cylc_cmd
from cylc.flow.scheduler import Scheduler, SchedulerError
from cylc.flow.scripts import cylc_header
from cylc.flow import suite_files
from cylc.flow.terminal import cli_function

PLAY_DOC = r"""cylc [control] play [OPTIONS] [ARGS]

Start running a workflow, or restart a stopped workflow from its previous
state/cycle point, or resume a paused workflow by releasing all tasks.

The scheduler will run as a daemon unless you specify --no-detach.

If the workflow is not already installed (by "cylc install" or a previous run)
it will be installed on the fly before start up.

Examples:
    # Start/restart the workflow with name REG.
    $ cylc play REG

A "cold start" (the default for a freshly-installed workflow) starts from the
initial cycle point (specified in flow.cylc or on the command line). Any
dependence on tasks prior to the initial cycle point is ignored.
It is also possible to start from a point that is later than the initial cycle
point, using the option --startcp=CYCLE_POINT. The initial cycle point is
preserved, but the workflow does not start there and instead starts part-way
through the graph (historically known as a "warm start").

A "restart" continues on from the most recent recorded state of the workflow.
Tasks recorded as submitted or running are polled at restart to determine what
happened to them while the workflow was shut down."""


FLOW_NAME_ARG_DOC = ("REG", "Workflow name")


@lru_cache()
def get_option_parser(add_std_opts=False):
    """Parse CLI for "cylc play"."""
    parser = COP(
        PLAY_DOC,
        icp=True,
        jset=True,
        argdoc=[FLOW_NAME_ARG_DOC])

    parser.add_option(
        "-n", "--no-detach", "--non-daemon",
        help="Do not daemonize the suite (infers --format=plain)",
        action="store_true", dest="no_detach")

    parser.add_option(
        "--profile", help="Output profiling (performance) information",
        action="store_true", dest="profile_mode")

    parser.add_option(
        "--start-cycle-point", "--startcp",
        help=(
            "Set the start cycle point, which may be after the initial cycle "
            "point. If the specified start point is not in the sequeunce, the "
            "next on-sequence point will be used. "
            "(Not to be confused with the initial cycle point.) "
            "This replaces the Cylc 7 --warm option."
        ),
        metavar="CYCLE_POINT", action="store", dest="startcp")

    parser.add_option(
        "--final-cycle-point", "--fcp",
        help=(
            "Set the final cycle point. "
            "This command line option overrides the workflow "
            "config option '[scheduling]final cycle point'."
        ),
        metavar="CYCLE_POINT", action="store", dest="fcp")

    parser.add_option(
        "--stop-cycle-point", "--stopcp",
        help=(
            "Set the stop cycle point. "
            "Shut down after all tasks have PASSED this cycle point. "
            "(Not to be confused with the final cycle point.) "
            "This command line option overrides the workflow "
            "config option '[scheduling]stop after cycle point'."
        ),
        metavar="CYCLE_POINT", action="store", dest="stopcp")

    parser.add_option(
        "--hold",
        help="Hold suite immediately on starting.",
        action="store_true", dest="hold_start")

    parser.add_option(
        "--hold-point", "--hold-after",
        help=(
            "Set hold cycle point. "
            "Hold suite AFTER all tasks have PASSED this cycle point."
        ),
        metavar="CYCLE_POINT", action="store", dest="holdcp")

    parser.add_option(
        "-m", "--mode",
        help="Run mode: live, dummy, dummy-local, simulation (default live).",
        metavar="STRING", action="store", dest="run_mode",
        choices=["live", "dummy", "dummy-local", "simulation"])

    parser.add_option(
        "--reference-log",
        help="Generate a reference log for use in reference tests.",
        action="store_true", default=False, dest="genref")

    parser.add_option(
        "--reference-test",
        help="Do a test run against a previously generated reference log.",
        action="store_true", default=False, dest="reftest")

    # Override standard parser option for specific help description.
    parser.add_option(
        "--host",
        help=(
            "Specify the host on which to start-up the suite. "
            "If not specified, a host will be selected using "
            "the '[scheduler]run hosts' global config."
        ),
        metavar="HOST", action="store", dest="host")

    parser.add_option(
        "--format",
        help="The format of the output: 'plain'=human readable, 'json'",
        choices=("plain", "json"),
        default="plain"
    )

    parser.add_option(
        "--main-loop",
        help=(
            "Specify an additional plugin to run in the main loop."
            " These are used in combination with those specified in"
            " [scheduler][main loop]plugins. Can be used multiple times"
        ),
        metavar="PLUGIN_NAME", action="append", dest="main_loop"
    )

    parser.add_option(
        "--abort-if-any-task-fails",
        help="If set workflow will abort with status 1 if any task fails.",
        action="store_true", default=False, dest="abort_if_any_task_fails"
    )

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


RunOptions = Options(
    get_option_parser(add_std_opts=True), DEFAULT_OPTS)


def _auto_install():
    """Register workflow installed in the cylc-run directory"""
    try:
        reg = suite_files.register()
    except SuiteServiceFileError as exc:
        sys.exit(exc)
    # Replace this process with "cylc play REG ..." for 'ps -f'.
    os.execv(
        sys.argv[0],
        [sys.argv[0]] + sys.argv[1:] + [reg]
    )


def _open_logs(reg, no_detach):
    """Open Cylc log handlers for a flow run."""
    if not no_detach:
        while LOG.handlers:
            LOG.handlers[0].close()
            LOG.removeHandler(LOG.handlers[0])
    suite_log_handler = get_suite_run_log_name(reg)
    LOG.addHandler(
        TimestampRotatingFileHandler(
            suite_log_handler,
            no_detach))

    # Add file installation log
    file_install_log_path = get_suite_file_install_log_name(reg)
    handler = TimestampRotatingFileHandler(file_install_log_path, no_detach)
    RSYNC_LOG.addHandler(handler)


def _close_logs():
    """Close Cylc log handlers for a flow run."""
    for handler in LOG.handlers:
        try:
            handler.close()
        except IOError:
            # suppress traceback which `logging` might try to write to the
            # log we are trying to close
            pass


def scheduler_cli(parser, options, reg):
    """Run the workflow.

    This function should contain all of the command line facing
    functionality of the Scheduler, exit codes, logging, etc.

    The Scheduler itself should be a Python object you can import and
    run in a regular Python session so cannot contain this kind of
    functionality.

    """
    reg = os.path.normpath(reg)
    try:
        suite_files.detect_old_contact_file(reg)
    except SuiteServiceFileError as exc:
        # TODO: unpause
        print(f"Workflow is already running\n\n{exc}")
        sys.exit(0)

    _check_srvd(reg)

    # re-execute on another host if required
    _distribute(options.host)

    # print the start message
    if options.no_detach or options.format == 'plain':
        print(
            cparse(
                cylc_header()
            )
        )

    # setup the scheduler
    # NOTE: asyncio.run opens an event loop, runs your coro,
    #       then shutdown async generators and closes the event loop
    scheduler = Scheduler(reg, options)
    asyncio.run(
        _setup(parser, options, reg, scheduler)
    )

    # daemonize if requested
    # NOTE: asyncio event loops cannot persist across daemonization
    #       ensure you have tidied up all threads etc before daemonizing
    if not options.no_detach:
        from cylc.flow.daemonize import daemonize
        daemonize(scheduler)

    # setup loggers
    _open_logs(reg, options.no_detach)

    # run the workflow
    ret = asyncio.run(
        _run(parser, options, reg, scheduler)
    )

    # exit
    # NOTE: we must clean up all asyncio / threading stuff before exiting
    # NOTE: any threads which include sleep statements could cause
    #       sys.exit to hang if not shutdown properly
    LOG.info("DONE")
    _close_logs()
    sys.exit(ret)


def _check_srvd(reg):
    """Check the run dir contains .service dir"""
    workflow_run_dir = get_workflow_run_dir(reg)
    if not Path(workflow_run_dir,
                suite_files.SuiteFiles.Service.DIRNAME).exists:
        sys.stderr.write(f'suite service directory not found '
                         f'at: {workflow_run_dir}\n')
        sys.exit(1)


def _distribute(host):
    """Re-invoke this command on a different host if requested."""
    # Check whether a run host is explicitly specified, else select one.
    if not host:
        host = select_suite_host()[0]
    if is_remote_host(host):
        # Prevent recursive host selection
        cmd = sys.argv[1:]
        cmd.append("--host=localhost")
        _remote_cylc_cmd(cmd, host=host)
        sys.exit(0)


async def _setup(parser, options, reg, scheduler):
    """Initialise the scheduler."""
    try:
        await scheduler.install()
    except SuiteServiceFileError as exc:
        sys.exit(exc)


async def _run(parser, options, reg, scheduler):
    """Run the workflow and handle exceptions."""
    # run cylc run
    ret = 0
    try:
        await scheduler.run()

    # stop cylc stop
    except SchedulerError:
        ret = 1
    except (KeyboardInterrupt, asyncio.CancelledError):
        ret = 2
    except Exception:
        ret = 3

    # kthxbye
    finally:
        return ret


@cli_function(get_option_parser)
def play(parser, options, reg):
    """Implement cylc play."""
    return scheduler_cli(parser, options, reg)
