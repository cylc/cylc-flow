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

View a processed workflow configuration.

Note:
  This is different to `cylc config` which displays the parsed
  configuration (as Cylc would see it).

View a read-only temporary copy of workflow NAME's flow.cylc file, in your
editor, after optional include-file inlining and Jinja2 preprocessing.

The edit process is spawned in the foreground as follows:
  $ <editor> flow.cylc
Where <editor> can be set in cylc global config.
"""

import os
import shlex
from subprocess import call
import sys
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING

from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.exceptions import CylcError
from cylc.flow.id_cli import parse_id
from cylc.flow.option_parsers import (
    WORKFLOW_ID_OR_PATH_ARG_DOC,
    CylcOptionParser as COP,
)
from cylc.flow.parsec.fileparse import read_and_proc
from cylc.flow.templatevars import load_template_vars
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
        "--gui", "-g", help="Force use of the configured GUI editor.",
        action="store_true", default=False, dest="geditor")

    parser.add_option(
        "--stdout", help="Print the workflow definition to stdout.",
        action="store_true", default=False, dest="stdout")

    return parser


@cli_function(get_option_parser)
def main(parser: COP, options: 'Values', workflow_id: str) -> None:
    workflow_id, _, flow_file = parse_id(
        workflow_id,
        src=True,
        constraint='workflows',
    )

    if options.geditor:
        editor = glbl_cfg().get(['editors', 'gui'])
    else:
        editor = glbl_cfg().get(['editors', 'terminal'])

    # read in the flow.cylc file
    viewcfg = {
        'mark': options.mark,
        'single': options.single,
        'label': options.label,
        'empy': options.empy or options.process,
        'jinja2': options.jinja2 or options.process,
        'contin': options.cat or options.process,
        'inline': (options.inline or options.jinja2 or options.empy
                   or options.process),
    }
    lines = read_and_proc(
        flow_file,
        load_template_vars(options.templatevars, options.templatevars_file),
        viewcfg=viewcfg)

    if options.stdout:
        for line in lines:
            print(line)
        sys.exit(0)

    # write to a temporary file
    viewfile = NamedTemporaryFile(
        suffix=".flow.cylc", prefix=workflow_id.replace('/', '_') + '.',
    )
    for line in lines:
        viewfile.write((line + '\n').encode())
    viewfile.seek(0, 0)

    # set the file to be read only
    os.chmod(viewfile.name, 0o400)

    # capture the temp file's mod time in case the user edits it
    # and overrides the readonly mode.
    modtime1 = os.stat(viewfile.name).st_mtime

    # in case editor has options, e.g. 'emacs -nw':
    command_list = shlex.split(editor)
    command_list.append(viewfile.name)
    command = ' '.join(command_list)
    # THIS BLOCKS UNTIL THE COMMAND COMPLETES
    retcode = call(command_list)  # nosec (editor command is user configurable)
    if retcode != 0:
        # the command returned non-zero exist status
        raise CylcError(f'{command} failed: {retcode}')

    # !!!VIEWING FINISHED!!!

    # Did the user edit the file
    modtime2 = os.stat(viewfile.name).st_mtime

    if modtime2 > modtime1:
        print(
            "\nWARNING: YOU HAVE EDITED A TEMPORARY READ-ONLY COPY "
            f"OF THE WORKFLOW:\n   {viewfile.name}\n",
            file=sys.stderr
        )
    # DONE
    viewfile.close()
