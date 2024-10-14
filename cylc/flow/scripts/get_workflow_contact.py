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

"""cylc get-workflow-contact [OPTIONS] ARGS

Print contact information of a running workflow.
"""

from typing import TYPE_CHECKING

from cylc.flow.exceptions import CylcError, ServiceFileError
from cylc.flow.id_cli import parse_id
from cylc.flow.option_parsers import (
    WORKFLOW_ID_ARG_DOC,
    CylcOptionParser as COP,
)
from cylc.flow.workflow_files import load_contact_file
from cylc.flow.terminal import cli_function

if TYPE_CHECKING:
    from optparse import Values


def get_option_parser():
    return COP(__doc__, argdoc=[WORKFLOW_ID_ARG_DOC])


@cli_function(get_option_parser)
def main(parser: COP, options: 'Values', workflow_id: str) -> None:
    """CLI for "cylc get-workflow-contact"."""
    workflow_id, *_ = parse_id(
        workflow_id,
        constraint='workflows',
    )
    try:
        data = load_contact_file(workflow_id)
    except ServiceFileError as exc:
        raise CylcError(
            f"{workflow_id}: cannot get contact info, workflow not running?"
        ) from exc
    else:
        for key, value in sorted(data.items()):
            print("%s=%s" % (key, value))
