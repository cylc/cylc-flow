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
from os import unlink
from pathlib import Path
from textwrap import dedent
from uuid import uuid4

import pytest

from cylc.flow import CYLC_LOG
from cylc.flow.exceptions import (
    ContactFileExists,
    CylcError,
)
from cylc.flow.workflow_files import (
    ContactFileFields as CFF,
    WorkflowFiles,
    _is_process_running,
    detect_old_contact_file,
    dump_contact_file,
    load_contact_file,
    load_contact_file_async,
)


@pytest.fixture(scope='module')
async def myflow(mod_flow, mod_scheduler, mod_run, mod_one_conf):
    id_ = mod_flow(mod_one_conf)
    schd = mod_scheduler(id_)
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
    id_ = flow(one_conf)
    schd = scheduler(id_)
    await schd.install()

    from collections import namedtuple
    Server = namedtuple('Server', ['port', 'pub_port'])
    schd.server = Server(1234, pub_port=2345)
    schd.uuid_str = str(uuid4())

    contact_data = schd.get_contact_data()
    contact_file = Path(
        run_dir,
        id_,
        WorkflowFiles.Service.DIRNAME,
        WorkflowFiles.Service.CONTACT
    )

    def dump_contact(**kwargs):
        dump_contact_file(
            id_,
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
            'id_',
            'contact_file',
            'contact_data',
            'dump_contact',
        ]
    )
    return Fixture(id_, contact_file, contact_data, dump_contact)


def test_detect_old_contact_file_running(workflow):
    """It should raise an error if the workflow is running."""
    # the workflow is running so we should get a ServiceFileError
    with pytest.raises(ContactFileExists):
        detect_old_contact_file(workflow.id_)
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
        detect_old_contact_file(workflow.id_)
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
    detect_old_contact_file(workflow.id_)

    # as a side effect the contact file should have been removed
    assert not workflow.contact_file.exists()
    assert log_filter(contains='Removed contact file')


def test_detect_old_contact_file_none(workflow):
    """It should do nothing if there is no contact file."""
    # remove the contact file
    workflow.contact_file.unlink()
    assert not workflow.contact_file.exists()
    # detect_old_contact_file should return

    detect_old_contact_file(workflow.id_)

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
    def mocked_is_process_running(*args):
        if not contact_present_after:
            # remove the contact file midway through detect_old_contact_file
            unlink(workflow.contact_file)

        return process_running

    monkeypatch.setattr(
        'cylc.flow.workflow_files._is_process_running',
        mocked_is_process_running,
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
        with pytest.raises(ContactFileExists):
            detect_old_contact_file(workflow.id_)
    else:
        detect_old_contact_file(workflow.id_)

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
        contains='Removed contact file',
    )) is remove_succeeded
    assert bool(log_filter(
        contains=(
            f'Failed to remove contact file for {workflow.id_}:'
            '\nmocked-os-error'
        ),
    )) is remove_failed


def test_is_process_running_dirty_output(monkeypatch, caplog):
    """Ensure _is_process_running can handle polluted output.

    E.G. this can happen if there is an echo statement in the `.bashrc`.
    """

    stdout = None

    class Popen():

        def __init__(self, *args, **kwargs):
            self.returncode = 0

        def communicate(self, *args, **kwargs):
            return (stdout, '')

    monkeypatch.setattr(
        'cylc.flow.workflow_files.Popen',
        Popen,
    )

    # respond with something Cylc should be able to make sense of
    stdout = dedent('''
        % simulated stdout pollution %
        [["expected", "command"]]
    ''')

    caplog.set_level(logging.WARN, logger=CYLC_LOG)
    assert _is_process_running('localhost', 1, 'expected command')
    assert not caplog.record_tuples
    assert not _is_process_running('localhost', 1, 'slartibartfast')
    assert not caplog.record_tuples

    # respond with something totally non-sensical
    stdout = 'sir henry'
    with pytest.raises(CylcError):
        _is_process_running('localhost', 1, 'expected command')

    # the command output should be in the debug message
    assert 'sir henry' in caplog.records[0].message
