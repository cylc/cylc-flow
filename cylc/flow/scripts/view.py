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

"""cylc view [OPTIONS] ARGS

Print a processed workflow configuration.

Print workflow configurations as processed before full parsing by Cylc. This
includes Jinja2 or Empy template processing, and inlining of include-files.
Some explanatory markup may also be requested.

Warning:
  This command will fail if `CYLC_` template variables are referenced
  without default values, because they are only defined for full parsing.
  E.g. (Jinja2): `{{CYLC_WORKFLOW_ID | default("not defined")}}`.

See also `cylc config`, which displays the fully parsed configuration.

"""

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

from cylc.flow.id_cli import parse_id_async
from cylc.flow.option_parsers import (
    AGAINST_SOURCE_OPTION,
    WORKFLOW_ID_OR_PATH_ARG_DOC,
    CylcOptionParser as COP,
)
from cylc.flow.pathutil import get_workflow_run_dir
from cylc.flow.parsec.fileparse import read_and_proc
from cylc.flow.templatevars import get_template_vars
from cylc.flow.terminal import cli_function

if TYPE_CHECKING:
    from optparse import Values


def get_option_parser():
    parser = COP(
        __doc__,
        jset=True,
        argdoc=[WORKFLOW_ID_OR_PATH_ARG_DOC],
    )

    parser.add_option(
        "--inline", "-i", help="Inline include-files.", action="store_true",
        default=False, dest="inline")

    parser.add_option(
        "--empy", "-e",
        help="View after EmPy template processing "
             "(implies '-i/--inline' as well).",
        action="store_true", default=False, dest="empy")

    parser.add_option(
        "--jinja2", "-j",
        help="View after Jinja2 template processing "
             "(implies '-i/--inline' as well).",
        action="store_true", default=False, dest="jinja2")

    parser.add_option(
        "-p", "--process",
        help="View after all processing (EmPy, Jinja2, inlining, "
             "line-continuation joining).",
        action="store_true", default=False, dest="process")

    parser.add_option(
        "--mark", "-m",
        help="(With '-i') Mark inclusions in the left margin.",
        action="store_true", default=False, dest="mark")

    parser.add_option(
        "--label", "-l",
        help="(With '-i') Label file inclusions with the file name. Line "
             "numbers will not correspond to those reported by the parser.",
        action="store_true", default=False, dest="label")

    parser.add_option(
        "--single",
        help="(With '-i') Inline only the first instances of any "
             "multiply-included files. Line numbers will not correspond to "
             "those reported by the parser.",
        action="store_true", default=False, dest="single")

    parser.add_option(
        "--cat", "-c",
        help="Concatenate continuation lines (line numbers will "
             "not correspond to those reported by the parser).",
             action="store_true", default=False, dest="cat")

    parser.add_option(
        *AGAINST_SOURCE_OPTION.args, **AGAINST_SOURCE_OPTION.kwargs)

    parser.add_cylc_rose_options()

    return parser


@cli_function(get_option_parser)
def main(parser: COP, options: 'Values', workflow_id: str) -> None:
    asyncio.run(_main(options, workflow_id))


async def _main(options: 'Values', workflow_id: str) -> None:
    workflow_id, _, flow_file = await parse_id_async(
        workflow_id,
        src=True,
        constraint='workflows',
    )

    # Save the location of the existing workflow run dir in the
    # against source option:
    if options.against_source:
        options.against_source = Path(get_workflow_run_dir(workflow_id))

    # read in the flow.cylc file
    for line in read_and_proc(
        flow_file,
        get_template_vars(options),
        viewcfg={
            'mark': options.mark,
            'single': options.single,
            'label': options.label,
            'empy': options.empy or options.process,
            'jinja2': options.jinja2 or options.process,
            'contin': options.cat or options.process,
            'inline': (
                options.jinja2 or options.empy or
                options.inline or options.process
            ),
        },
        opts=options,
    ):
        print(line)
