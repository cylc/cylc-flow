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
"""Test scan filters and data provision stuff."""

from pathlib import Path
import re
from textwrap import dedent

from cylc.flow.network.scan import (
    api_version,
    contact_info,
    cylc_version,
    filter_name,
    graphql_query,
    validate_contact_info
)
from cylc.flow.workflow_files import (
    ContactFileFields,
    WorkflowFiles
)


SRV_DIR = Path(WorkflowFiles.Service.DIRNAME)
CONTACT = Path(WorkflowFiles.Service.CONTACT)


def test_filter_name_preprocess():
    """It should combine provided patterns and compile them."""
    pipe = filter_name('^f', '^c')
    assert pipe.args[0] == re.compile('(^f|^c)')


async def test_filter_name():
    """It should filter flows by registration name."""
    pipe = filter_name('^f')
    assert await pipe.func(
        {'name': 'foo'},
        *pipe.args
    )
    assert not await pipe.func(
        {'name': 'bar'},
        *pipe.args
    )


async def test_cylc_version():
    """It should filter flows by cylc version."""
    version = ContactFileFields.VERSION

    pipe = cylc_version('>= 8.0a1, < 9')
    assert await pipe.func(
        {version: '8.0a1'},
        *pipe.args
    )

    pipe = cylc_version('>= 8.0a1, < 9')
    assert not await pipe.func(
        {version: '7.8.4'},
        *pipe.args
    )


async def test_api_version():
    """It should filter flows by api version."""
    version = ContactFileFields.API

    pipe = api_version('>= 4, < 5')
    assert await pipe.func(
        {version: '4'},
        *pipe.args
    )

    pipe = api_version('>= 4, < 5')
    assert not await pipe.func(
        {version: '5'},
        *pipe.args
    )


async def test_contact_info(tmp_path):
    """It should load info from the contact file."""
    # create a dummy flow
    Path(tmp_path, 'foo', SRV_DIR).mkdir(parents=True)
    # write a contact file with some junk in it
    with open(Path(tmp_path, 'foo', SRV_DIR, CONTACT), 'w+') as contact:
        contact.write(dedent('''
            foo=1
            bar=2
            baz=3
        ''').strip())
    # create a flow dict as returned by scan
    flow = {
        'name': 'foo',
        'path': tmp_path / 'foo'
    }
    # ensure the contact fields get added to the flow dict
    assert await contact_info.func(flow) == {
        **flow,
        'foo': '1',
        'bar': '2',
        'baz': '3'
    }


def test_graphql_query_preproc():
    """It should format graphql query fragments from the input data."""
    pipe = graphql_query(['a', 'b', 'c'])
    assert pipe.args[0] == dedent('''
        a
        b
        c
    ''')

    pipe = graphql_query({'a': None, 'b': None, 'c': None})
    assert pipe.args[0] == dedent('''
        a
        b
        c
    ''')

    pipe = graphql_query({'a': None, 'b': ['ba', 'bb'], 'c': None})
    assert pipe.args[0] == dedent('''
        a
        c
        b {
          ba
          bb
        }
    ''')


async def test_validate_contact_file(tmp_path):
    """Ensure rejection for missing fields"""

    flow = {
        'name': 'foo',
        'path': tmp_path / 'foo',
    }
    # contact_info has already loaded info from contact file (missing fields)
    assert await validate_contact_info.func(flow) is False


async def test_validate_contact_file_no_missing_fields(tmp_path):
    """Ensure rejection for missing fields"""
    version = ContactFileFields.API
    name = ContactFileFields.NAME
    host = ContactFileFields.HOST
    flow = {
        'name': 'foo',
        'path': tmp_path / 'foo',
        version: 1,
        name: 'moo',
        host: 'hosty'
    }
    assert await validate_contact_info.func(flow) == flow
