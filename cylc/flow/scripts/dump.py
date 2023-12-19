#!/usr/bin/env python3

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

"""cylc dump [OPTIONS] ARGS

Print information about a running workflow.

This command can provide information about active tasks, e.g. running or queued
tasks. For more detailed view of the workflow see `cylc tui` or `cylc gui`.

For command line monitoring:
* `cylc tui`
* `watch cylc dump WORKFLOW_ID` works for small simple workflows

For more information about a specific task, such as the current state of
its prerequisites and outputs, see 'cylc show'.

Examples:
  # Display the state of all active tasks, sorted by cycle point:
  $ cylc dump --tasks --sort WORKFLOW_ID | grep running

  # Display the state of all active in a particular cycle point:
  $ cylc dump -t WORKFLOW_ID | grep 2010082406
"""

import asyncio
import json
from typing import TYPE_CHECKING

from graphene.utils.str_converters import to_snake_case

from cylc.flow.exceptions import CylcError
from cylc.flow.id_cli import parse_id_async
from cylc.flow.option_parsers import (
    WORKFLOW_ID_ARG_DOC,
    CylcOptionParser as COP,
)
from cylc.flow.network.client_factory import get_client
from cylc.flow.terminal import cli_function

if TYPE_CHECKING:
    from optparse import Values


TASK_SUMMARY_FRAGMENT = '''
fragment tProxy on TaskProxy {
  id
  name
  cyclePoint
  state
  graphDepth
  isHeld
  isQueued
  isRunahead
  flowNums
  firstParent {
    id
  }
  jobSubmits
  jobs(sort: {keys: ["submitNum"], reverse: true}) {
    id
    state
    submitNum
    submittedTime
    startedTime
    finishedTime
    jobLogDir
    platform
    executionTimeLimit
    jobRunnerName
    jobId
  }
}
'''

FAMILY_SUMMARY_FRAGMENT = '''
fragment fProxy on FamilyProxy {
  id
  name
  cyclePoint
  state
}
'''

WORKFLOW_SUMMARY_FRAGMENT = '''
fragment wFlow on Workflow {
  name
  oldestActiveCyclePoint
  newestActiveCyclePoint
  timeZoneInfo {
    hours
    minutes
    stringBasic
    stringExtended
  }
  lastUpdated
  runMode
  states
  namespaceDefinitionOrder: nsDefOrder
  reloaded
  stateTotals
  meta {
    title
    description
    URL
    userDefined
  }
  status
  statusMsg
  families {
    name
    meta {
      title
      description
      URL
      userDefined
    }
    firstParent {
      name
    }
  }
  tasks {
    name
    meta {
      title
      description
      URL
      userDefined
    }
    meanElapsedTime
    firstParent {
      name
    }
  }
}
'''


def get_option_parser():
    parser = COP(
        __doc__,
        comms=True,
        argdoc=[WORKFLOW_ID_ARG_DOC],
    )
    parser.add_option(
        "-g", "--global", help="Global information only.",
        action="store_const", const="global", dest="disp_form")
    parser.add_option(
        "-t", "--tasks", help="Task states only.",
        action="store_const", const="tasks", dest="disp_form")
    parser.add_option(
        "-f", "--flows", help="Print flow numbers with tasks.",
        action="store_true", default=False, dest="show_flows")
    parser.add_option(
        "-r", "--raw", "--raw-format",
        help='Display raw format.',
        action="store_const", const="raw", dest="disp_form")
    parser.add_option(
        "-p", "--pretty", "--pretty-print",
        help='Display raw format with indents and newlines.',
        action="store_true", default=False, dest="pretty")
    parser.add_option(
        "-s", "--sort",
        help="Task states only; sort by cycle point instead of name.",
        action="store_true", default=False, dest="sort_by_cycle")

    return parser


@cli_function(get_option_parser)
def main(_, options: 'Values', workflow_id: str) -> None:
    asyncio.run(dump(workflow_id, options))


async def dump(workflow_id, options, write=print):
    workflow_id, *_ = await parse_id_async(
        workflow_id,
        constraint='workflows',
    )
    pclient = get_client(
        workflow_id,
        # set the default timeout a bit higher for "cylc dump" as it can
        # take a little while for Cylc to formulate the response
        timeout=options.comms_timeout or 15,
    )

    if options.sort_by_cycle:
        sort_args = {'keys': ['cyclePoint', 'name']}
    else:
        sort_args = {'keys': ['name', 'cyclePoint']}

    # retrict to the n=0 window
    graph_depth = 0

    if options.disp_form == "raw":
        query = f'''
            {TASK_SUMMARY_FRAGMENT}
            {FAMILY_SUMMARY_FRAGMENT}
            {WORKFLOW_SUMMARY_FRAGMENT}
            query ($wFlows: [ID]!, $sortBy: SortArgs) {{
              workflows (ids: $wFlows, stripNull: false) {{
                ...wFlow
                taskProxies (sort: $sortBy, graphDepth: {graph_depth}) {{
                  ...tProxy
                }}
                familyProxies (sort: $sortBy, graphDepth: {graph_depth}) {{
                  ...fProxy
                }}
              }}
            }}'''
    elif options.disp_form != "tasks":
        query = f'''
            {WORKFLOW_SUMMARY_FRAGMENT}
            query ($wFlows: [ID]!) {{
              workflows (ids: $wFlows, stripNull: false) {{
                ...wFlow
              }}
            }}'''
    else:
        query = f'''
            {TASK_SUMMARY_FRAGMENT}
            query ($wFlows: [ID]!, $sortBy: SortArgs) {{
              workflows (ids: $wFlows, stripNull: false) {{
                taskProxies (sort: $sortBy, graphDepth: {graph_depth}) {{
                  ...tProxy
                }}
              }}
            }}'''

    query_kwargs = {
        'request_string': query,
        'variables': {'wFlows': [workflow_id], 'sortBy': sort_args}
    }

    workflows = await pclient.async_request('graphql', query_kwargs)

    try:
        for summary in workflows['workflows']:
            if options.disp_form == "raw":
                if options.pretty:
                    write(json.dumps(summary, indent=4))
                else:
                    write(summary)
            else:
                if options.disp_form != "tasks":
                    node_urls = {
                        node['name']: node['meta']['URL']
                        for node in summary['tasks'] + summary['families']
                    }
                    summary['workflowUrls'] = {
                        node_name: node_urls[node_name]
                        for node_name in summary['namespaceDefinitionOrder']
                        if node_name in node_urls
                    }
                    summary['workflowUrls']['workflow_id'] = (
                        summary['meta']['URL'])
                    del summary['tasks']
                    del summary['families']
                    del summary['meta']
                    for key, value in sorted(summary.items()):
                        write(
                            f'{to_snake_case(key).replace("_", " ")}={value}')
                else:
                    for item in summary['taskProxies']:
                        if options.sort_by_cycle:
                            values = [
                                item['cyclePoint'],
                                item['name'],
                                item['state']]
                        else:
                            values = [
                                item['name'],
                                item['cyclePoint'],
                                item['state']]
                        values.append('held' if item['isHeld'] else 'not-held')
                        values.append('queued' if item['isQueued']
                                      else 'not-queued')
                        values.append('runahead' if item['isRunahead']
                                      else 'not-runahead')
                        if options.show_flows:
                            values.append(item['flowNums'])
                        write(', '.join(values))
    except Exception as exc:
        raise CylcError(
            json.dumps(workflows, indent=4) + '\n' + str(exc) + '\n')
