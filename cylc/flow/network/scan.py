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
"""Functionality for searching for workflows running as the current user.

The :py:func:`scan` asynchronous generator yields workflows. Iterate
over them using an ``async for`` statement::

    async for flow in scan():
        print(flow['name'])

For further functionality construct a pipe::

    pipe = scan | is_active(True) | contact_info
    async for flow in pipe:
        print(f'{flow["name"]} {flow["CYLC_WORKFLOW_HOST"]}')

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
.. autofunction:: workflow_params

"""

import asyncio
from pathlib import Path
import re
from typing import AsyncGenerator, Dict, Iterable, List, Optional, Tuple, Union

from pkg_resources import (
    parse_requirements,
    parse_version
)

from cylc.flow import LOG
from cylc.flow.async_util import (
    pipe,
    scandir
)
from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.exceptions import WorkflowStopped
from cylc.flow.network.client import (
    ClientError,
    ClientTimeout,
    WorkflowRuntimeClient,
)
from cylc.flow.pathutil import get_cylc_run_dir
from cylc.flow.rundb import CylcWorkflowDAO
from cylc.flow.workflow_files import (
    ContactFileFields,
    WorkflowFiles,
    get_workflow_title,
    load_contact_file_async,
)


SERVICE = Path(WorkflowFiles.Service.DIRNAME)
CONTACT = Path(WorkflowFiles.Service.CONTACT)

FLOW_FILES = {
    # marker files/dirs which we use to determine if something is a flow
    WorkflowFiles.Service.DIRNAME,
    WorkflowFiles.SUITE_RC,   # cylc7 flow definition file name
    WorkflowFiles.FLOW_FILE,  # cylc8 flow definition file name
    WorkflowFiles.LOG_DIR
}

EXCLUDE_FILES = {
    WorkflowFiles.RUN_N,
    WorkflowFiles.Install.SOURCE
}


def dir_is_flow(listing: Iterable[Path]) -> bool:
    """Return True if a Path contains a flow at the top level.

    Args:
        listing (list):
            A listing of the directory in question as a list of
            ``pathlib.Path`` objects.

    Returns:
        bool - True if the listing indicates that this is a flow directory.

    """
    names = {path.name for path in listing}
    return bool(FLOW_FILES & names)


@pipe
async def scan_multi(
    dirs: Iterable[Path],
    max_depth: Optional[int] = None
) -> AsyncGenerator[dict, None]:
    """List flows from multiple directories.

    This is intended for listing uninstalled flows though will work for
    installed ones.

    Args:
        dirs
    """
    if max_depth is None:
        max_depth = glbl_cfg().get(['install', 'max depth'])
    for dir_ in dirs:
        async for flow in scan(
            run_dir=dir_,
            scan_dir=dir_,
            max_depth=max_depth
        ):
            # set the flow name as the full path
            flow['name'] = dir_ / flow['name']
            yield flow


@pipe
async def scan(
    run_dir: Optional[Path] = None,
    scan_dir: Optional[Path] = None,
    max_depth: Optional[int] = None
) -> AsyncGenerator[Dict[str, Union[str, Path]], None]:
    """List flows installed on the filesystem.

    Args:
        run_dir:
            The run dir to look for workflows in, defaults to ~/cylc-run.

            All workflow registrations will be given relative to this path.
        scan_dir:
            The directory to scan for workflows in.

            Use in combination with run_dir if you want to scan a subdir
            within the run_dir.
        max_depth:
            The maximum number of levels to descend before bailing.

            * ``max_depth=1`` will pick up top-level workflows (e.g. ``foo``).
            * ``max_depth=2`` will pick up nested workflows (e.g. ``foo/bar``).

    Yields:
        dict - Dictionary containing information about the flow.

    """
    cylc_run_dir = Path(get_cylc_run_dir())
    if not run_dir:
        run_dir = cylc_run_dir
    if not scan_dir:
        scan_dir = run_dir
    if max_depth is None:
        max_depth = glbl_cfg().get(['install', 'max depth'])

    running: List[asyncio.tasks.Task] = []

    # wrapper for scandir to preserve context
    async def _scandir(path: Path, depth: int) -> Tuple[Path, int, List[Path]]:
        contents = await scandir(path)
        return path, depth, contents

    def _scan_subdirs(listing: List[Path], depth: int) -> None:
        for subdir in listing:
            if subdir.is_dir() and subdir.stem not in EXCLUDE_FILES:
                running.append(
                    asyncio.create_task(
                        _scandir(subdir, depth + 1)
                    )
                )

    # perform the first directory listing
    scan_dir_listing = await scandir(scan_dir)
    if scan_dir != cylc_run_dir and dir_is_flow(scan_dir_listing):
        # If the scan_dir itself is a workflow run dir, yield nothing
        return

    _scan_subdirs(scan_dir_listing, depth=0)

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
                _scan_subdirs(contents, depth)
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
        pattern (re.Pattern):
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

               # state must be running or paused
               [('state',), ('running', 'paused')]

    """
    query = f'query {{ workflows(ids: ["{flow["name"]}"]) {{ {fields} }} }}'
    try:
        client = WorkflowRuntimeClient(
            flow['name'],
            # use contact_info data if present for efficiency
            host=flow.get('CYLC_WORKFLOW_HOST'),
            port=flow.get('CYLC_WORKFLOW_PORT')
        )
    except WorkflowStopped:
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
    """Attempt to parse the workflow title out of the flow config file.

    .. warning::
       This uses a fast but dumb method which may fail to extract the workflow
       title.

       Obtaining the workflow title via :py:func:`graphql_query` is preferable
       for running flows.

    """
    flow['title'] = get_workflow_title(flow['name'])
    return flow


@pipe
async def workflow_params(flow):
    """Extract workflow parameter entries from the workflow database.

    Requires:
        * is_active(True)
    """
    params = {}

    def _callback(_, entry):
        nonlocal params
        key, value = entry
        params[key] = value

    db_file = flow['path'] / SERVICE / 'db'
    if db_file.exists():
        dao = CylcWorkflowDAO(db_file, is_public=False)
        dao.connect()
        dao.select_workflow_params(_callback)
        flow['workflow_params'] = params

    return flow
