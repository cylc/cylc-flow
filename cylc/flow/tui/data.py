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

from subprocess import Popen, PIPE
import sys

from cylc.flow.exceptions import ClientError
from cylc.flow.tui.util import (
    extract_context
)


QUERY = '''
  query cli($taskStates: [String]){
    workflows {
      id
      name
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

MUTATIONS = {
    'workflow': [
        'pause',
        'resume',
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

ARGUMENT_TYPES = {
    'workflow': '[WorkflowID]!',
    'task': '[NamespaceIDGlob]!',
}

MUTATION_TEMPLATES = {
    'workflow': '''
        mutation($workflow: [WorkflowID]!) {
            pause (workflows: $workflow) {
            result
          }
        }
    ''',
    'task': '''
        mutation($workflow: [WorkflowID]!, $task: [NamespaceIDGlob]!) {
          trigger (workflows: $workflow, tasks: $task) {
            result
          }
        }
    '''
}


def generate_mutation(mutation, arguments):
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


def list_mutations(selection):
    context = extract_context(selection)
    selection_type = list(context)[-1]
    return MUTATIONS.get(selection_type, [])


def context_to_variables(context):
    """Derive multiple selection out of single selection.

    Examples:
        >>> context_to_variables(extract_context(['~a/b//c/d']))
        {'workflow': ['b'], 'task': ['c/d']}

        >>> context_to_variables(extract_context(['~a/b//c']))
        {'workflow': ['b'], 'task': ['c/*']}

        >>> context_to_variables(extract_context(['~a/b']))
        {'workflow': ['b']}

    """
    # context_to_variables because it can only handle single-selection ATM
    variables = {'workflow': context['workflow']}
    if 'task' in context:
        variables['task'] = [
            f'{context["cycle"][0]}/{context["task"][0]}'
        ]
    elif 'cycle' in context:
        variables['task'] = [f'{context["cycle"][0]}/*']
    return variables


def mutate(client, mutation, selection):
    """Issue a mutation over a network interface."""
    context = extract_context(selection)
    variables = context_to_variables(context)
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
    for workflow in variables['workflow']:
        if mutation == 'play':
            cli_cmd('play', workflow)
        elif mutation == 'clean':  # noqa: SIM106
            cli_cmd('clean', workflow)
            # tui only supports single-workflow display ATM so
            # clean should shut down the program
            sys.exit()
        elif mutation in list_mutations(selection):  # noqa: SIM106
            # this is an "online" mutation -> ignore
            pass
        else:
            raise Exception(f'Invalid mutation: {mutation}')


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
    out, err = proc.communicate()
    if proc.returncode != 0:
        raise ClientError(err)
