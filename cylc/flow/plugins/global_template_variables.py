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

"""Plugin which loads global template variables.

This loads variables from ``global.cylc[install][template variables]``,
provisioning them for use in ``flow.cylc``.
"""

from typing import TYPE_CHECKING

from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.parsec.fileparse import TEMPLATE_VARIABLES


if TYPE_CHECKING:
    from pathlib import Path

    from cylc.flow.option_parsers import Values


def pre_configure(srcdir: 'Path', opts: 'Values') -> dict:
    return {
        TEMPLATE_VARIABLES: glbl_cfg().get(['install', 'template variables'])
    }
