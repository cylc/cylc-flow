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
        parents {
          id
          name
        }
        jobs {
          id
          submitNum
          state
          host
          batchSysName
          batchSysJobId
          startedTime
        }
        task {
          meanElapsedTime
        }
      }
      familyProxies(states: $taskStates) {
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
    }
  }
'''


MUTATIONS = {
    'workflow': [
        'hold',
        'release',
        'stop'
    ],
    'task':  [
        'hold',
        'release',
        'kill',
        'trigger'
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
    return MUTATIONS[selection_type]


def fudge(context):
    # fudge because it can only handle single-selection ATM
    selection_type = list(context)[-1]
    args = {'workflow': context['workflow']}
    if 'task' in context:
        args['task'] = [f'{context["task"][0]}.{context["cycle_point"][0]}']
    return args


def mutate(client, mutation, selection):
    context = extract_context(selection)
    variables = fudge(context)
    request_string = generate_mutation(mutation, variables)
    res = client(
        'graphql',
        {
            # 'request_string': MUTATION_TEMPLATES[selection_type],
            'request_string': request_string,
            'variables': variables
        }
    )
