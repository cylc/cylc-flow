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

from cylc.flow.dbstatecheck import check_polling_config
from cylc.flow.exceptions import InputError

import pytest


def test_check_polling_config():
    """It should reject invalid or unreliable polling configurations.

    See https://github.com/cylc/cylc-flow/issues/6157
    """
    # invalid polling use cases
    with pytest.raises(InputError, match='No such task state'):
        check_polling_config('elephant', False, False)

    with pytest.raises(InputError, match='Cannot poll for'):
        check_polling_config('waiting', False, False)

    with pytest.raises(InputError, match='is not reliable'):
        check_polling_config('running', False, False)

    # valid polling use cases
    check_polling_config('started', True, False)
    check_polling_config('started', False, True)

    # valid query use cases
    check_polling_config(None, False, True)
    check_polling_config(None, False, False)
