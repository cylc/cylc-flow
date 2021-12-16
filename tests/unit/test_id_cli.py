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

import os
from pathlib import Path
import pytest

from cylc.flow.exceptions import UserInputError
from cylc.flow.id import detokenise
from cylc.flow.id_cli import parse_ids_async


@pytest.fixture(scope='module')
def abc_src_dir(tmp_path_factory):
    cwd_before = Path.cwd()
    tmp_path = tmp_path_factory.getbasetemp()
    os.chdir(tmp_path)
    for name in ('a', 'b', 'c'):
        Path(tmp_path, name).mkdir()
        Path(tmp_path, name, 'flow.cylc').touch()  # TODO: const
    yield tmp_path
    os.chdir(cwd_before)


@pytest.mark.parametrize(
    'ids_in,ids_out',
    [
        (('a//',), ['a']),
        (('a//', 'a//'), ['a']),
        (('a//', 'b//'), ['a', 'b']),
    ]
)
async def test_parse_ids_workflows(ids_in, ids_out):
    ret = await parse_ids_async(*ids_in, constraint='workflows')
    assert list(ret[0]) == ids_out


@pytest.mark.parametrize(
    'ids_in,ids_out',
    [
        (('./a',), ['a']),
    ]
)
async def test_parse_ids_workflows_src(ids_in, ids_out, abc_src_dir):
    ret = await parse_ids_async(*ids_in, constraint='workflows', src=True)
    assert list(ret[0]) == ids_out


@pytest.mark.parametrize(
    'ids_in,ids_out',
    [
        (
            ('a//i',),
            {'a': ['//i']},
        ),
        (
            ('a//i', 'a//j'),
            {'a': ['//i', '//j']},
        ),
        (
            ('a//i', 'b//i'),
            {'a': ['//i'], 'b': ['//i']},
        ),
        (
            ('a//', '//i', 'b//', '//i'),
            {'a': ['//i'], 'b': ['//i']},
        ),
    ]
)
async def test_parse_ids_tasks(ids_in, ids_out):
    ret = await parse_ids_async(*ids_in, constraint='tasks')
    assert {
        workflow_id: [detokenise(tokens) for tokens in tokens_list]
        for workflow_id, tokens_list in ret[0].items()
    } == ids_out


@pytest.mark.parametrize(
    'ids_in,ids_out',
    [
        (
            ('./a', '//i'),
            {'a': ['//i']}
        ),
        (
            ('./a', '//i', '//j', '//k'),
            {'a': ['//i', '//j', '//k']}
        ),
    ]
)
async def test_parse_ids_tasks_src(ids_in, ids_out, abc_src_dir):
    ret = await parse_ids_async(*ids_in, constraint='tasks', src=True)
    assert {
        workflow_id: [detokenise(tokens) for tokens in tokens_list]
        for workflow_id, tokens_list in ret[0].items()
    } == ids_out


@pytest.mark.parametrize(
    'ids_in,ids_out',
    [
        (('a//',), {'a': []}),
        (
            ('a//', 'b//', 'c//'),
            {'a': [], 'b': [], 'c': []}
        ),
        (('a//i',), {'a': ['//i']}),
        (('a//', '//i'), {'a': ['//i']}),
        (
            ('a//', '//i', '//j', '//k'),
            {'a': ['//i', '//j', '//k']},
        ),
        (('a//', '//i', 'b//'), {'a': ['//i'], 'b': []}),
    ]
)
async def test_parse_ids_mixed(ids_in, ids_out):
    ret = await parse_ids_async(*ids_in, constraint='mixed')
    assert {
        workflow_id: [detokenise(tokens) for tokens in tokens_list]
        for workflow_id, tokens_list in ret[0].items()
    } == ids_out


@pytest.mark.parametrize(
    'ids_in,ids_out',
    [
        (('./a',), {'a': []}),
        (('./a', '//i'), {'a': ['//i']}),
        (('./a', '//i', '//j', '//k'), {'a': ['//i', '//j', '//k']}),
        # (('./a', 'b//'), {'a': [], 'b': []}),  # TODO (debatable)
    ]
)
async def test_parse_ids_mixed_src(ids_in, ids_out, abc_src_dir):
    ret = await parse_ids_async(*ids_in, constraint='mixed', src=True)
    assert {
        workflow_id: [detokenise(tokens) for tokens in tokens_list]
        for workflow_id, tokens_list in ret[0].items()
    } == ids_out


@pytest.mark.parametrize(
    'ids_in,errors',
    [
        (('a//',), False),
        (('a//', 'b//'), False),
        (('a//', 'b//', 'c//'), True),
    ]
)
async def test_parse_ids_max_workflows(ids_in, errors):
    try:
        await parse_ids_async(*ids_in, constraint='workflows', max_workflows=2)
    except UserInputError:
        if not errors:
            raise
    else:
        if errors:
            raise Exception('Should have raised UserInputError')


@pytest.mark.parametrize(
    'ids_in,errors',
    [
        (('a//', '//i'), False),
        (('a//', '//i', '//j'), False),
        (('a//', '//i', '//j', '//k'), True),
    ]
)
async def test_parse_ids_max_tasks(ids_in, errors):
    try:
        await parse_ids_async(*ids_in, constraint='tasks', max_tasks=2)
    except UserInputError:
        if not errors:
            raise
    else:
        if errors:
            raise Exception('Should have raised UserInputError')


# async def test_parse_ids_infer_run_name():
#     workflows = await parse_ids_async(['foo//'], constraint='workflows')
#     assert workflows == []
