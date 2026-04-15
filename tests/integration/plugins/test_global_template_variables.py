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


from cylc.flow.util import sstrip


async def test_global_template_variables(
    flow, scheduler, start, mock_glbl_cfg, one_conf
):
    """It should ingest template variables defined in the global config.

    This test makes sure that global tempalte variables are provided, but also
    that they are provided as the appropriate type by attempting to mutate
    them (e.g. `STRING + ' '`).
    """
    mock_glbl_cfg(
        'cylc.flow.plugins.global_template_variables.glbl_cfg',
        '''
            [install]
                [[template variables]]
                    # NOTE: both sets of quotes should be preserved
                    STRING = '"answer"'
                    INT = 40
                    BOOL = True
                    LIST = [5, 6]
                    TUPLE = (1, "7")
                    DICT = {'a': 0, 1: 'possible'}
        ''',
    )
    id_ = flow(
        {
            '#!Jinja2': '',
            'meta': {
                'description': '''
                    The {{ STRING + ' ' }}is {{ INT + 1 + BOOL }}.

                    The question, what do you get if you multiply
                    {{ LIST[0] + 1 }} by {{ TUPLE[1] + '?' }}

                    Or is it {{ DICT[TUPLE[DICT['a']]] + ' to know both' }}?
                '''
            },
            **one_conf,
        }
    )
    schd = scheduler(id_)
    async with start(schd):
        assert schd.config.cfg['meta']['description'] == sstrip('''
            The "answer" is 42.
            The question, what do you get if you multiply
            6 by 7?
            Or is it possible to know both?
        ''')
