#!/usr/bin/env python3

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

"""cylc search [OPTIONS] ARGS

Search for patterns in workflow configurations.

Search for pattern matches in workflow definitions and any files in the
workflow bin directory. Matches are reported by line number and workflow
section. An unquoted list of PATTERNs will be converted to an OR'd
pattern. Note that the order of command line arguments conforms to
normal cylc command usage (workflow name first) not that of the grep
command.

Note that this command performs a text search on the workflow definition,
it does not search the data structure that results from parsing the
workflow definition - so it will not report implicit default settings.

For case insensitive matching use '(?i)PATTERN'."""

from collections import deque
import os
import re
import sys

from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.workflow_files import parse_reg
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
        argdoc=[('WORKFLOW', 'Workflow name or path'),
                ('PATTERN', 'Python-style regular expression'),
                ('[PATTERN2...]', 'Additional search patterns')])

    parser.add_option(
        "-x", help="Do not search in the workflow bin directory",
        action="store_false", default=True, dest="search_bin")

    return parser


@cli_function(get_option_parser)
def main(parser, options, reg, *patterns):
    workflow, flow_file = parse_reg(reg, src=True)

    # cylc search WORKFLOW PATTERN
    pattern = '|'.join(patterns)

    workflowdir = os.path.dirname(flow_file)

    if os.path.isfile(flow_file):
        with open(flow_file, 'r') as handle:
            lines = handle.readlines()
        lines = inline(lines, workflowdir, flow_file, for_grep=True)
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
                curr_file = os.path.join(workflowdir, inc_file)
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

    # search files in workflow bin directory
    bin_ = os.path.join(workflowdir, 'bin')
    if not os.path.isdir(bin_):
        print("\nWorkflow " + workflow + " has no bin directory",
              file=sys.stderr)
        sys.exit(0)

    for name in os.listdir(bin_):
        if name.startswith('.'):
            # skip hidden dot-files
            # (e.g. vim editor temporary files)
            continue
        new_file = True
        try:
            with open(os.path.join(bin_, name), 'r') as handle:
                contents = handle.readlines()
        except IOError as exc:
            # e.g. there's a sub-directory under bin; ignore it.
            print('Unable to open file ' + os.path.join(bin_, name),
                  file=sys.stderr)
            print(exc, file=sys.stderr)
            continue

        for count, line in enumerate(contents):
            line = line.rstrip('\n')
            if re.search(pattern, line):
                if new_file:
                    print('\nFILE:', os.path.join(bin_, name))
                    new_file = False
                print('   (' + str(count) + '): ' + line)


if __name__ == '__main__':
    main()
