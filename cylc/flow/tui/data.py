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
        firstParent {
          id
          name
        }
        jobs(sort: { keys: ["submit_num"], reverse: true}) {
          id
          submitNum
          state
          host
          jobRunnerName
          jobId
          startedTime
        }
        task {
          meanElapsedTime
        }
      }
      familyProxies(exids: ["root"], states: $taskStates) {
        id
        name
        cyclePoint
        state
        isHeld
        firstParent {
          id
          name
        }
      }
      cyclePoints: familyProxies(ids: ["root"], states: $taskStates) {
        id
        cyclePoint
        state
        isHeld
      }
    }
  }
'''

MUTATIONS = {
    'workflow': [
        'hold',
        'release',
        'reload',
        'stop'
    ],
    'cycle_point': [
        'hold',
        'release',
        'kill',
        'trigger'
    ],
    'task': [
        'hold',
        'release',
        'kill',
        'trigger'
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
            hold (workflows: $workflow) {
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

        >>> context_to_variables(extract_context(['a|b|c|d']))
        {'workflow': ['b'], 'task': ['d.c']}

        >>> context_to_variables(extract_context(['a|b|c']))
        {'workflow': ['b'], 'task': ['*.c']}

        >>> context_to_variables(extract_context(['a|b']))
        {'workflow': ['b']}

    """
    # context_to_variables because it can only handle single-selection ATM
    variables = {'workflow': context['workflow']}
    if 'task' in context:
        variables['task'] = [
            f'{context["task"][0]}.{context["cycle_point"][0]}'
        ]
    elif 'cycle_point' in context:
        variables['task'] = [f'*.{context["cycle_point"][0]}']
    return variables


def mutate(client, mutation, selection):
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
