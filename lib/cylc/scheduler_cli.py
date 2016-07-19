#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2016 NIWA
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

import sys

from cylc.option_parsers import CylcOptionParser as COP
import cylc.flags
from cylc.scheduler import Scheduler

RUN_DOC = r"""cylc [control] run|start [OPTIONS] ARGS

Start a suite run from scratch, wiping out any previous suite state. To
restart from a previous state see 'cylc restart --help'.

The scheduler runs in daemon mode unless you specify --no-detach or --debug.

Any dependence on cycle points earlier than the start cycle point is ignored.

A "cold start" (the default) starts from the suite's initial cycle point
(specified in the suite.rc or on the command line), and loads any special
one-off cold-start tasks (see below).

A "warm start" (-w/--warm) starts from a given cycle point that is later than
the initial cycle point (specified in the suite.rc), and loads any cold-start
tasks as succeeded just to satisfy initial dependence on them.  The original
suite initial cycle point is preserved, but all tasks and dependencies before
the given start cycle point are ignored.

Aside from the starting cycle point there is no difference between cold and
warm start unless you use special cold-start tasks. See "Suite Start-up" and
"Cold-Start Tasks" in the User Guide for more."""

RUN_ARG1 = (
    "[START_POINT]",
    "Initial cycle point or 'now';\n" +
    " " * 31 +  # 20 + len("START_POINT")
    "overrides the suite definition.")

RESTART_DOC = r"""cylc [control] restart [OPTIONS] ARGS

Start a suite run from a previous state. To start from scratch (cold or warm
start) see the 'cylc run' command.

The scheduler runs in daemon mode unless you specify n/--no-detach or --debug.

The most recent previous suite state is loaded by default, but earlier state
files in the suite state directory can be specified on the command line.

Tasks recorded as submitted or running are polled at start-up to determine what
happened to them while the suite was down."""

RESTART_ARG1 = (
    "[FILE]",
    "Optional state dump, assumed to reside in the\n" +
    " " * 24 +  # 20 + len("FILE")
    "suite state dump directory unless an absolute path\n" +
    " " * 24 +  # 20 + len("FILE")
    "is given. Defaults to the most recent suite state.")


def main(is_restart=False):
    """CLI main."""
    options, args = parse_commandline(is_restart)
    scheduler = Scheduler(is_restart, options, args)

    try:
        scheduler.start()
    except Exception as exc:
        if cylc.flags.debug:
            raise
        sys.exit(str(exc))


def parse_commandline(is_restart):
    """Parse CLI for "cylc run" or "cylc restart"."""
    if is_restart:
        doc = RESTART_DOC
        arg1 = RESTART_ARG1
    else:
        doc = RUN_DOC
        arg1 = RUN_ARG1
    parser = COP(doc, jset=True, argdoc=[("REG", "Suite name"), arg1])

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
            "--ignore-final-cycle-point",
            help=(
                "Ignore the final cycle point in the state dump. " +
                "If one is specified in the suite definition it will " +
                "be used, however."),
            action="store_true", default=False, dest="ignore_stop_point")

        parser.add_option(
            "--ignore-initial-cycle-point",
            help=(
                "Ignore the initial cycle point in the state dump. " +
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
        metavar="CYCLE_POINT", action="store",
        dest="final_point_string")

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
        help="Run mode: live, simulation, or dummy; default is live.",
        metavar="STRING", action="store", default='live', dest="run_mode",
        choices=["live", "dummy", "simulation"])

    parser.add_option(
        "--reference-log",
        help="Generate a reference log for use in reference tests.",
        action="store_true", default=False, dest="genref")

    parser.add_option(
        "--reference-test",
        help="Do a test run against a previously generated reference log.",
        action="store_true", default=False, dest="reftest")

    options, args = parser.parse_args()

    if not is_restart and options.warm and len(args) < 2:
        # Warm start must have a start point
        sys.exit(parser.get_usage())

    return options, args
