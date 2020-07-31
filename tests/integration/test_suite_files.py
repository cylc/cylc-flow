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

import pytest

from cylc.flow.suite_files import (
    ContactFileFields as CFF,
    load_contact_file,
    load_contact_file_async
)


@pytest.fixture(scope='module')
async def myflow(mod_flow, mod_scheduler, mod_run, mod_one_conf):
    reg = mod_flow(mod_one_conf)
    schd = mod_scheduler(reg)
    async with mod_run(schd):
        yield schd


def test_load_contact_file(myflow):
    cont = load_contact_file(myflow.suite)
    assert cont[CFF.HOST] == myflow.host


@pytest.mark.asyncio
async def test_load_contact_file_async(myflow):
    cont = await load_contact_file_async(myflow.suite)
    assert cont[CFF.HOST] == myflow.host

    # compare the async interface to the sync interface
    cont2 = load_contact_file(myflow.suite)
    assert cont == cont2
