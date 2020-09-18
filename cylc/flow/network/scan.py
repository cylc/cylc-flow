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
"""Functionality for searching for workflows running as the current user.

The :py:func:`scan` asynchronous generator yields workflows. Iterate
over them using an ``async for`` statement::

    async for flow in scan():
        print(flow['name'])

For further functionality construct a pipe::

    pipe = scan | is_active(True) | contact_info
    async for flow in pipe:
        print(f'{flow["name"]} {flow["CYLC_SUITE_HOST"]}')

There are filters which you can you to omit workflows e.g.
:py:func:`cylc_version` and transformers which acquire more information
e.g. :py:func:`contact_info`.

.. note: we must manually list functions so they get built into the docs

.. autofunction:: scan
.. autofunction:: filter_name
.. autofunction:: is_active
.. autofunction:: contact_info
.. autofunction:: cylc_version
.. autofunction:: api_version
.. autofunction:: graphql_query
.. autofunction:: title

"""

from collections.abc import Iterable
import asyncio
from pathlib import Path
import re

from pkg_resources import (
    parse_requirements,
    parse_version
)

from cylc.flow import LOG
from cylc.flow.async_util import (
    pipe,
    scandir
)
from cylc.flow.network.client import (
    SuiteRuntimeClient, ClientError, ClientTimeout)
from cylc.flow.platforms import get_platform
from cylc.flow.exceptions import SuiteStopped
from cylc.flow.suite_files import (
    ContactFileFields,
    SuiteFiles,
    get_suite_title,
    load_contact_file_async
)


SERVICE = Path(SuiteFiles.Service.DIRNAME)
CONTACT = Path(SuiteFiles.Service.CONTACT)

FLOW_FILES = {
    # marker files/dirs which we use to determine if something is a flow
    SuiteFiles.Service.DIRNAME,
    SuiteFiles.SUITE_RC,   # cylc7 flow definition file name
    SuiteFiles.FLOW_FILE,  # cylc8 flow definition file name
    'log'
}


def dir_is_flow(listing):
    """Return True if a Path contains a flow at the top level.

    Args:
        listing (list):
            A listing of the directory in question as a list of
            ``pathlib.Path`` objects.

    Returns:
        bool - True if the listing indicates that this is a flow directory.

    """
    listing = {
        path.name
        for path in listing
    }
    return bool(FLOW_FILES & listing)


@pipe
async def scan(run_dir=None, scan_dir=None, max_depth=4):
    """List flows installed on the filesystem.

    Args:
        run_dir (pathlib.Path):
            The run dir to look for workflows in, defaults to ~/cylc-run.

            All workflow registrations will be given relative to this path.
        scan_dir(pathlib.Path):
            The directory to scan for workflows in.

            Use in combination with run_dir if you want to scan a subdir
            within the run_dir.
        max_depth (int):
            The maximum number of levels to descend before bailing.

            * ``max_depth=1`` will pick up top-level suites (e.g. ``foo``).
            * ``max_depth=2`` will pick up nested suites (e.g. ``foo/bar``).

    Yields:
        dict - Dictionary containing information about the flow.

    """
    if not run_dir:
        run_dir = Path(
            get_platform()['run directory'].replace('$HOME', '~')
        ).expanduser()
    if not scan_dir:
        scan_dir = run_dir

    running = []

    # wrapper for scandir to preserve context
    async def _scandir(path, depth):
        contents = await scandir(path)
        return path, depth, contents

    # perform the first directory listing
    for subdir in await scandir(scan_dir):
        if subdir.is_dir():
            running.append(
                asyncio.create_task(
                    _scandir(subdir, 1)
                )
            )

    # perform all further directory listings
    while running:
        # wait here until there's something to do
        done, _ = await asyncio.wait(
            running,
            return_when=asyncio.FIRST_COMPLETED
        )
        for task in done:
            path, depth, contents = task.result()
            running.remove(task)
            if dir_is_flow(contents):
                # this is a flow directory
                yield {
                    'name': str(path.relative_to(run_dir)),
                    'path': path,
                }
            elif depth < max_depth:
                # we may have a nested flow, lets see...
                for subdir in contents:
                    if subdir.is_dir():
                        running.append(
                            asyncio.create_task(
                                _scandir(subdir, depth + 1)
                            )
                        )
        # don't allow this to become blocking
        await asyncio.sleep(0)


def join_regexes(*patterns):
    """Combine multiple regexes using OR logic."""
    return (re.compile(rf'({"|".join(patterns)})'),), {}


@pipe(preproc=join_regexes)
async def filter_name(flow, pattern):
    """Filter flows by name.

    Args:
        flow (dict):
            Flow information dictionary, provided by scan through the pipe.
        pattern (str):
            One or more regex patterns as strings.
            This will return True if any of the patterns match.

    """
    return bool(pattern.match(flow['name']))


@pipe
async def is_active(flow, is_active):
    """Filter flows by the presence of a contact file.

    Args:
        flow (dict):
            Flow information dictionary, provided by scan through the pipe.
        is_active (bool):
            True to filter for running flows.
            False to filter for stopped and unregistered flows.

    """
    contact = flow['path'] / SERVICE / CONTACT
    _is_active = contact.exists()
    if _is_active:
        flow['contact'] = contact
    return _is_active == is_active


@pipe
async def contact_info(flow):
    """Read information from the contact file.

    Requires:
        * is_active(True)

    Args:
        flow (dict):
            Flow information dictionary, provided by scan through the pipe.

    """
    flow.update(
        await load_contact_file_async(flow['name'], run_dir=flow['path'])
    )
    return flow


def parse_requirement(requirement_string):
    """Parse a requirement from a requirement string."""
    # we have to give the requirement a name but what we call it doesn't
    # actually matter
    for req in parse_requirements(f'x {requirement_string}'):
        # there should only be one requirement
        return (req,), {}


@pipe(preproc=parse_requirement)
async def cylc_version(flow, requirement):
    """Filter by cylc version.

    Requires:
        * is_active(True)
        * contact_info

    Args:
        flow (dict):
            Flow information dictionary, provided by scan through the pipe.
        requirement (str):
            Requirement specifier in pkg_resources format e.g. ``> 8, < 9``

    """
    return parse_version(flow[ContactFileFields.VERSION]) in requirement


@pipe(preproc=parse_requirement)
async def api_version(flow, requirement):
    """Filter by the cylc API version.

    Requires:
        * is_active(True)
        * contact_info

    Args:
        flow (dict):
            Flow information dictionary, provided by scan through the pipe.
        requirement (str):
            Requirement specifier in pkg_resources format e.g. ``> 8, < 9``

    """
    return parse_version(flow[ContactFileFields.API]) in requirement


def format_query(fields, filters=None):
    ret = ''
    stack = [(None, fields)]
    while stack:
        path, fields = stack.pop()
        if isinstance(fields, dict):
            leftover_fields = []
            for key, value in fields.items():
                if value:
                    stack.append((
                        key,
                        value
                    ))
                else:
                    leftover_fields.append(key)
            if leftover_fields:
                fields = leftover_fields
            else:
                continue
        if path:
            ret += '\n' + f'{path} {{'
            for field in fields:
                ret += f'\n  {field}'
            ret += '\n}'
        else:
            for field in fields:
                ret += f'\n{field}'
    return (ret + '\n',), {'filters': filters}


@pipe(preproc=format_query)
async def graphql_query(flow, fields, filters=None):
    """Obtain information from a GraphQL request to the flow.

    Requires:
        * is_active(True)
        * contact_info

    Args:
        flow (dict):
            Flow information dictionary, provided by scan through the pipe.
        fields (iterable):
            Iterable containing the fields to request e.g::

               ['id', 'name']

            One level of nesting is supported e.g::

               {'name': None, 'meta': ['title']}
        filters (list):
            Filter by the data returned from the query.
            List in the form ``[(key, ...), value]``, e.g::

               # state must be running
               [('state',), 'running']

               # state must be running or held
               [('state',), ('running', 'held')]

    """
    query = f'query {{ workflows(ids: ["{flow["name"]}"]) {{ {fields} }} }}'
    try:
        client = SuiteRuntimeClient(
            flow['name'],
            # use contact_info data if present for efficiency
            host=flow.get('CYLC_SUITE_HOST'),
            port=flow.get('CYLC_SUITE_PORT')
        )
    except SuiteStopped:
        LOG.warning(f'Workflow not running: {flow["name"]}')
        return False
    try:
        ret = await client.async_request(
            'graphql',
            {
                'request_string': query,
                'variables': {}
            }
        )
    except ClientTimeout:
        LOG.exception(
            f'Timeout: name: {flow["name"]}, '
            f'host: {client.host}, '
            f'port: {client.port}'
        )
        return False
    except ClientError as exc:
        LOG.exception(exc)
        return False
    else:
        # stick the result into the flow object
        for item in ret:
            if 'error' in item:
                LOG.exception(item['error']['message'])
                return False
            for workflow in ret.get('workflows', []):
                flow.update(workflow)

        # process filters
        for field, value in filters or []:
            for field_ in field:
                value_ = flow[field_]
            if isinstance(value, Iterable):
                if value_ not in value:
                    return False
            else:
                if value_ != value:
                    return False

        return flow


@pipe
async def title(flow):
    """Attempt to parse the suite title out of the flow config file.

    .. warning::
       This uses a fast but dumb method which may fail to extract the suite
       title.

       Obtaining the suite title via :py:func:`graphql_query` is preferable
       for running flows.

    """
    flow['title'] = get_suite_title(flow['name'])
    return flow
