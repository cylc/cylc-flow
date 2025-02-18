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

"""Test parsec type parsing.

.. note::

   This test is a pytest port of the old ``tests/parsec/synonyms``
   test battery.

"""

import pytest

from cylc.flow.parsec.config import (
    ConfigNode as Conf
)
from cylc.flow.parsec.validate import (
    CylcConfigValidator as VDR
)


@pytest.fixture
def generate_spec():
    def _inner(typ, validator):
        """Return a sample spec for the given data type.

        Args:
            typ (str):
                An arbirtrary name for this type.
            validator (str):
                A parsec validator.

        Returns:
            cylc.flow.parsec.config.ConfigNode

        """
        with Conf('/') as myconf, Conf(typ):
            Conf('<item>', validator)
        return myconf
    return _inner


@pytest.fixture
def generate_config():
    def _inner(typ, value):
        """Return a sample config for the given data type.

        The aim is to cover every facetious combination of quotes
        newlines and comments.

        Args:
            typ (str):
                An arbitrary name for this type.
            value (object):
                A stringable value to dump in the conf.
                For list types provide a list of stringable values.

        """
        if isinstance(value, list):
            return f'''
                [{typ}]
                    plain = {','.join(value)}  # comment
                    spaced = {', '.join(value)}  # comment
                    badly spaced = {'  ,  '.join(value)}  # comment
                    single quoted = {', '.join((f"'{x}'" for x in value))}
                    double quoted = {', '.join((f'"{x}"' for x in value))}
                    multi line = {value[0]}, \\
                        {', '.join(value[1:])}  # comment
            '''
        else:
            return f'''
                [{typ}]
                    plain1 = {value}  # comment
                    single quoted = '{value}'  # comment
                    double quoted = "{value}"  # comment
                    triple single quoted = \'\'\'{value}\'\'\'  # comment
                    triple double quoted = """{value}"""  # comment
                    triple single quoted multi = \'\'\'
                        {value}
                    \'\'\'  # comment
                    triple double quoted multi = """
                        {value}
                    """  # comment
            '''
    return _inner


def test_types(generate_spec, generate_config, config):
    """Test type parsing.

    Test every facetious combination of:

    * Data types.
    * Quotation.
    * Inline-commenting.

    """
    for typ, validator, string_repr, parsed_value in [
            ('boolean', VDR.V_BOOLEAN, 'true', True),
            ('boolean', VDR.V_BOOLEAN, 'True', True),
            ('boolean', VDR.V_BOOLEAN, 'false', False),
            ('boolean', VDR.V_BOOLEAN, 'False', False),
            ('integer', VDR.V_INTEGER, '42', 42),
            ('float', VDR.V_FLOAT, '9.9', 9.9),
            ('string', VDR.V_STRING, 'the quick brown fox',
             'the quick brown fox'),
            (
                'integer_list',
                VDR.V_INTEGER_LIST,
                ['1', '2', '3', '4', '5'],
                [1, 2, 3, 4, 5]
            ),
            (
                'float_list',
                VDR.V_FLOAT_LIST,
                ['1.1', '2.2', '3.3', '4.4', '5.5'],
                [1.1, 2.2, 3.3, 4.4, 5.5]
            ),
            (
                'string_list',
                VDR.V_STRING_LIST,
                ['be', 'ef', 'we', 'll', 'in', 'gt', 'on'],
                ['be', 'ef', 'we', 'll', 'in', 'gt', 'on']
            ),
    ]:
        spec = generate_spec(typ, validator)
        conf = generate_config(typ, string_repr)
        cfg = config(spec, conf)
        assert all((
            value == parsed_value
            for value in cfg.get()[typ].values()
        ))
