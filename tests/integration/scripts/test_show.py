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

import json
import pytest
from types import SimpleNamespace

from colorama import init as colour_init

from cylc.flow.id import Tokens
from cylc.flow.scripts.show import (
    show,
)


@pytest.fixture(scope='module')
def mod_my_conf():
    """A workflow configuration with some workflow metadata."""
    return {
        'meta': {
            'title': 'Workflow Title',
            'description': """
                My
                multiline
                description.
            """,
            'URL': 'http://ismycomputerturnedon.com/',
            'answer': '42',
        },
        'scheduling': {
            'graph': {
                'R1': 'foo'
            }
        },
        'runtime': {
            'foo': {
                'meta': {
                    'title': 'Task Title',
                    'description': '''
                        Task
                        multiline
                        description
                    ''',
                    'URL': (
                        'http://hasthelargehadroncollider'
                        'destroyedtheworldyet.com/'
                    ),
                    'question': 'mutually exclusive',
                }
            }
        },
    }


@pytest.fixture(scope='module')
async def mod_my_schd(mod_flow, mod_scheduler, mod_start, mod_my_conf):
    """A "started" workflow."""
    id_ = mod_flow(mod_my_conf)
    schd = mod_scheduler(id_)
    async with mod_start(schd):
        yield schd


async def test_workflow_meta_query(mod_my_schd, capsys):
    """It should fetch workflow metadata."""
    colour_init(strip=True, autoreset=True)
    opts = SimpleNamespace(
        comms_timeout=5,
        json=False,
        list_prereqs=False,
        task_defs=None,
    )

    # plain output
    ret = await show(mod_my_schd.workflow, [], opts)
    assert ret == 0
    out, err = capsys.readouterr()
    assert out.splitlines() == [
        'title: Workflow Title',
        'description: My',
        'multiline',
        'description.',
        'answer: 42',
        'URL: http://ismycomputerturnedon.com/',
    ]

    # json output
    opts.json = True
    ret = await show(mod_my_schd.workflow, [], opts)
    assert ret == 0
    out, err = capsys.readouterr()
    assert json.loads(out) == {
        'title': 'Workflow Title',
        'description': 'My\nmultiline\ndescription.',
        'answer': '42',
        'URL': 'http://ismycomputerturnedon.com/',
    }


async def test_task_meta_query(mod_my_schd, capsys):
    """It should fetch task metadata."""
    colour_init(strip=True, autoreset=True)
    opts = SimpleNamespace(
        comms_timeout=5,
        json=False,
        list_prereqs=False,
        task_defs=['foo'],
    )

    # plain output
    ret = await show(
        mod_my_schd.workflow,
        # [Tokens(cycle='1', task='foo')],
        None,
        opts,
    )
    assert ret == 0
    out, err = capsys.readouterr()
    assert out.splitlines() == [
        'title: Task Title',
        'question: mutually exclusive',
        'description: Task',
        'multiline',
        'description',
        'URL: http://hasthelargehadroncolliderdestroyedtheworldyet.com/',
    ]

    # json output
    opts.json = True
    ret = await show(mod_my_schd.workflow, [], opts)
    assert ret == 0
    out, err = capsys.readouterr()
    assert json.loads(out) == {
        'foo': {
            'title': 'Task Title',
            'question': 'mutually exclusive',
            'description': 'Task\nmultiline\ndescription',
            'URL': 'http://hasthelargehadroncolliderdestroyedtheworldyet.com/',
        }
    }
