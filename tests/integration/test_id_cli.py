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

"""Some integration tests running on live workflows to test filtering properly.
"""

import pytest_asyncio

from cylc.flow.pathutil import get_cylc_run_dir
from cylc.flow.id_cli import parse_ids_async


@pytest_asyncio.fixture(scope='module')
async def harness(
    mod_run,
    mod_scheduler,
    mod_flow,
    mod_one_conf,
    mod_test_dir,
):
    """Create three workflows, two running, one stopped."""
    reg_prefix = mod_test_dir.relative_to(get_cylc_run_dir())
    # abc:running
    reg1 = mod_flow(mod_one_conf, name='abc')
    schd1 = mod_scheduler(reg1)
    # def:running
    reg2 = mod_flow(mod_one_conf, name='def')
    schd2 = mod_scheduler(reg2)
    # ghi:stopped
    reg3 = mod_flow(mod_one_conf, name='ghi')
    async with mod_run(schd1):
        async with mod_run(schd2):
            yield reg_prefix, reg1, reg2, reg3


async def test_glob_wildcard(harness):
    """It should search for workflows using globs."""
    reg_prefix, reg1, reg2, reg3 = harness
    # '*' should return all workflows
    workflows, _ = await parse_ids_async(
        f'{reg_prefix / "*"}',
        constraint='workflows',
        match_workflows=True,
    )
    assert sorted(workflows) == sorted([reg1, reg2])
    workflows, _ = await parse_ids_async(
        f'{reg_prefix / "z*"}',
        constraint='workflows',
        match_workflows=True,
    )
    assert sorted(workflows) == sorted([])


async def test_glob_pattern(harness):
    """It should support fnmatch syntax including square brackets."""
    # [a]* should match workflows starting with "a"
    reg_prefix, reg1, reg2, reg3 = harness
    workflows, _ = await parse_ids_async(
        f'{reg_prefix / "[a]*"}',
        constraint='workflows',
        match_workflows=True,
    )
    assert sorted(workflows) == sorted([reg1])
    workflows, _ = await parse_ids_async(
        f'{reg_prefix / "[z]*"}',
        constraint='workflows',
        match_workflows=True,
    )
    assert sorted(workflows) == sorted([])


async def test_state_filter(harness):
    """It should filter by workflow state."""
    reg_prefix, reg1, reg2, reg3 = harness
    # '*' should return all workflows
    workflows, _ = await parse_ids_async(
        f'{reg_prefix / "*"}',
        constraint='workflows',
        match_workflows=True,
        match_active=None,
    )
    assert sorted(workflows) == sorted([reg1, reg2, reg3])
    workflows, _ = await parse_ids_async(
        f'{reg_prefix / "*"}',
        constraint='workflows',
        match_workflows=True,
        match_active=True,
    )
    assert sorted(workflows) == sorted([reg1, reg2])
    workflows, _ = await parse_ids_async(
        f'{reg_prefix / "*"}',
        constraint='workflows',
        match_workflows=True,
        match_active=False,
    )
    assert sorted(workflows) == sorted([reg3])
