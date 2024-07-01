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

from typing import Optional, Type

import pytest
from pytest import param
from graphql import parse

from cylc.flow.network.protobuf.cylc.v5.schema_pb2 import PbTaskProxy, PbPrerequisite
from cylc.flow.network.graphql import (
    AstDocArguments, null_setter, NULL_VALUE, grow_tree
)
from cylc.flow.network.schema import schema


TASK_PROXY_PREREQS = PbTaskProxy()
TASK_PROXY_PREREQS.prerequisites.append(PbPrerequisite(expression="foo"))


@pytest.mark.parametrize(
    'query,'
    'variables,'
    'expected_variables,'
    'expected_error',
    [
        pytest.param(
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
            None,
            id="simple query with correct variables"
        ),
        pytest.param(
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
            None,
            id="query with a fragment and correct variables"
        ),
        pytest.param(
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
            ValueError,
            id="correct variable definition, but missing variable in "
               "provided values"
        )
    ]
)
def test_query_variables(
        query: str,
        variables: dict,
        expected_variables: Optional[dict],
        expected_error: Optional[Type[Exception]],
):
    """Test that query variables are parsed correctly.

    Args:
        query: a valid GraphQL query (using our schema)
        variables: map with variable values for the query
        expected_variables: expected parsed variables
        expected_error: expected error, if any
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


@pytest.mark.parametrize(
    'pre_result,'
    'expected_result',
    [
        (
            'foo',
            'foo'
        ),
        (
            [],
            NULL_VALUE
        ),
        (
            {},
            NULL_VALUE
        ),
        (
            TASK_PROXY_PREREQS.prerequisites,
            TASK_PROXY_PREREQS.prerequisites
        ),
        (
            PbTaskProxy().prerequisites,
            NULL_VALUE
        )
    ]
)
def test_null_setter(pre_result, expected_result):
    """Test the null setting of different data types/results."""
    post_result = null_setter(pre_result)
    assert post_result == expected_result


@pytest.mark.parametrize(
    'expect, tree, path, leaves',
    [
        param(
            {'foo': {'bar': {'baz': {}}}}, {}, ['foo', 'bar', 'baz'], None,
            id='fill-empty-tree'
        ),
        param(
            {'bar': {'baz': {}}}, {'bar': {'baz': {}}}, ['bar', 'baz'], None,
            id='keep-full-tree'
        ),
        param(
            {'foo': {'bar': {}, 'qux': {}}},
            {'foo': {'bar': {}}},
            ['foo', 'qux'],
            None,
            id='add-new-branch'
        ),
        param(
            {'leaves': {'foo': {}}}, {}, [], {'foo': {}},
            id='add-leaves'
        )
    ]
)
def test_grow_tree(expect, tree, path, leaves):
    grow_tree(tree, path, leaves)
    assert tree == expect
