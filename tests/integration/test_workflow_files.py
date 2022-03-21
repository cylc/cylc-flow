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

from itertools import product
import logging
from pathlib import Path

import pytest

from cylc.flow import CYLC_LOG
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


async def test_load_contact_file_async(myflow):
    cont = await load_contact_file_async(myflow.workflow)
    assert cont[CFF.HOST] == myflow.host

    # compare the async interface to the sync interface
    cont2 = load_contact_file(myflow.workflow)
    assert cont == cont2


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


def test_detect_old_contact_file_old_run(workflow, caplog, log_filter):
    """It should remove the contact file from an old run."""
    # modify the contact file to make it look like the COMMAND has changed
    workflow.dump_contact(
        **{
            CFF.COMMAND: 'foo bar baz'
        }
    )
    caplog.set_level(logging.INFO, logger=CYLC_LOG)

    # the workflow should not appear to be running (according to the contact
    # data) so detect_old_contact_file should not raise any errors
    detect_old_contact_file(workflow.reg)

    # as a side effect the contact file should have been removed
    assert not workflow.contact_file.exists()
    assert log_filter(caplog, contains='Removed contact file')


def test_detect_old_contact_file_none(workflow):
    """It should do nothing if there is no contact file."""
    # remove the contact file
    workflow.contact_file.unlink()
    assert not workflow.contact_file.exists()
    # detect_old_contact_file should return

    detect_old_contact_file(workflow.reg)

    # it should not recreate the contact file
    assert not workflow.contact_file.exists()


@pytest.mark.parametrize(
    'process_running,contact_present_after,raises_error',
    filter(
        lambda x: x != (False, False, True),  # logically impossible
        product([True, False], repeat=3),
    )
)
def test_detect_old_contact_file_removal_errors(
    workflow,
    monkeypatch,
    caplog,
    log_filter,
    process_running,
    contact_present_after,
    raises_error,
):
    """Test issues with removing the contact file are handled correctly.

    Args:
        process_running:
            If True we will make it look like the workflow process is still
            running (i.e. the workflow is still running). In this case
            detect_old_contact_file should *not* attempt to remove the contact
            file.
        contact_present_after:
            If False we will make the contact file disappear midway through
            the operation. This can happen because:

            * detect_old_contact_file in another client.
            * cylc clean.
            * Aliens.

            This is fine, nothing should be logged.
        raises_error:
            If True we will make it look like removing the contact file
            resulted in an OS error (not a FileNotFoundError). This error
            should be logged.

    """
    # patch the is_process_running method
    def _is_process_running(*args):
        nonlocal workflow
        nonlocal process_running
        if not contact_present_after:
            # remove the contact file midway through detect_old_contact_file
            workflow.contact_file.unlink()
        return process_running

    monkeypatch.setattr(
        'cylc.flow.workflow_files._is_process_running',
        _is_process_running,
    )

    # patch the contact file removal
    def _unlink(*args):
        raise OSError('mocked-os-error')

    if raises_error:
        # force os.unlink to raise an arbitrary error
        monkeypatch.setattr(
            'cylc.flow.workflow_files.os.unlink',
            _unlink,
        )

    caplog.set_level(logging.INFO, logger=CYLC_LOG)

    # try to remove the contact file
    if process_running:
        # this should error if the process is running
        with pytest.raises(ServiceFileError):
            detect_old_contact_file(workflow.reg)
    else:
        detect_old_contact_file(workflow.reg)

    # decide which log messages we should expect to see
    if process_running:
        remove_succeeded = False
        remove_failed = False
    else:
        if contact_present_after:
            if raises_error:
                remove_succeeded = False
                remove_failed = True
            else:
                remove_succeeded = True
                remove_failed = False
        else:
            remove_succeeded = False
            remove_failed = False

    # check the appropriate messages were logged
    assert bool(log_filter(
        caplog,
        contains='Removed contact file',
    )) is remove_succeeded
    assert bool(log_filter(
        caplog,
        contains=(
            f'Failed to remove contact file for {workflow.reg}:'
            '\nmocked-os-error'
        ),
    )) is remove_failed
