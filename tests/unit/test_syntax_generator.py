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

import importlib

from pathlib import Path


# Fake up the module.
path = Path(__file__).parent.parent.parent / 'etc/bin/syntax_generator.py'
loader = importlib.machinery.SourceFileLoader(
    'syntaxgenerator', str(path)
)
syntax = loader.load_module()


def test_get_keywords_from_workflow_cfg():
    """It gets a list of config items.

    Not a thorough check, but ensure type is sensible and some unlikely-to
    change items are present.
    """
    result = syntax.get_keywords_from_workflow_cfg()
    assert isinstance(result, list)
    assert 'meta' in result
    assert 'scheduling' in result
    assert 'cycle point format' in result


def test_update_cylc_lang_new_section(tmp_path):
    test_file = tmp_path / 'testfile'
    test_file.write_text((
        "<!--TAG_FOR_AUTO_UPDATE-->\n"
        "some stuff"
        "<!--END_TAG_FOR_AUTO_UPDATE-->"
    ))
    syntax.update_cylc_lang(
        ['gamma', 'nu'], test_file, '#kword#{word}#kword# - '
    )
    assert test_file.read_text() == (
        "<!--TAG_FOR_AUTO_UPDATE-->\n#kword#gamma#kword#"
        " - #kword#nu#kword# -         "
        "<!--END_TAG_FOR_AUTO_UPDATE-->"
    )
