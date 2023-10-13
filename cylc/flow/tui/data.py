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

from functools import partial
from subprocess import Popen, PIPE

from cylc.flow.exceptions import (
    ClientError,
    ClientTimeout,
    WorkflowStopped,
)
from cylc.flow.network.client_factory import get_client
from cylc.flow.id import Tokens
from cylc.flow.tui.util import (
    extract_context
)


# the GraphQL query which Tui runs against each of the workflows
# is is subscribed to
QUERY = '''
  query cli($taskStates: [String]){
    workflows {
      id
      name
      port
      status
      stateTotals
      taskProxies(states: $taskStates) {
        id
        name
        cyclePoint
        state
        isHeld
        isQueued
        isRunahead
        firstParent {
          id
          name
        }
        jobs(sort: { keys: ["submit_num"], reverse: true}) {
          id
          submitNum
          state
          platform
          jobRunnerName
          jobId
          startedTime
          finishedTime
        }
        task {
          meanElapsedTime
        }
      }
      familyProxies(exids: ["*/root"], states: $taskStates) {
        id
        name
        cyclePoint
        state
        isHeld
        isQueued
        isRunahead
        firstParent {
          id
          name
        }
      }
      cyclePoints: familyProxies(ids: ["*/root"], states: $taskStates) {
        id
        cyclePoint
        state
        isHeld
        isQueued
        isRunahead
      }
    }
  }
'''

# the list of mutations we can call on a running scheduler
MUTATIONS = {
    'workflow': [
        'pause',
        'reload',
        'stop',
    ],
    'cycle': [
        'hold',
        'release',
        'kill',
        'trigger',
        'poll',
    ],
    'task': [
        'hold',
        'release',
        'kill',
        'trigger',
        'poll',
    ],
    'job': [
        'kill',
    ]
}

# mapping of Tui's node types (e.g. workflow) onto GraphQL argument types
# (e.g. WorkflowID)
ARGUMENT_TYPES = {
    # <tui-node-type>: <graphql-argument-type>
    'workflow': '[WorkflowID]!',
    'task': '[NamespaceIDGlob]!',
}


def cli_cmd(*cmd):
    """Issue a CLI command.

    Args:
        cmd:
            The command without the 'cylc' prefix'.

    Rasies:
        ClientError:
            In the event of mishap for consistency with the network
            client alternative.

    """
    proc = Popen(  # nosec (command constructed internally, no untrusted input)
        ['cylc', *cmd],
        stderr=PIPE,
        stdout=PIPE,
        text=True,
    )
    _out, err = proc.communicate()
    if proc.returncode != 0:
        raise ClientError(f'Error in command cylc {" ".join(cmd)}\n{err}')


# the mutations we have to go through the CLI to perform
OFFLINE_MUTATIONS = {
    'user': {
        'stop-all': partial(cli_cmd, 'stop', '*'),
    },
    'workflow': {
        'play': partial(cli_cmd, 'play'),
        'clean': partial(cli_cmd, 'clean', '--yes'),
        'reinstall-reload': partial(cli_cmd, 'vr', '--yes'),
    }
}


def generate_mutation(mutation, arguments):
    """Return a GraphQL mutation string.

    Args:
        mutation:
            The mutation name.
        Arguments:
            The arguments to provide to it.

    """
    arguments.pop('user')
    graphql_args = ', '.join([
        f'${argument}: {ARGUMENT_TYPES[argument]}'
        for argument in arguments
    ])
    mutation_args = ', '.join([
        f'{argument}s: ${argument}'
        for argument in arguments
    ])

    return f'''
        mutation({graphql_args}) {{
            {mutation} ({mutation_args}) {{
                result
            }}
        }}
    '''


def list_mutations(selection, is_running=True):
    """List mutations relevant to the provided selection.

    Args:
        selection:
            The user selection.
        is_running:
            If False, then mutations which require the scheduler to be
            running will be omitted.

            Note, this is only relevant for workflow nodes because if a
            workflow is stopped, then any tasks within it will be removed
            anyway.

    """
    context = extract_context(selection)
    selection_type = list(context)[-1]
    ret = []
    if is_running:
        # add the online mutations
        ret.extend(MUTATIONS.get(selection_type, []))
    # add the offline mutations
    ret.extend(OFFLINE_MUTATIONS.get(selection_type, []))
    return sorted(ret)


def context_to_variables(context):
    """Derive multiple selection out of single selection.

    Examples:
        >>> context_to_variables(extract_context(['~a/b//c/d']))
        {'user': ['a'], 'workflow': ['b'], 'task': ['c/d']}

        >>> context_to_variables(extract_context(['~a/b//c']))
        {'user': ['a'], 'workflow': ['b'], 'task': ['c/*']}

        >>> context_to_variables(extract_context(['~a/b']))
        {'user': ['a'], 'workflow': ['b']}

    """
    # context_to_variables because it can only handle single-selection ATM
    variables = {'user': context['user']}

    if 'workflow' in context:
        variables['workflow'] = context['workflow']
    if 'task' in context:
        variables['task'] = [
            Tokens(
                cycle=context['cycle'][0],
                task=context['task'][0]
            ).relative_id
        ]
    elif 'cycle' in context:
        variables['task'] = [
            Tokens(cycle=context['cycle'][0], task='*').relative_id
        ]
    return variables


def mutate(mutation, selection):
    """Call a mutation.

    Args:
        mutation:
            The mutation name (e.g. stop).
        selection:
            The Tui selection (i.e. the row(s) selected in Tui).

    """
    if mutation in {
        _mutation
        for section in OFFLINE_MUTATIONS.values()
        for _mutation in section
    }:
        offline_mutate(mutation, selection)
    else:
        online_mutate(mutation, selection)


def online_mutate(mutation, selection):
    """Issue a mutation over a network interface."""
    context = extract_context(selection)
    variables = context_to_variables(context)

    # note this only supports single workflow mutations at present
    workflow = variables['workflow'][0]
    try:
        client = get_client(workflow)
    except WorkflowStopped:
        raise Exception(
            f'Cannot peform command {mutation} on a stopped workflow'
        )
    except (ClientError, ClientTimeout) as exc:
        raise Exception(
            f'Error connecting to workflow: {exc}'
        )

    request_string = generate_mutation(mutation, variables)
    client(
        'graphql',
        {
            'request_string': request_string,
            'variables': variables
        }
    )


def offline_mutate(mutation, selection):
    """Issue a mutation over the CLI or other offline interface."""
    context = extract_context(selection)
    variables = context_to_variables(context)
    if 'workflow' in variables:
        for workflow in variables['workflow']:
            # NOTE: this currently only supports workflow mutations
            OFFLINE_MUTATIONS['workflow'][mutation](workflow)
    else:
        OFFLINE_MUTATIONS['user'][mutation]()
