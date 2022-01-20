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

from pathlib import Path

import pytest

from cylc.flow.exceptions import (
    CylcError,
    ServiceFileError,
)
from cylc.flow.workflow_files import (
    ContactFileFields as CFF,
    WorkflowFiles,
    detect_old_contact_file,
    dump_contact_file,
    load_contact_file,
    load_contact_file_async,
)


@pytest.fixture(scope='module')
async def myflow(mod_flow, mod_scheduler, mod_run, mod_one_conf):
    reg = mod_flow(mod_one_conf)
    schd = mod_scheduler(reg)
    async with mod_run(schd):
        yield schd


def test_load_contact_file(myflow):
    cont = load_contact_file(myflow.workflow)
    assert cont[CFF.HOST] == myflow.host


@pytest.mark.asyncio
async def test_load_contact_file_async(myflow):
    cont = await load_contact_file_async(myflow.workflow)
    assert cont[CFF.HOST] == myflow.host

    # compare the async interface to the sync interface
    cont2 = load_contact_file(myflow.workflow)
    assert cont == cont2


@pytest.mark.asyncio
@pytest.fixture
async def workflow(flow, scheduler, one_conf, run_dir):
    reg = flow(one_conf)
    schd = scheduler(reg)
    await schd.install()

    from collections import namedtuple
    Server = namedtuple('Server', ['port'])
    schd.server = Server(1234)
    schd.publisher = Server(2345)

    contact_data = schd.get_contact_data()
    contact_file = Path(
        run_dir,
        reg,
        WorkflowFiles.Service.DIRNAME,
        WorkflowFiles.Service.CONTACT
    )

    def dump_contact(**kwargs):
        nonlocal contact_data, reg
        dump_contact_file(
            reg,
            {
                **contact_data,
                **kwargs
            }
        )
        assert contact_file.exists()

    dump_contact()

    Fixture = namedtuple(
        'TextFixture',
        [
            'reg',
            'contact_file',
            'contact_data',
            'dump_contact',
        ]
    )
    return Fixture(reg, contact_file, contact_data, dump_contact)


def test_detect_old_contact_file_running(workflow):
    """It should raise an error if the workflow is running."""
    # the workflow is running so we should get a ServiceFileError
    with pytest.raises(ServiceFileError):
        detect_old_contact_file(workflow.reg)
    # the contact file is valid so should be left alone
    assert workflow.contact_file.exists()


def test_detect_old_contact_file_network_issue(workflow):
    """It should raise an error if there are network issues."""
    # modify the contact file to make it look like the PID has changed
    workflow.dump_contact(
        **{
            # set the HOST to a non existent host
            CFF.HOST: 'not-a-host.no-such.domain'
        }
    )
    # detect_old_contact_file should report that it can't tell if the workflow
    # is running or not
    with pytest.raises(CylcError) as exc_ctx:
        detect_old_contact_file(workflow.reg)
    assert (
        'Cannot determine whether workflow is running'
        in str(exc_ctx.value)
    )
    # the contact file should be left alone
    assert workflow.contact_file.exists()


def test_detect_old_contact_file_old_run(workflow):
    """It should remove the contact file from an old run."""
    # modify the contact file to make it look like the COMMAND has changed
    workflow.dump_contact(
        **{
            CFF.COMMAND: 'foo bar baz'
        }
    )
    # the workflow should not appear to be running (according to the contact
    # data) so detect_old_contact_file should not raise any errors
    detect_old_contact_file(workflow.reg)
    # as a side effect the contact file should have been removed
    assert not workflow.contact_file.exists()


def test_detect_old_contact_file_none(workflow):
    """It should do nothing if there is no contact file."""
    # remove the contact file
    workflow.contact_file.unlink()
    assert not workflow.contact_file.exists()
    # detect_old_contact_file should return
    detect_old_contact_file(workflow.reg)
    # it should not recreate the contact file
    assert not workflow.contact_file.exists()
