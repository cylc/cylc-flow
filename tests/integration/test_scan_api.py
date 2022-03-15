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
"""Test the cylc scan Python API (which is equivalent to the CLI)."""

import json
from pathlib import Path
from shutil import (
    copytree,
    rmtree
)

import pytest

from cylc.flow.scripts.scan import (
    main,
    ScanOptions
)
from cylc.flow.workflow_files import (
    ContactFileFields,
    WorkflowFiles,
    dump_contact_file,
    load_contact_file
)


@pytest.fixture(scope='module')
async def flows(mod_flow, mod_scheduler, mod_run, mod_one_conf):
    """Three workflows in different states.

    One stopped, one paused and one that thinks its running.

    TODO:
        Start one of the workflows with tasks in funny states
        in order to test the state totals functionality properly.

        Requires: https://github.com/cylc/cylc-flow/pull/3668

    """
    # a simple workflow we will leave stopped
    mod_flow(mod_one_conf, name='-stopped-')

    # a simply hierarchically registered workflow we will leave stopped
    mod_flow(mod_one_conf, name='a/b/c')

    # a simple workflow we will leave paused
    reg1 = mod_flow(mod_one_conf, name='-paused-')
    schd1 = mod_scheduler(reg1, paused_start=True)

    # a workflow with some metadata we will make look like it's running
    reg2 = mod_flow(
        {
            'meta': {
                'title': 'Foo',
                'description': '''
                    Here we find a
                    multi
                    line
                    description
                '''
            },
            'scheduler': {
                'allow implicit tasks': True
            },
            'scheduling': {
                'graph': {
                    'R1': 'foo'
                }
            },
            'runtime': {
                'one': {
                    'execution time limit': 'PT10S'
                }
            }
        },
        name='-running-'
    )
    schd2 = mod_scheduler(reg2, run_mode='simulation', paused_start=False)

    # run cylc run
    async with mod_run(schd1):
        async with mod_run(schd2):
            yield


async def test_state_filter(flows, mod_test_dir):
    """It should filter flows by state."""
    # one stopped flow
    opts = ScanOptions(states='stopped', sort=True)
    lines = []
    await main(opts, write=lines.append, scan_dir=mod_test_dir)
    assert len(lines) == 2
    assert '-stopped-' in lines[0]
    assert 'a/b/c' in lines[1]

    # one paused flow
    opts = ScanOptions(states='paused')
    lines = []
    await main(opts, write=lines.append, scan_dir=mod_test_dir)
    assert len(lines) == 1
    assert '-paused-' in lines[0]

    # one running flow
    opts = ScanOptions(states='running')
    lines = []
    await main(opts, write=lines.append, scan_dir=mod_test_dir)
    assert len(lines) == 1
    assert '-running-' in lines[0]

    # two active flows
    opts = ScanOptions(states='paused,running')
    lines = []
    await main(opts, write=lines.append, scan_dir=mod_test_dir)
    assert len(lines) == 2

    # three registered flows
    opts = ScanOptions(states='paused,running,stopped')
    lines = []
    await main(opts, write=lines.append, scan_dir=mod_test_dir)
    assert len(lines) == 4


async def test_name_filter(flows, mod_test_dir):
    """It should filter flows by name regex."""
    # one stopped flow
    opts = ScanOptions(states='all', name=['.*paused.*'])
    lines = []
    await main(opts, write=lines.append, scan_dir=mod_test_dir)
    assert len(lines) == 1
    assert '-paused-' in lines[0]


async def test_name_sort(flows, mod_test_dir):
    """It should sort flows by name."""
    # one stopped flow
    opts = ScanOptions(states='all', sort=True)
    lines = []
    await main(opts, write=lines.append, scan_dir=mod_test_dir)
    assert len(lines) == 4
    assert '-paused-' in lines[0]
    assert '-running-' in lines[1]
    assert '-stopped-' in lines[2]
    assert 'a/b/c' in lines[3]


async def test_format_json(flows, mod_test_dir):
    """It should dump results in json format."""
    # one stopped flow
    opts = ScanOptions(states='all', format='json')
    lines = []
    await main(opts, write=lines.append, scan_dir=mod_test_dir)
    data = json.loads(lines[0])
    assert len(data) == 4
    assert data[0]['name']


async def test_format_tree(flows, run_dir, ses_test_dir, mod_test_dir):
    """It should dump results in an ascii tree format."""
    # one stopped flow
    opts = ScanOptions(states='running', format='tree')
    workflows = []
    await main(opts, write=workflows.append, scan_dir=mod_test_dir)
    assert len(workflows) == 1
    lines = workflows[0].splitlines()
    # this flow is hierarchically registered in the run dir already
    # it should be registered as <session test dir>/<module test dir>/<name>
    assert ses_test_dir.name in lines[0]
    assert mod_test_dir.name in lines[1]
    assert '-running-' in lines[2]


async def test_format_rich(flows, mod_test_dir):
    """It should print results in a long human-friendly format."""
    # one stopped flow (--colour-blind)
    opts = ScanOptions(states='running', format='rich', colour_blind=True)
    workflows = []
    await main(opts, write=workflows.append, scan_dir=mod_test_dir)
    assert len(workflows) == 1
    lines = workflows[0].splitlines()

    # test that the multi-line description was output correctly
    # with trailing lines indented correctly
    desc_lines = [
        'Here we find a',
        'multi',
        'line',
        'description'
    ]
    prev_ind = -1
    prev_offset = -1
    for expected in desc_lines:
        for ind, line in enumerate(lines):
            if expected in line:
                offset = line.index(expected)
                if prev_ind < 1:
                    prev_ind = ind
                    prev_offset = offset
                else:
                    if ind != prev_ind + 1:
                        raise Exception(
                            f'Lines found in wrong order: {line}')
                    if offset != prev_offset:
                        raise Exception('Line incorrectly indented: {line}')
            break
        else:
            raise Exception(f'Missing line: {line}')

    # test that the state totals show one task running (colour_blind mode)
    for line in lines:
        if 'running:1' in line:
            break
    else:
        raise Exception('missing state totals line (colour_blind)')

    # one stopped flow (--colour=always)
    opts = ScanOptions(states='running', format='rich')
    workflows = []
    await main(
        opts, write=workflows.append, scan_dir=mod_test_dir, color='always'
    )
    assert len(workflows) == 1
    lines = workflows[0].splitlines()

    # test that the state totals show one task running (colour mode)
    for line in lines:
        if '1 ■' in line:
            break
    else:
        raise Exception('missing state totals line (colourful)')


async def test_scan_cleans_stuck_contact_files(
    start,
    scheduler,
    flow,
    one_conf,
    run_dir,
    test_dir,
):
    """Ensure scan tidies up contact files from crashed flows."""
    # create a flow
    reg = flow(one_conf, name='-crashed-')
    schd = scheduler(reg)
    srv_dir = Path(run_dir, reg, WorkflowFiles.Service.DIRNAME)
    tmp_dir = test_dir / 'srv'
    cont = srv_dir / WorkflowFiles.Service.CONTACT

    # run the flow, copy the contact, stop the flow, copy back the contact
    async with start(schd):
        copytree(srv_dir, tmp_dir)
    rmtree(srv_dir)
    copytree(tmp_dir, srv_dir)
    rmtree(tmp_dir)

    # the old contact file check uses the CLI command that the flow was run
    # with to check that whether the flow is running. Because this is an
    # integration test the process is the pytest process and it is still
    # running so we need to change the command so that Cylc sees the flow as
    # having crashed
    contact_info = load_contact_file(reg)
    contact_info[ContactFileFields.COMMAND] += 'xyz'
    dump_contact_file(reg, contact_info)

    # make sure this flow shows for a regular filesystem-only scan
    opts = ScanOptions(states='running,paused', format='name')
    flows = []
    await main(opts, write=flows.append, scan_dir=test_dir)
    assert len(flows) == 1
    assert '-crashed-' in flows[0]

    # the contact file should still be there
    assert cont.exists()

    # make sure this flow shows for a regular filesystem-only scan
    opts = ScanOptions(states='running,paused', format='name', ping=True)
    flows = []
    await main(opts, write=flows.append, scan_dir=test_dir)
    assert len(flows) == 0

    # the contact file should have been removed by the scan
    assert not cont.exists()
