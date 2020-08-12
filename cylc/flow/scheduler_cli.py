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
"""Common logic for "cylc run" and "cylc restart" CLI."""

import asyncio
from functools import partial, lru_cache
from itertools import zip_longest
import os
import sys

from cylc.flow import LOG, __version__ as CYLC_VERSION
from cylc.flow.exceptions import SuiteServiceFileError
from cylc.flow.host_select import select_suite_host
from cylc.flow.hostuserutil import is_remote_host
from cylc.flow.loggingutil import TimestampRotatingFileHandler
from cylc.flow.option_parsers import (
    CylcOptionParser as COP,
    Options
)
from cylc.flow.pathutil import get_suite_run_dir
from cylc.flow.remote import remote_cylc_cmd
from cylc.flow.scheduler import Scheduler, SchedulerError
from cylc.flow import suite_files
from cylc.flow.terminal import cli_function


RUN_DOC = r"""cylc [control] run|start [OPTIONS] [ARGS]

Start a suite run from scratch, ignoring dependence prior to the start point.

WARNING: this will wipe out previous suite state. To restart from a previous
state, see 'cylc restart --help'.

The scheduler will run as a daemon unless you specify --no-detach.

If the suite is not already registered (by "cylc register" or a previous run)
it will be registered on the fly before start up.

Examples:
    # Run the suite registered with name REG.
    $ cylc run REG

    # Register $PWD/suite.rc as $(basename $PWD) and run it.
    # Note REG must be given explicitly if START_POINT is on the command line.
    $ cylc run

A "cold start" (the default) starts from the suite initial cycle point
(specified in the suite.rc or on the command line). Any dependence on tasks
prior to the suite initial cycle point is ignored.

A "warm start" (-w/--warm) starts from a given cycle point later than the suite
initial cycle point (specified in the suite.rc). Any dependence on tasks prior
to the given warm start cycle point is ignored. The suite initial cycle point
is preserved."""

RESTART_DOC = r"""cylc [control] restart [OPTIONS] ARGS

Start a suite run from the previous state. To start from scratch (cold or warm
start) see the 'cylc run' command.

The scheduler runs as a daemon unless you specify --no-detach.

Tasks recorded as submitted or running are polled at start-up to determine what
happened to them while the suite was down."""

SUITE_NAME_ARG_DOC = ("[REG]", "Suite name")
START_POINT_ARG_DOC = (
    "[START_POINT]",
    "Initial cycle point or 'now';\n" +
    " " * 31 +  # 20 + len("START_POINT")
    "overrides the suite definition.")


@lru_cache()
def get_option_parser(is_restart, add_std_opts=False):
    """Parse CLI for "cylc run" or "cylc restart"."""
    if is_restart:
        parser = COP(RESTART_DOC, jset=True, argdoc=[SUITE_NAME_ARG_DOC])
    else:
        parser = COP(
            RUN_DOC,
            icp=True,
            jset=True,
            argdoc=[SUITE_NAME_ARG_DOC, START_POINT_ARG_DOC])

    parser.add_option(
        "-n", "--no-detach", "--non-daemon",
        help="Do not daemonize the suite (infers --format=plain)",
        action="store_true", dest="no_detach")

    parser.add_option(
        "-a", "--no-auto-shutdown", help="Do not shut down"
        " the suite automatically when all tasks have finished."
        " This flag overrides the corresponding suite config item.",
        action="store_true", dest="no_auto_shutdown")

    parser.add_option(
        "--auto-shutdown", help="Shut down"
        " the suite automatically when all tasks have finished."
        " This flag overrides the corresponding suite config item.",
        action="store_false", dest="no_auto_shutdown")

    parser.add_option(
        "--profile", help="Output profiling (performance) information",
        action="store_true", dest="profile_mode")

    if is_restart:
        parser.add_option(
            "--checkpoint",
            help="Specify the ID of a checkpoint to restart from",
            metavar="CHECKPOINT-ID", action="store", dest="checkpoint")

        parser.add_option(
            "--ignore-initial-cycle-point",
            help=(
                "Ignore the initial cycle point in the suite run database. " +
                "If one is specified in the suite definition it will " +
                "be used, however."),
            action="store_true", dest="ignore_icp")

        parser.add_option(
            "--ignore-final-cycle-point",
            help=(
                "Ignore the final cycle point in the suite run database. " +
                "If one is specified in the suite definition it will " +
                "be used, however."),
            action="store_true", dest="ignore_fcp")

        parser.add_option(
            "--ignore-start-cycle-point",
            help="Ignore the start cycle point in the suite run database.",
            action="store_true", dest="ignore_startcp")

        parser.add_option(
            "--ignore-stop-cycle-point",
            help="Ignore the stop cycle point in the suite run database.",
            action="store_true", dest="ignore_stopcp")

        parser.set_defaults(icp=None, startcp=None, warm=None)
    else:
        parser.add_option(
            "-w", "--warm",
            help="Warm start the suite. The default is to cold start.",
            action="store_true", dest="warm")

        parser.add_option(
            "--start-cycle-point", "--start-point",
            help=(
                "Set the start cycle point. Implies --warm."
                "(Not to be confused with the initial cycle point.)"
            ),
            metavar="CYCLE_POINT", action="store", dest="startcp")

    parser.add_option(
        "--final-cycle-point", "--final-point", "--until", "--fcp",
        help="Set the final cycle point.",
        metavar="CYCLE_POINT", action="store", dest="fcp")

    parser.add_option(
        "--stop-cycle-point", "--stop-point",
        help=(
            "Set stop point. "
            "Shut down after all tasks have PASSED this cycle point. "
            "(Not to be confused with the final cycle point.)"
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
            "the 'suite servers' global config."
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
            " [cylc][main loop]plugins. Can be used multiple times"
        ),
        metavar="PLUGIN_NAME", action="append", dest="main_loop"
    )

    parser.set_defaults(stop_point_string=None)
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
    get_option_parser(is_restart=False, add_std_opts=True), DEFAULT_OPTS)
RestartOptions = Options(
    get_option_parser(is_restart=True, add_std_opts=True), DEFAULT_OPTS)


def _auto_register():
    """Register a suite installed in the cylc-run directory."""
    try:
        reg = suite_files.register()
    except SuiteServiceFileError as exc:
        sys.exit(exc)
    # Replace this process with "cylc run REG ..." for 'ps -f'.
    os.execv(sys.argv[0], [sys.argv[0]] + [reg] + sys.argv[1:])


def _open_logs(reg, no_detach):
    """Open Cylc log handlers for a flow run."""
    if not no_detach:
        while LOG.handlers:
            LOG.handlers[0].close()
            LOG.removeHandler(LOG.handlers[0])
    LOG.addHandler(TimestampRotatingFileHandler(reg, no_detach))


def _close_logs():
    """Close Cylc log handlers for a flow run."""
    for handler in LOG.handlers:
        try:
            handler.close()
        except IOError:
            # suppress traceback which `logging` might try to write to the
            # log we are trying to close
            pass


def _start_print_blurb():
    """Print copyright and license information."""
    logo = (
        "            ._.       \n"
        "            | |       \n"
        "._____._. ._| |_____. \n"
        "| .___| | | | | .___| \n"
        "| !___| !_! | | !___. \n"
        "!_____!___. |_!_____! \n"
        "      .___! |         \n"
        "      !_____!         \n"
    )
    cylc_license = """
The Cylc Suite Engine [%s]
Copyright (C) 2008-2019 NIWA
& British Crown (Met Office) & Contributors.
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
This program comes with ABSOLUTELY NO WARRANTY.
It is free software, you are welcome to
redistribute it under certain conditions;
see `COPYING' in the Cylc source distribution.
""" % CYLC_VERSION

    logo_lines = logo.splitlines()
    license_lines = cylc_license.splitlines()
    lmax = max(len(line) for line in license_lines)
    print(('\n'.join((
        ('{0} {1: ^%s}' % lmax).format(*x) for x in zip_longest(
            logo_lines, license_lines, fillvalue=' ' * (
                len(logo_lines[-1]) + 1))))))


def scheduler_cli(parser, options, args, is_restart=False):
    """Implement cylc (run|restart).

    This function should contain all of the command line facing
    functionality of the Scheduler, exit codes, logging, etc.

    The Scheduler itself should be a Python object you can import and
    run in a regular Python session so cannot contain this kind of
    functionality.

    """
    reg = args[0]
    # Check suite is not already running before start of host selection.
    try:
        suite_files.detect_old_contact_file(reg)
    except SuiteServiceFileError as exc:
        sys.exit(exc)

    _check_registration(reg)

    # re-execute on another host if required
    _distribute(options.host, is_restart)

    # print the start message
    if options.no_detach or options.format == 'plain':
        _start_print_blurb()

    # setup the scheduler
    # NOTE: asyncio.run opens an event loop, runs your coro,
    #       then shutdown async generators and closes the event loop
    scheduler = Scheduler(reg, options, is_restart=is_restart)
    asyncio.run(
        _setup(parser, options, reg, is_restart, scheduler)
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
        _run(parser, options, reg, is_restart, scheduler)
    )

    # exit
    # NOTE: we must clean up all asyncio / threading stuff before exiting
    # NOTE: any threads which include sleep statements could cause
    #       sys.exit to hang if not shutdown properly
    LOG.info("DONE")
    _close_logs()
    sys.exit(ret)


def _check_registration(reg):
    """Ensure the flow is registered."""
    suite_run_dir = get_suite_run_dir(reg)
    if not os.path.exists(suite_run_dir):
        sys.stderr.write(f'suite service directory not found '
                         f'at: {suite_run_dir}\n')
        sys.exit(1)


def _distribute(host, is_restart):
    """Re-invoke this command on a different host if requested."""
    # Check whether a run host is explicitly specified, else select one.
    if not host:
        host = select_suite_host()[0]
    if is_remote_host(host):
        if is_restart:
            base_cmd = ["restart"] + sys.argv[1:]
        else:
            base_cmd = ["run"] + sys.argv[1:]
        # Prevent recursive host selection
        base_cmd.append("--host=localhost")
        remote_cylc_cmd(base_cmd, host=host)
        sys.exit(0)


async def _setup(parser, options, reg, is_restart, scheduler):
    """Initialise the scheduler."""
    try:
        await scheduler.install()
    except SuiteServiceFileError as exc:
        sys.exit(exc)


async def _run(parser, options, reg, is_restart, scheduler):
    """Run the workflow and handle exceptions."""
    # run cylc run
    ret = 0
    try:
        await scheduler.run()

    # stop cylc stop
    except SchedulerError:
        ret = 1
    except KeyboardInterrupt as exc:
        try:
            await scheduler.shutdown(exc)
        except Exception as exc2:
            # In case of exceptions in the shutdown method itself.
            LOG.exception(exc2)
            raise exc2 from None
        ret = 2
    except Exception:
        ret = 3

    # kthxbye
    finally:
        return ret


def main(is_restart=False):
    """Abstraction for cylc (run|restart) CLI"""
    # the cli_function decorator changes the function signature which
    # irritates pylint.
    if is_restart:
        return restart()  # pylint: disable=E1120
    else:
        return run()  # pylint: disable=E1120


@cli_function(partial(get_option_parser, is_restart=True))
def restart(parser, options, *args):
    """Implement cylc restart."""
    return scheduler_cli(parser, options, args, is_restart=True)


@cli_function(partial(get_option_parser, is_restart=False))
def run(parser, options, *args):
    """Implement cylc run."""
    if not args:
        _auto_register()
    if options.startcp:
        options.warm = True
    if len(args) >= 2:
        if not options.warm and not options.icp:
            options.icp = args[1]
        elif options.warm and not options.startcp:
            options.startcp = args[1]
    if options.warm and not options.startcp:
        # Warm start must have a start point
        sys.exit(parser.get_usage())
    return scheduler_cli(parser, options, args, is_restart=False)
