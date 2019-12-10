from ansimarkup import parse

TASK_ICONS = {
    'waiting': '\u25CB',
    'submitted': '\u2299',
    'running:0': '\u2299',
    'running:25': '\u25D4',
    'running:50': '\u25D1',
    'running:75': '\u25D5',
    'succeeded': '\u25CB',
    'failed': '\u2297'
}

JOB_ICON = '\u25A0'

JOB_COLOURS = {
    'submitted': '7DCFD4',
    'running': '6AA4F1',
    'succeeded': '51AF51',
    'failed': 'CF4848',
    'submit-failed': 'BE6AC0'
}


def format_job(status):
    colour = JOB_COLOURS[status]
    return parse(f'<fg #{colour}>{JOB_ICON}</fg #{colour}>')


EXAMPLES = [
    {
        'name': 'foo',
        'status': 'waiting',
        'jobs': []
    },
    {
        'name': 'bar',
        'status': 'submitted',
        'jobs': ['submitted']
    },
    {
        'name': 'baz',
        'status': 'failed',
        'jobs': ['failed']
    },
    {
        'name': 'pub',
        'status': 'running:25',
        'jobs': ['running', 'failed', 'failed']
    }
]

for example in EXAMPLES:
    print(
        TASK_ICONS[example['status']]
        + ' '
        + example['name']
        + ' '
        + ' '.join(format_job(status) for status in example['jobs'])
    )
