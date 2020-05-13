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

from functools import partial
import os
import sys

import cylc.flow.flags
from cylc.flow.exceptions import SuiteServiceFileError
from cylc.flow.host_select import select_suite_host
from cylc.flow.hostuserutil import is_remote_host
from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.pathutil import get_suite_run_dir
from cylc.flow.remote import remrun, remote_cylc_cmd
from cylc.flow.scheduler import Scheduler
from cylc.flow import suite_files
from cylc.flow.suite_files import (KeyInfo, KeyOwner, KeyType)
from cylc.flow.resources import extract_resources
from cylc.flow.terminal import cli_function

RUN_DOC = r"""cylc [control] run|start [OPTIONS] [ARGS]

Start a suite run from scratch, ignoring dependence prior to the start point.

WARNING: this will wipe out previous suite state. To restart from a previous
state, see 'cylc restart --help'.

The scheduler will run as a daemon unless you specify --no-detach.

If the suite is not already registered (by "cylc register" or a previous run)
it will be registered on the fly before start up.

% cylc run REG
  Run the suite registered with name REG.

% cylc run
  Register $PWD/suite.rc as $(basename $PWD) and run it.
 (Note REG must be given explicitly if START_POINT is on the command line.)

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


def get_option_parser(is_restart):
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

    return parser


def _auto_register():
    """Register a suite installed in the cylc-run directory."""
    try:
        reg = suite_files.register()
    except SuiteServiceFileError as exc:
        sys.exit(exc)
    # Replace this process with "cylc run REG ..." for 'ps -f'.
    os.execv(sys.argv[0], [sys.argv[0]] + [reg] + sys.argv[1:])


def scheduler_cli(parser, options, args, is_restart=False):
    """CLI main."""
    reg = args[0]
    # Check suite is not already running before start of host selection.
    try:
        suite_files.detect_old_contact_file(reg)
    except SuiteServiceFileError as exc:
        sys.exit(exc)

    suite_run_dir = get_suite_run_dir(reg)

    if not os.path.exists(suite_run_dir):
        sys.stderr.write(f'suite service directory not found '
                         f'at: {suite_run_dir}\n')
        sys.exit(1)

    # Extract job.sh from library, for use in job scripts.
    extract_resources(
        suite_files.get_suite_srv_dir(reg),
        ['etc/job.sh'])

    # Check whether a run host is explicitly specified, else select one.
    if not options.host:
        host = select_suite_host()[0]
        if is_remote_host(host):
            if is_restart:
                base_cmd = ["restart"] + sys.argv[1:]
            else:
                base_cmd = ["run"] + sys.argv[1:]
            # Prevent recursive host selection
            base_cmd.append("--host=localhost")
            return remote_cylc_cmd(base_cmd, host=host)
    suite_srv_dir = suite_files.get_suite_srv_dir(reg)
    keys = {
        "client_public_key": KeyInfo(
            KeyType.PUBLIC,
            KeyOwner.CLIENT,
            suite_srv_dir=suite_srv_dir, platform=host),
        "client_private_key": KeyInfo(
            KeyType.PRIVATE,
            KeyOwner.CLIENT,
            suite_srv_dir=suite_srv_dir),
        "server_public_key": KeyInfo(
            KeyType.PUBLIC,
            KeyOwner.SERVER,
            suite_srv_dir=suite_srv_dir),
        "server_private_key": KeyInfo(
            KeyType.PRIVATE,
            KeyOwner.SERVER,
            suite_srv_dir=suite_srv_dir)
    }
    # Clean any existing authentication keys and create new ones.
    suite_files.remove_keys_on_server(keys)
    suite_files.create_server_keys(keys, suite_srv_dir)
    if remrun(set_rel_local=True):  # State localhost as above.
        sys.exit()

    try:
        suite_files.get_suite_source_dir(args[0], options.owner)
    except SuiteServiceFileError:
        # Source path is assumed to be the run directory
        suite_files.register(args[0], get_suite_run_dir(args[0]))

    try:
        scheduler = Scheduler(is_restart, options, args)
    except SuiteServiceFileError as exc:
        sys.exit(exc)
    scheduler.start()


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
