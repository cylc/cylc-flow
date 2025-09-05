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

import pytest

from cylc.flow.parsec import fileparse
from cylc.flow.parsec.fileparse import read_and_proc
from cylc.flow.parsec.exceptions import TemplateVarLanguageClash


@pytest.mark.parametrize(
    'templating, hashbang, msg',
    [
        ['other', '#!jinja2', 'A plugin'],
        ['jinja2', '#!other', 'A plugin'],
        ['template variables', '', 'No shebang line']
    ]
)
def test_read_and_proc_raises_TemplateVarLanguageClash(
    monkeypatch, tmp_path, templating, hashbang, msg
):
    """func fails when diffn't templating engines set in hashbang and plugin.
    """

    def fake_process_plugins(_, __):
        extra_vars = {
            'env': {},
            'template_variables': {'foo': 52},
            'templating_detected': templating
        }
        return extra_vars
    monkeypatch.setattr(fileparse, 'process_plugins', fake_process_plugins)

    file_ = tmp_path / 'flow.cylc'
    file_.write_text(
        f'{hashbang}\nfoo'
    )

    with pytest.raises(TemplateVarLanguageClash, match=msg) as exc:
        read_and_proc(file_)

    assert exc.type == TemplateVarLanguageClash
