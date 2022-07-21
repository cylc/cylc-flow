#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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

"""cylc cycle-point [OPTIONS] ARGS

Utility for simple date-time cycle point arithmetic.

For more generic date-time manipulations see the "isodatetime" command.

Filename templating replaces elements of a template string with corresponding
elements of the current or given cycle point.

Use ISO 8601 or posix date-time format elements:
  $ cylc cycle-point 2010080T00 --template foo-CCYY-MM-DD-Thh.nc
  foo-2010-08-08-T00.nc
  $ cylc cycle-point 2010080T00 --template foo-%Y-%m-%d-T%H.nc
  foo-2010-08-08-T00.nc

Other examples:
  # print offset from an explicit cycle point:
  $ cylc cycle-point --offset-hours=6 20100823T1800Z
  20100824T0000Z

  # print offset from $CYLC_TASK_CYCLE_POINT (as in workflow tasks):
  $ export CYLC_TASK_CYCLE_POINT=20100823T1800Z
  $ cylc cycle-point --offset-hours=-6
  20100823T1200Z

  # cycle point filename templating, explicit template:
  $ export CYLC_TASK_CYCLE_POINT=2010-08
  $ cylc cycle-point --offset-years=2 --template=foo-CCYY-MM.nc
  foo-2012-08.nc

  # cycle point filename templating, template in a variable:
  $ export CYLC_TASK_CYCLE_POINT=2010-08
  $ export MYTEMPLATE=foo-CCYY-MM.nc
  $ cylc cycle-point --offset-years=2 --template=MYTEMPLATE
  foo-2012-08.nc
"""

import os
import sys

import cylc.flow.cycling.iso8601
from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.terminal import cli_function

import metomi.isodatetime.data
import metomi.isodatetime.dumpers
import metomi.isodatetime.parsers
from metomi.isodatetime.exceptions import IsodatetimeError


def get_option_parser() -> COP:
    parser = COP(
        __doc__,
        color=False,
        argdoc=[
            COP.optional(
                ('POINT', 'ISO8601 date-time, default=$CYLC_TASK_CYCLE_POINT')
            )
        ]
    )

    parser.add_option(
        "--offset-hours", metavar="HOURS",
        help="Add N hours to CYCLE (may be negative)",
        action="store", dest="offsethours")

    parser.add_option(
        "--offset-days", metavar="DAYS",
        help="Add N days to CYCLE (N may be negative)",
        action="store", dest="offsetdays")

    parser.add_option(
        "--offset-months", metavar="MONTHS",
        help="Add N months to CYCLE (N may be negative)",
        action="store", dest="offsetmonths")

    parser.add_option(
        "--offset-years", metavar="YEARS",
        help="Add N years to CYCLE (N may be negative)",
        action="store", dest="offsetyears")

    parser.add_option(
        "--offset", metavar="ISO_OFFSET",
        help="Add an ISO 8601-based interval representation to CYCLE",
        action="store", dest="offset")

    parser.add_option(
        "--equal", metavar="POINT2",
        help="Succeed if POINT2 is equal to POINT (format agnostic).",
        action="store", dest="point2")

    parser.add_option(
        "--template", metavar="TEMPLATE",
        help="Filename template string or variable",
        action="store", dest="template")

    parser.add_option(
        "--time-zone", metavar="TEMPLATE",
        help="Control the formatting of the result's timezone e.g. "
             "(Z, +13:00, -hh",
        action="store", default=None, dest="time_zone")

    parser.add_option(
        "--num-expanded-year-digits", metavar="NUMBER",
        help="Specify a number of expanded year digits to print in the result",
        action="store", default=0, dest="num_expanded_year_digits")

    parser.add_option(
        "--print-year", help="Print only CCYY of result",
        action="store_true", default=False, dest="print_year")

    parser.add_option(
        "--print-month", help="Print only MM of result",
        action="store_true", default=False, dest="print_month")

    parser.add_option(
        "--print-day", help="Print only DD of result",
        action="store_true", default=False, dest="print_day")

    parser.add_option(
        "--print-hour", help="Print only hh of result",
        action="store_true", default=False, dest="print_hour")

    return parser


@cli_function(get_option_parser)
def main(parser, options, *args):
    if len(args) == 0:
        # input cycle point must be defined in the environment.
        if 'CYLC_TASK_CYCLE_POINT' not in os.environ:
            parser.error("Provide CYCLE arg, or define $CYLC_TASK_CYCLE_POINT")
        cycle_point_string = os.environ['CYLC_TASK_CYCLE_POINT']

    else:
        # must be cycle point
        cycle_point_string = args[0]

    # template string
    template = None
    if options.template:
        if (options.print_month or options.print_year or options.print_day or
                options.print_hour):
            parser.error(
                '"print only" options are incompatible with templating')
        tmp = options.template
        template = os.environ.get(tmp, tmp)
    else:
        n_chosen = 0

        if options.print_year:
            n_chosen += 1
            if options.num_expanded_year_digits:
                template = "±XCCYY"
            else:
                template = "CCYY"

        if options.print_month:
            n_chosen += 1
            template = "MM"

        if options.print_day:
            n_chosen += 1
            template = "DD"

        if options.print_hour:
            n_chosen += 1
            template = "%H"

        if n_chosen != 0 and n_chosen != 1:
            parser.error("Choose NONE or ONE of print_(year|month|day|hour)")

    cylc.flow.cycling.iso8601.init(
        num_expanded_year_digits=options.num_expanded_year_digits,
        time_zone=options.time_zone
    )
    iso_point_parser = metomi.isodatetime.parsers.TimePointParser(
        num_expanded_year_digits=options.num_expanded_year_digits
    )
    iso_point_dumper = metomi.isodatetime.dumpers.TimePointDumper(
        num_expanded_year_digits=options.num_expanded_year_digits
    )
    try:
        cycle_point = iso_point_parser.parse(
            cycle_point_string, dump_as_parsed=(template is None))
    except IsodatetimeError as exc:
        parser.error('ERROR: invalid cycle: %s' % exc)

    if options.point2:
        try:
            cycle_point2 = iso_point_parser.parse(
                options.point2, dump_as_parsed=(template is None))
        except IsodatetimeError as exc:
            parser.error('ERROR: invalid cycle: %s' % exc)
        if cycle_point2 == cycle_point:
            sys.exit(0)
        else:
            sys.exit(1)

    offset_props = {}

    if options.offsethours:
        try:
            offset_props["hours"] = int(options.offsethours)
        except ValueError:
            parser.error('ERROR: offset must be integer')

    if options.offsetdays:
        try:
            offset_props["days"] = int(options.offsetdays)
        except ValueError:
            parser.error('ERROR: offset must be integer')

    if options.offsetmonths:
        try:
            offset_props["months"] = int(options.offsetmonths)
        except ValueError:
            parser.error('ERROR: offset must be integer')

    if options.offsetyears:
        try:
            offset_props["years"] = int(options.offsetyears)
        except ValueError:
            parser.error('ERROR: offset must be integer')

    offset = metomi.isodatetime.data.Duration(**offset_props)

    if options.offset:
        opt_offset = options.offset
        sign_factor = 1
        if options.offset.startswith("-"):
            opt_offset = options.offset[1:]
            sign_factor = -1
        try:
            offset += metomi.isodatetime.parsers.DurationParser().parse(
                opt_offset) * sign_factor
        except IsodatetimeError as exc:
            parser.error('ERROR: offset not valid: %s' % exc)
    cycle_point += offset
    if template is None:
        print(cycle_point)
    else:
        dump_string = iso_point_dumper.dump(cycle_point, template)
        if (dump_string == template and
                not any(_ in template for _ in ["CCYY", "MM", "DD", "%"])):
            # A pure time string, no date - not well handled in isodatetime.
            print(iso_point_dumper.dump(cycle_point, "T" + template)[1:])
        else:
            print(dump_string)
