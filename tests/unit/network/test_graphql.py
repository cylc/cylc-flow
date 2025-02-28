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
from pytest import param
from graphql import (
    TypeInfo,
    TypeInfoVisitor,
    get_operation_ast,
    parse,
    visit
)

from cylc.flow.data_messages_pb2 import PbTaskProxy, PbPrerequisite
from cylc.flow.network.graphql import (
    CylcVisitor, null_setter, strip_null, async_next, NULL_VALUE, grow_tree
)
from cylc.flow.network.schema import schema


TASK_PROXY_PREREQS = PbTaskProxy()
TASK_PROXY_PREREQS.prerequisites.append(PbPrerequisite(expression="foo"))


@pytest.mark.parametrize(
    'query,'
    'variables,'
    'search_arg,'
    'expected_result',
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
                'arg': 'ids',
                'val': ['cylc|workflow'],
            },
            True,
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
                'arg': 'ids',
                'val': ['cylc|workflow'],
            },
            True,
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
            {
                'arg': 'ids',
                'val': None,
            },
            False,
            id="correct variable definition, but missing variable in "
               "provided values"
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
            {
                'arg': 'idfsdf',
                'val': ['cylc|workflow'],
            },
            False,
            id="correct variable definition, but wrong search argument"
        )
    ]
)
def test_query_variables(
        query: str,
        variables: dict,
        search_arg: dict,
        expected_result: bool,
):
    """Test that query variables are parsed and found correctly.

    Args:
        query: a valid GraphQL query (using our schema)
        variables: map with variable values for the query
        search_arg: argument and value to search for
        expected_result: was the argument and value found
    """
    def test():
        """Inner function to avoid duplication in if/else"""
        document = parse(query)
        type_info = TypeInfo(schema)
        cylc_visitor = CylcVisitor(
            type_info,
            variables,
            search_arg
        )
        visit(
            get_operation_ast(document),
            TypeInfoVisitor(
                type_info,
                cylc_visitor
            ),
            None
        )

        assert expected_result == cylc_visitor.arg_flag


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
    'pre_result,'
    'expected_result',
    [
        (
            'foo',
            'foo'
        ),
        (
            [NULL_VALUE],
            []
        ),
        (
            {'nothing': NULL_VALUE},
            {},
        ),
        (
            TASK_PROXY_PREREQS.prerequisites,
            TASK_PROXY_PREREQS.prerequisites
        ),
        (
            [NULL_VALUE],
            [],
        )
    ]
)
async def test_strip_null(pre_result, expected_result):
    """Test the null stripping of different result data/types."""
    # non-async
    post_result = async_next(strip_null, pre_result)
    assert post_result == expected_result

    async def async_result(result):
        return result

    # async
    async_post_result = async_next(strip_null, async_result(pre_result))
    assert await async_post_result == expected_result


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
