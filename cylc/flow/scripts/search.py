#!/usr/bin/env python3

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

"""cylc search [OPTIONS] ARGS

Search for patterns in suite configurations.

Search for pattern matches in suite definitions and any files in the
suite bin directory. Matches are reported by line number and suite
section. An unquoted list of PATTERNs will be converted to an OR'd
pattern. Note that the order of command line arguments conforms to
normal cylc command usage (suite name first) not that of the grep
command.

Note that this command performs a text search on the suite definition,
it does not search the data structure that results from parsing the
suite definition - so it will not report implicit default settings.

For case insensitive matching use '(?i)PATTERN'."""

from collections import deque
import os
import re
import sys

from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.suite_files import parse_suite_arg
from cylc.flow.terminal import cli_function
from cylc.flow.parsec.include import inline


def section_level(heading):
    # e.g. foo => 0
    #     [foo] => 1
    #    [[foo]] => 2
    m = re.match(r'^(\[+)', heading)
    if m:
        level = len(m.groups()[0])
    else:
        level = 0
    return level


def print_heading(heading):
    print('>>>' + '->'.join(heading))


def get_option_parser():
    parser = COP(
        __doc__, prep=True,
        argdoc=[('SUITE', 'Suite name or path'),
                ('PATTERN', 'Python-style regular expression'),
                ('[PATTERN2...]', 'Additional search patterns')])

    parser.add_option(
        "-x", help="Do not search in the suite bin directory",
        action="store_false", default=True, dest="search_bin")

    return parser


@cli_function(get_option_parser)
def main(parser, options, reg, *patterns):
    suite, flow_file = parse_suite_arg(options, reg)

    # cylc search SUITE PATTERN
    pattern = '|'.join(patterns)

    suitedir = os.path.dirname(flow_file)

    if os.path.isfile(flow_file):
        h = open(flow_file, 'r')
        lines = h.readlines()
        h.close()
        lines = inline(lines, suitedir, flow_file, for_grep=True)
    else:
        parser.error(f"File not found: {flow_file}")

    sections = deque(['(top)'])

    line_count = 1
    inc_file = None
    in_include_file = False
    prev_section_key = None
    prev_file = None

    for line in lines:

        m = re.match(
            r'^#\+\+\+\+ START INLINED INCLUDE FILE ([\w/\.\-]+)', line)
        if m:
            inc_file = m.groups()[0]
            in_include_file = True
            inc_line_count = 0
            continue

        if not in_include_file:
            line_count += 1
        else:
            inc_line_count += 1
            m = re.match(
                r'^#\+\+\+\+ END INLINED INCLUDE FILE ' + inc_file, line)
            if m:
                in_include_file = False
                inc_file = None
                continue

        m = re.match(r'\s*(\[+\s*.+\s*\]+)', line)
        if m:
            # new section heading detected
            heading = m.groups()[0]
            level = section_level(heading)
            # unwind to the current section level
            while len(sections) > level - 1:
                sections.pop()
            sections.append(heading)
            continue

        if re.search(pattern, line):
            # Found a pattern match.

            # Print the file name
            if in_include_file:
                curr_file = os.path.join(suitedir, inc_file)
                line_no = inc_line_count
            else:
                curr_file = flow_file
                line_no = line_count

            if curr_file != prev_file:
                prev_file = curr_file
                print("\nFILE:", curr_file)

            # Print the nested section headings
            section_key = '->'.join(sections)
            if section_key != prev_section_key:
                prev_section_key = section_key
                print('   SECTION:', section_key)

            # Print the pattern match, with line number
            print('      (' + str(line_no) + '):', line.rstrip('\n'))

    if not options.search_bin:
        sys.exit(0)

    # search files in suite bin directory
    bin_ = os.path.join(suitedir, 'bin')
    if not os.path.isdir(bin_):
        print("\nSuite " + suite + " has no bin directory", file=sys.stderr)
        sys.exit(0)

    for name in os.listdir(bin_):
        if name.startswith('.'):
            # skip hidden dot-files
            # (e.g. vim editor temporary files)
            continue
        new_file = True
        try:
            h = open(os.path.join(bin_, name), 'r')
        except IOError as exc:
            # e.g. there's a sub-directory under bin; ignore it.
            print('Unable to open file ' + os.path.join(bin_, name),
                  file=sys.stderr)
            print(exc, file=sys.stderr)
            continue
        contents = h.readlines()
        h.close()

        count = 0
        for line in contents:
            line = line.rstrip('\n')
            count += 1
            if re.search(pattern, line):
                if new_file:
                    print('\nFILE:', os.path.join(bin_, name))
                    new_file = False
                print('   (' + str(count) + '): ' + line)


if __name__ == '__main__':
    main()
