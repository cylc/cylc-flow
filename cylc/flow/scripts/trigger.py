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

"""cylc trigger [OPTIONS] ARGS

Force tasks to run despite unsatisfied prerequisites.

* Triggering an unqueued waiting task queues it, regardless of prerequisites.
* Triggering a queued task submits it, regardless of queue limiting.
* Triggering an active task has no effect (it already triggered).

Incomplete and active-waiting tasks in the n=0 window already belong to a flow.
Triggering them queues them to run (or rerun) in the same flow.

Beyond n=0, triggered tasks get all current active flow numbers by default, or
specified flow numbers via the --flow option. Those flows - if/when they catch
up - will see tasks that ran after triggering event as having run already.

Examples:
  # trigger task foo in cycle 1234 in test
  $ cylc trigger test//1234/foo

  # trigger all failed tasks in test
  $ cylc trigger 'test//*:failed'

  # start a new flow by triggering 1234/foo in test
  $ cylc trigger --flow=new test//1234/foo
"""

from functools import partial
from typing import TYPE_CHECKING

from cylc.flow.exceptions import InputError
from cylc.flow.network.client_factory import get_client
from cylc.flow.network.multi import call_multi
from cylc.flow.option_parsers import (
    FULL_ID_MULTI_ARG_DOC,
    CylcOptionParser as COP,
)
from cylc.flow.terminal import cli_function
from cylc.flow.flow_mgr import FLOW_NONE, FLOW_NEW, FLOW_ALL

if TYPE_CHECKING:
    from optparse import Values


ERR_OPT_FLOW_VAL = "Flow values must be integer, 'all', 'new', or 'none'"
ERR_OPT_FLOW_INT = "Multiple flow options must all be integer valued"
ERR_OPT_FLOW_META = "Metadata is only for new flows"
ERR_OPT_FLOW_WAIT = (
    f"--wait is not compatible with --flow={FLOW_NEW} or --flow={FLOW_NONE}"
)


MUTATION = '''
mutation (
  $wFlows: [WorkflowID]!,
  $tasks: [NamespaceIDGlob]!,
  $flow: [Flow!],
  $flowWait: Boolean,
  $flowDescr: String,
) {
  trigger (
    workflows: $wFlows,
    tasks: $tasks,
    flow: $flow,
    flowWait: $flowWait,
    flowDescr: $flowDescr
  ) {
    result
  }
}
'''


def get_option_parser() -> COP:
    parser = COP(
        __doc__,
        comms=True,
        multitask=True,
        multiworkflow=True,
        argdoc=[FULL_ID_MULTI_ARG_DOC],
    )

    parser.add_option(
        "--flow", action="append", dest="flow", metavar="FLOW",
        help=f"Assign the triggered task to all active flows ({FLOW_ALL});"
             f" no flow ({FLOW_NONE}); a new flow ({FLOW_NEW});"
             f" or a specific flow (e.g. 2). The default is {FLOW_ALL}."
             " Reuse the option to assign multiple specific flows."
    )

    parser.add_option(
        "--meta", metavar="DESCRIPTION", action="store",
        dest="flow_descr", default=None,
        help=f"description of triggered flow (with --flow={FLOW_NEW})."
    )

    parser.add_option(
        "--wait", action="store_true", default=False, dest="flow_wait",
        help="Wait for merge with current active flows before flowing on."
    )

    return parser


def _validate(options):
    """Check validity of flow-related options."""
    for val in options.flow:
        val = val.strip()
        if val in [FLOW_NONE, FLOW_NEW, FLOW_ALL]:
            if len(options.flow) != 1:
                raise InputError(ERR_OPT_FLOW_INT)
        else:
            try:
                int(val)
            except ValueError:
                raise InputError(ERR_OPT_FLOW_VAL.format(val))

    if options.flow_descr and options.flow != [FLOW_NEW]:
        raise InputError(ERR_OPT_FLOW_META)

    if options.flow_wait and options.flow[0] in [FLOW_NEW, FLOW_NONE]:
        raise InputError(ERR_OPT_FLOW_WAIT)


async def run(options: 'Values', workflow_id: str, *tokens_list):
    pclient = get_client(workflow_id, timeout=options.comms_timeout)

    mutation_kwargs = {
        'request_string': MUTATION,
        'variables': {
            'wFlows': [workflow_id],
            'tasks': [
                tokens.relative_id
                for tokens in tokens_list
            ],
            'flow': options.flow,
            'flowWait': options.flow_wait,
            'flowDescr': options.flow_descr,
        }
    }

    await pclient.async_request('graphql', mutation_kwargs)


@cli_function(get_option_parser)
def main(parser: COP, options: 'Values', *ids: str):
    """CLI for "cylc trigger"."""

    if options.flow is None:
        options.flow = [FLOW_ALL]  # default to all active flows
    _validate(options)

    call_multi(
        partial(run, options),
        *ids,
    )
