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

"""cylc diff [OPTIONS] SUITE1 SUITE2

Compare two suite configurations and display any differences.

Differencing is done after parsing the flow.cylc files so it takes
account of default values that are not explicitly defined, it disregards
the order of configuration items, and it sees any include-file content
after inlining has occurred.

Files in the suite bin directory and other sub-directories of the
suite definition directory are not currently differenced."""

import sys

from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.config import SuiteConfig
from cylc.flow.suite_files import parse_suite_arg
from cylc.flow.templatevars import load_template_vars
from cylc.flow.terminal import cli_function

n_oone = 0
n_otwo = 0
n_diff = 0


def diffdict(one, two, oone, otwo, diff):
    global n_oone, n_otwo, n_diff
    # Recursively difference two dictionaries in which any element
    # may be another dictionary, keeping items that appear only
    # in one or the other, and items that appear in both but differ.
    for key in one:
        if key not in two:
            oone[key] = one[key]
            n_oone += 1
        elif one[key] != two[key]:
            if isinstance(one[key], dict):
                for item in oone, otwo, diff:
                    if key not in item:
                        item[key] = {}
                diffdict(one[key], two[key], oone[key], otwo[key], diff[key])
            else:
                diff[key] = (one[key], two[key])
                n_diff += 1

    for key in two:
        if key not in one:
            otwo[key] = two[key]
            n_otwo += 1


def prdict(dct, arrow='<', section='', level=0, diff=False, nested=False):
    """Recursively print, in pseudo 'diff' format, the contents of
    one of the three dictionaries populated by the diffdict() function
    above (any element may itself be a dictionary).
    """

    if section != '':
        prfx = section + ' '
    else:
        prfx = ''

    if section == '':
        sctn = '(top)'
    else:
        sctn = section

    foo = False

    for key in dct:
        if isinstance(dct[key], dict):
            lvl = level + 1
            if nested:
                pre = prfx + '\n' + '   ' * lvl
            else:
                pre = prfx
            prdict(dct[key], arrow,
                   pre + '[' * lvl + str(key) + ']' * lvl, lvl,
                   diff, nested)
        else:
            if not foo:
                if nested:
                    print('  ', sctn)
                else:
                    print('\n  ', sctn)
                foo = True

            if diff:
                print(' <  ', key, '=', dct[key][0])
                print(' >  ', key, '=', dct[key][1])
            else:
                print(' ' + arrow + '  ', key, '=', dct[key])


def get_option_parser():
    parser = COP(
        __doc__, jset=True, prep=True, icp=True,
        argdoc=[('SUITE1', 'Suite name or path'),
                ('SUITE2', 'Suite name or path')])

    parser.add_option(
        "-n", "--nested",
        help="print flow.cylc section headings in nested form.",
        action="store_true", default=False, dest="nested")

    return parser


@cli_function(get_option_parser)
def main(parser, options, *args):
    suite1_name, suite1_config = parse_suite_arg(options, args[0])
    suite2_name, suite2_config = parse_suite_arg(options, args[1])
    if suite1_name == suite2_name:
        parser.error("You can't diff a single suite.")
    print(f"Parsing {suite1_name} ({suite1_config})")
    template_vars = load_template_vars(
        options.templatevars, options.templatevars_file)
    config1 = SuiteConfig(
        suite1_name, suite1_config, options, template_vars).cfg
    print(f"Parsing {suite2_name} ({suite2_config})")
    config2 = SuiteConfig(
        suite2_name, suite2_config, options, template_vars, is_reload=True).cfg

    if config1 == config2:
        print(f"Suite definitions {suite1_name} and {suite2_name} are "
              f"identical")
        sys.exit(0)

    print(f"Suite definitions {suite1_name} and {suite2_name} differ")

    suite1_only = {}
    suite2_only = {}
    diff_1_2 = {}

    diffdict(config1, config2, suite1_only, suite2_only, diff_1_2)

    if n_oone > 0:
        print(f'\n{n_oone} items only in {suite1_name} (<)')
        prdict(suite1_only, '<', nested=options.nested)

    if n_otwo > 0:
        print(f'\n{n_otwo} items only in {suite2_name} (>)')
        prdict(suite2_only, '>', nested=options.nested)

    if n_diff > 0:
        print(f'\n{n_diff} common items differ {suite1_name}(<) '
              f'{suite2_name}(>)')
        prdict(diff_1_2, '', diff=True, nested=options.nested)


if __name__ == "__main__":
    main()
