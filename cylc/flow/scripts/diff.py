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

"""cylc diff [OPTIONS] ARGS

Compare two workflow configurations and display any differences.

Differencing is done after parsing the flow.cylc files so it takes
account of default values that are not explicitly defined, it disregards
the order of configuration items, and it sees any include-file content
after inlining has occurred.

Files in the workflow bin directory and other sub-directories of the
run directory are not currently differenced.
"""

import sys
from typing import TYPE_CHECKING

from cylc.flow.id_cli import parse_id
from cylc.flow.option_parsers import (
    WORKFLOW_ID_OR_PATH_ARG_DOC,
    CylcOptionParser as COP,
    icp_option,
)
from cylc.flow.config import WorkflowConfig
from cylc.flow.templatevars import get_template_vars
from cylc.flow.terminal import cli_function

if TYPE_CHECKING:
    from optparse import Values


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


def get_option_parser() -> COP:
    parser = COP(
        __doc__,
        jset=True,
        argdoc=[
            (f'WORKFLOW_{n}', WORKFLOW_ID_OR_PATH_ARG_DOC[1])
            for n in (1, 2)
        ]
    )

    parser.add_option(
        "-n", "--nested",
        help="print flow.cylc section headings in nested form.",
        action="store_true", default=False, dest="nested"
    )

    parser.add_option(icp_option)

    return parser


@cli_function(get_option_parser)
def main(parser: COP, options: 'Values', workflow_id1: str, workflow_id2: str):
    workflow_id_1, _, workflow_file_1_ = parse_id(
        workflow_id1,
        src=True,
        constraint='workflows',
    )
    workflow_id_2, _, workflow_file_2_ = parse_id(
        workflow_id2,
        src=True,
        constraint='workflows',
    )
    if workflow_file_1_ == workflow_file_2_:
        parser.error("You can't diff a single workflow.")
    print(f"Parsing {workflow_id_1} ({workflow_file_1_})")
    template_vars = get_template_vars(options)
    config1 = WorkflowConfig(
        workflow_id_1, workflow_file_1_, options, template_vars
    ).cfg
    print(f"Parsing {workflow_id_2} ({workflow_file_2_})")
    config2 = WorkflowConfig(
        workflow_id_2, workflow_file_2_, options, template_vars
    ).cfg

    if config1 == config2:
        print(
            f"Workflow definitions {workflow_id_1} and {workflow_id_2} are "
            f"identical"
        )
        sys.exit(0)

    print(f"Workflow definitions {workflow_id_1} and {workflow_id_2} differ")

    workflow1_only = {}  # type: ignore
    workflow2_only = {}  # type: ignore
    diff_1_2 = {}  # type: ignore
    # TODO: this whole file could do wih refactoring at some point

    diffdict(config1, config2, workflow1_only, workflow2_only, diff_1_2)

    if n_oone > 0:
        print(f'\n{n_oone} items only in {workflow_id_1} (<)')
        prdict(workflow1_only, '<', nested=options.nested)

    if n_otwo > 0:
        print(f'\n{n_otwo} items only in {workflow_id_2} (>)')
        prdict(workflow2_only, '>', nested=options.nested)

    if n_diff > 0:
        print(f'\n{n_diff} common items differ {workflow_id_1}(<) '
              f'{workflow_id_2}(>)')
        prdict(diff_1_2, '', diff=True, nested=options.nested)
