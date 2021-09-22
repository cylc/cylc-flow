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

Print contact information of a running workflow."""

from typing import TYPE_CHECKING

from cylc.flow.exceptions import CylcError, ServiceFileError
from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.workflow_files import load_contact_file, parse_reg
from cylc.flow.terminal import cli_function

if TYPE_CHECKING:
    from optparse import Values


def get_option_parser():
    return COP(__doc__, argdoc=[('REG', 'Workflow name')])


@cli_function(get_option_parser)
def main(parser: COP, options: 'Values', reg: str) -> None:
    """CLI for "cylc get-workflow-contact"."""
    reg, _ = parse_reg(reg)
    try:
        data = load_contact_file(reg)
    except ServiceFileError:
        raise CylcError(
            f"{reg}: cannot get contact info, workflow not running?"
        )
    else:
        for key, value in sorted(data.items()):
            print("%s=%s" % (key, value))


if __name__ == "__main__":
    main()
