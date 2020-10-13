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

from typing import Optional

import pytest
from graphql import parse

from cylc.flow.network.graphql import AstDocArguments
from cylc.flow.network.schema import schema


@pytest.mark.parametrize(
    'query,'
    'variables,'
    'expected_variables,'
    'expected_error',
    [
        # a simple query with the correct variables
        (
            '''
            query ($workflowID: ID) {
                workflows (ids: [$workflowID]) {
                    id
                }
            }
            ''',
            {
                'workflowID': 'cylc|workflow'
            },
            {
                'workflowID': 'cylc|workflow'
            },
            None
        ),
        # a query with a fragment and with the correct variables
        (
            '''
            query ($workflowID: ID) {
                ...WorkflowData
            }
            fragment WorkflowData on workflows {
                workflows (ids: [$workflowID]) {
                    id
                }
            }
            ''',
            {
                'workflowID': 'cylc|workflow'
            },
            {
                'workflowID': 'cylc|workflow'
            },
            None
        ),
        # a query with the right variable definition, but missing
        # variable in the provided values
        (
            '''
            query ($workflowID: ID) {
                workflows (ids: [$workflowID]) {
                    id
                }
            }
            ''',
            {
                'workflowId': 'cylc|workflow'
            },
            None,
            ValueError
        )
    ]
)
def test_query_variables(
        query: str,
        variables: dict,
        expected_variables: Optional[dict],
        expected_error: Optional[Exception]
):
    """Test that query variables are parsed correctly.

    Args:
        query (str): a valid GraphQL query (using our schema)
        variables (dict): map with variable values for the query
        expected_variables (dict): expected parsed variables
        expected_error (Exception): expected error, if any
    """
    def test():
        """Inner function to avoid duplication in if/else"""
        document = parse(query)
        document_arguments = AstDocArguments(
            schema=schema,
            document_ast=document,
            variable_values=variables
        )
        parsed_variables = next(
            iter(
                document_arguments.operation_defs.values()
            )
        )['variables']
        assert expected_variables == parsed_variables
    if expected_error is not None:
        with pytest.raises(expected_error):
            test()
    else:
        test()
