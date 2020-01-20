# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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
"""

A modification of th GraphQL Core backend:
https://github.com/graphql-python/graphql-core

GraphQL Middleware defined here also.

"""
from functools import partial
import logging

from graphql.execution import ExecutionResult, execute
from graphql.language.base import parse, print_ast
from graphql.language import ast
from graphql.validation import validate
from graphql.backend.base import GraphQLBackend, GraphQLDocument
from rx import Observable

logger = logging.getLogger(__name__)


# Is possible to not use middleware and do all the filtering here.
# However, middleware allows for argument of the request doc to set.
def strip_null(data):
    """Recursively strip data structure of nulls."""
    if isinstance(data, dict):
        return {
            key: strip_null(val)
            for key, val in data.items()
            if val is not None
        }
    if isinstance(data, list):
        return [
            strip_null(val)
            for val in data
            if val is not None
        ]
    return data


def attr_strip_null(result):
    """Work on the attribute/data of ExecutionResult if present."""
    if hasattr(result, 'data'):
        result.data = strip_null(result.data)
        return result
    return strip_null(result)


def null_stripper(exe_result):
    """Strip nulls in accordance with type of execution result."""
    if isinstance(exe_result, Observable):
        return exe_result.map(attr_strip_null)
    if not exe_result.errors:
        return attr_strip_null(exe_result)
    return exe_result


def execute_and_validate(
        schema,  # type: GraphQLSchema
        document_ast,  # type: Document
        *args,  # type: Any
        **kwargs  # type: Any
):
    # type: (...) -> Union[ExecutionResult, Observable]
    """Validate schema, and execute request doc against it."""
    do_validation = kwargs.get("validate", True)
    if do_validation:
        validation_errors = validate(schema, document_ast)
        if validation_errors:
            return ExecutionResult(errors=validation_errors, invalid=True)

    result = execute(schema, document_ast, *args, **kwargs)

    if kwargs.get('strip_null', False):
        if kwargs.get('return_promise', False):
            return result.then(null_stripper)
        return null_stripper(result)
    return result


class GraphQLCoreBackend(GraphQLBackend):
    """GraphQLCoreBackend will return a document using the default
    graphql executor"""

    def __init__(self, executor=None):
        # type: (Optional[Any]) -> None
        self.execute_params = {"executor": executor}

    def document_from_string(self, schema, document_string):
        # type: (GraphQLSchema, Union[Document, str]) -> GraphQLDocument
        """Parse string and setup request docutment for execution."""
        if isinstance(document_string, ast.Document):
            document_ast = document_string
            document_string = print_ast(document_ast)
        else:
            if not isinstance(document_string, str):
                logger.error("The query must be a string")
            document_ast = parse(document_string)
        return GraphQLDocument(
            schema=schema,
            document_string=document_string,
            document_ast=document_ast,
            execute=partial(
                execute_and_validate,
                schema,
                document_ast,
                **self.execute_params
            ),
        )


# -- Middleware --

class IgnoreFieldMiddleware:
    """Set to null/None type undesired field values for stripping."""

    ALLOW_TYPES = (0, 0., False)

    def resolve(self, next, root, info, **args):
        """Middleware resolver; handles field according to operation."""
        if getattr(info.operation.name, 'value', None) == 'IntrospectionQuery':
            return next(root, info, **args)
        if info.operation.operation == 'query':
            return self.async_null_setter(next, root, info, **args)
        if info.operation.operation == 'subscription':
            return self.null_setter(next(root, info, **args))
        if info.operation.operation == 'mutation':
            return self.async_resolve(next, root, info, **args)
        return next(root, info, **args)

    async def async_resolve(self, next, root, info, **args):
        """Return awaited coroutine"""
        return await next(root, info, **args)

    async def async_null_setter(self, next, root, info, **args):
        """Set type to null after awaited result if empty/null-like."""
        result = await next(root, info, **args)
        return self.null_setter(result)

    def null_setter(self, result):
        """Set type to null if result is empty/null-like."""
        # If result is not empty... could be some other condition.
        # excluded False, as could be a flag turned off.
        if result or result in self.ALLOW_TYPES:
            return result
        return None
