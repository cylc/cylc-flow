#!/usr/bin/env python3

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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

import os
import sys

from cylc import LOG
from cylc.cfgspec.glbl_cfg import glbl_cfg
import cylc.flags
from cylc.host_appointer import HostAppointer, EmptyHostList
from cylc.hostuserutil import is_remote_host
from cylc.option_parsers import CylcOptionParser as COP
from cylc.remote import remrun, remote_cylc_cmd
from cylc.scheduler import Scheduler
from cylc.suite_srv_files_mgr import (
    SuiteSrvFilesManager, SuiteServiceFileError)
from cylc.terminal import cli_function

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


@cli_function
def main(is_restart=False):
    """CLI main."""
    options, args = parse_commandline(is_restart)
    if not args:
        # Auto-registration: "cylc run" (no args) in source dir.
        try:
            reg = SuiteSrvFilesManager().register()
        except SuiteServiceFileError as exc:
            sys.exit(exc)
        # Replace this process with "cylc run REG ..." for 'ps -f'.
        os.execv(sys.argv[0], [sys.argv[0]] + [reg] + sys.argv[1:])

    # Check suite is not already running before start of host selection.
    try:
        SuiteSrvFilesManager().detect_old_contact_file(args[0])
    except SuiteServiceFileError as exc:
        sys.exit(exc)

    # Create auth files if needed.
    SuiteSrvFilesManager().create_auth_files(args[0])

    # Check whether a run host is explicitly specified, else select one.
    if not options.host:
        try:
            host = HostAppointer().appoint_host()
        except EmptyHostList as exc:
            if cylc.flags.debug:
                raise
            else:
                sys.exit(str(exc))
        if is_remote_host(host):
            if is_restart:
                base_cmd = ["restart"] + sys.argv[1:]
            else:
                base_cmd = ["run"] + sys.argv[1:]
            # Prevent recursive host selection
            base_cmd.append("--host=localhost")
            return remote_cylc_cmd(base_cmd, host=host)
    if remrun(set_rel_local=True):  # State localhost as above.
        sys.exit()

    try:
        SuiteSrvFilesManager().get_suite_source_dir(args[0], options.owner)
    except SuiteServiceFileError:
        # Source path is assumed to be the run directory
        SuiteSrvFilesManager().register(
            args[0],
            glbl_cfg().get_derived_host_item(args[0], 'suite run directory'))

    try:
        scheduler = Scheduler(is_restart, options, args)
    except SuiteServiceFileError as exc:
        sys.exit(exc)
    scheduler.start()


def parse_commandline(is_restart):
    """Parse CLI for "cylc run" or "cylc restart"."""
    if is_restart:
        parser = COP(RESTART_DOC, jset=True, argdoc=[SUITE_NAME_ARG_DOC])
    else:
        parser = COP(
            RUN_DOC, jset=True,
            argdoc=[SUITE_NAME_ARG_DOC, START_POINT_ARG_DOC])

    parser.add_option(
        "--non-daemon", help="(deprecated: use --no-detach)",
        action="store_true", default=False, dest="no_detach")

    parser.add_option(
        "-n", "--no-detach", help="Do not daemonize the suite",
        action="store_true", default=False, dest="no_detach")

    parser.add_option(
        "-a", "--no-auto-shutdown", help="Do not shut down"
        " the suite automatically when all tasks have finished."
        " This flag overrides the corresponding suite config item.",
        action="store_true", default=False, dest="no_auto_shutdown")

    parser.add_option(
        "--profile", help="Output profiling (performance) information",
        action="store_true", default=False, dest="profile_mode")

    if is_restart:
        parser.add_option(
            "--checkpoint",
            help="Specify the ID of a checkpoint to restart from",
            metavar="CHECKPOINT-ID", action="store", dest="checkpoint")

        parser.add_option(
            "--ignore-final-cycle-point",
            help=(
                "Ignore the final cycle point in the suite run database. " +
                "If one is specified in the suite definition it will " +
                "be used, however."),
            action="store_true", default=False, dest="ignore_stop_point")

        parser.add_option(
            "--ignore-initial-cycle-point",
            help=(
                "Ignore the initial cycle point in the suite run database. " +
                "If one is specified in the suite definition it will " +
                "be used, however."),
            action="store_true", default=False, dest="ignore_start_point")
    else:
        parser.add_option(
            "-w", "--warm",
            help="Warm start the suite. "
                 "The default is to cold start.",
            action="store_true", default=False, dest="warm")

        parser.add_option(
            "--ict",
            help="Does nothing, option for backward compatibility only",
            action="store_true", default=False, dest="set_ict")

    parser.add_option(
        "--until",
        help=("Shut down after all tasks have PASSED " +
              "this cycle point."),
        metavar="CYCLE_POINT", action="store", dest="final_point_string")

    parser.add_option(
        "--hold",
        help="Hold (don't run tasks) immediately on starting.",
        action="store_true", default=False, dest="start_held")

    parser.add_option(
        "--hold-after",
        help="Hold (don't run tasks) AFTER this cycle point.",
        metavar="CYCLE_POINT", action="store", dest="hold_point_string")

    parser.add_option(
        "-m", "--mode",
        help="Run mode: live, dummy, dummy-local, simulation (default live).",
        metavar="STRING", action="store", default='live', dest="run_mode",
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
        help="Specify the host on which to start-up the suite. Without this "
        "set a host will be selected using the 'suite servers' global config.",
        metavar="HOST", action="store", dest="host")

    options, args = parser.parse_args()

    if not is_restart and options.warm and len(args) < 2:
        # Warm start must have a start point
        sys.exit(parser.get_usage())

    return options, args
