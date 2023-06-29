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

from cylc.flow.scripts.view import get_option_parser, _main as view
from cylc.flow.option_parsers import Options


async def test_list_tvars(tmp_path, capsys):
    """View shows that lists of comma separated args are converted into
    strings:
    """
    (tmp_path / 'flow.cylc').write_text(
        '#!jinja2\n'
        '{% for i in FOO %}\n'
        '# {{i}} is string: {{i is string}}\n'
        '{% endfor %}\n'
    )
    options = Options(get_option_parser())()
    options.jinja2 = True
    options.templatevars_lists = ['FOO="w,x",y,z']
    await view(options, str(tmp_path))
    result = capsys.readouterr().out.split('\n')
    for string in ['w,x', 'y', 'z']:
        assert f'# {string} is string: True' in result
