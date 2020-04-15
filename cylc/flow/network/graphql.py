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
"""

A modification of th GraphQL Core backend:
https://github.com/graphql-python/graphql-core

GraphQL Middleware defined here also.

"""

from functools import partial
import logging

from inspect import isclass, iscoroutinefunction

from graphene.utils.str_converters import to_snake_case
from graphql.execution import ExecutionResult, execute
from graphql.execution.utils import (
    get_operation_root_type, get_field_def
)
from graphql.execution.values import get_argument_values, get_variable_values
from graphql.language.base import parse, print_ast
from graphql.language import ast
from graphql.validation import validate
from graphql.backend.base import GraphQLBackend, GraphQLDocument
from graphql.utils.base import type_from_ast
from graphql.type import get_named_type
from promise import Promise
from rx import Observable

logger = logging.getLogger(__name__)

STRIP_ARG = 'strip_null'
NULL_VALUE = None
EMPTY_VALUES = ([], {})


def grow_tree(tree, path, leaves=None):
    """Additively grows tree with leaves at terminal of new branch.

    Given existing dictionary, it follows the new path from root through
    existing trunk and without clobbering existing leaves when encountered.

    Args:
        tree (dict): Existing or new dictionary/tree.
        path (list): List of keys from root to branch end.
        leaves (dict, optional):
            Dictionary of information to put at path end.

    Returns:
        None
    """
    tree_loc = [tree, {}]
    b_1 = 0
    b_2 = 1
    for key in path:
        if key in tree_loc[b_1 % 2]:
            tree_loc[b_2 % 2] = tree_loc[b_1 % 2][key]
        else:
            tree_loc[b_1 % 2][key] = tree_loc[b_2 % 2]
        tree_loc[b_1 % 2] = {}
        b_1 += 1
        b_2 += 1
    if leaves:
        tree_loc[len(path) % 2].update(leaves)


def instantiate_middleware(middlewares):
    """Take iterable of middlewares and instantiate.

    Middleware instantiated here will not be shared amongst
    subscriptions/queries.

    """
    for middleware in middlewares:
        if isclass(middleware):
            yield middleware()
            continue
        yield middleware


def null_setter(result):
    """Set type to null if result is empty/null-like."""
    # Only set empty parents to null.
    if result in EMPTY_VALUES:
        return NULL_VALUE
    return result


# Is possible to not use middleware and do all the filtering here.
# However, middleware allows for argument of the request doc to set.
def strip_null(data):
    """Recursively strip data structure of nulls."""
    if isinstance(data, Promise):
        return data.then(strip_null)
    if isinstance(data, dict):
        return {
            key: strip_null(val)
            for key, val in data.items()
            if val is not NULL_VALUE
        }
    if isinstance(data, list):
        return [
            strip_null(val)
            for val in data
            if val is not NULL_VALUE
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


class AstDocArguments:
    """Request doc Argument inspection."""

    def __init__(self, schema, document_ast, variable_values):
        self.schema = schema
        self.operation_defs = {}
        self.fragment_defs = {}
        self.visited_fragments = set()

        for defn in document_ast.definitions:
            if isinstance(defn, ast.OperationDefinition):
                root_type = get_operation_root_type(schema, defn)
                self.operation_defs[getattr(defn.name, 'value', root_type)] = {
                    'definition': defn,
                    'parent_type': root_type,
                    'variables': get_variable_values(
                        schema,
                        defn.variable_definitions or [],
                        variable_values
                    ),
                }
            elif isinstance(defn, ast.FragmentDefinition):
                self.fragment_defs[defn.name.value] = defn

    def has_arg_val(self, arg_name, arg_value):
        """Search through document definitions for argument value.

        Args:
            arg_name (str): Field argument to search for.
            arg_value (Any): Argument value required.

        Returns:

            Boolean

        """
        try:
            for components in self.operation_defs.values():
                if self.args_selection_search(
                        components['definition'].selection_set,
                        components['variables'],
                        components['parent_type'],
                        arg_name,
                        arg_value,
                ):
                    return True
        except Exception as exc:
            import traceback
            logger.debug(traceback.format_exc())
            logger.error(exc)
        return False

    def args_selection_search(
            self, selection_set, variables, parent_type, arg_name, arg_value):
        """Recursively search through feild/fragment selection set fields."""
        for field in selection_set.selections:
            if isinstance(field, ast.FragmentSpread):
                if field.name.value in self.visited_fragments:
                    continue
                frag_def = self.fragment_defs[field.name.value]
                frag_type = type_from_ast(self.schema, frag_def.type_condition)
                if self.args_selection_search(
                        frag_def.selection_set, variables,
                        frag_type, arg_name, arg_value):
                    return True
                self.visited_fragments.add(frag_def.name)
                continue
            field_def = get_field_def(
                self.schema, parent_type, field.name.value)
            if field_def is None:
                continue
            arg_vals = get_argument_values(
                field_def.args, field.arguments, variables)
            if arg_vals.get(arg_name) == arg_value:
                return True
            if field.selection_set is None:
                continue
            if self.args_selection_search(
                    field.selection_set, variables,
                    get_named_type(field_def.type), arg_name, arg_value):
                return True
        return False


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

    # Search request docuement to determine if 'stripNull: true' is set
    # as and argument. It can not be done in the middleware, as they
    # can be Promises/futures (so may not been resolved at this point).
    variable_values = kwargs['variable_values'] or {}
    doc_args = AstDocArguments(schema, document_ast, variable_values)
    if doc_args.has_arg_val(STRIP_ARG, True):
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

    # Sometimes `next` is a Partial(coroutine) or Promise,
    # making inspection for know how to resolve it difficult.
    ASYNC_OPS = {'query', 'mutation'}

    def __init__(self):
        self.args_tree = {}
        self.tree_paths = set()
        self.field_sets = {}

    def resolve(self, next, root, info, **args):
        """Middleware resolver; handles field according to operation."""
        # GraphiQL introspection is 'query' but not async
        if getattr(info.operation.name, 'value', None) == 'IntrospectionQuery':
            return next(root, info, **args)

        path_string = f'{info.path}'
        parent_path_string = f'{info.path[:-1:]}'
        field_name = to_snake_case(info.field_name)
        # Avoid using the protobuf default if field isn't set.
        if (
                parent_path_string not in self.field_sets
                and hasattr(root, 'ListFields')
        ):
            self.field_sets[parent_path_string] = set(
                field.name
                for field, _ in root.ListFields()
            )

        # Needed for child fields that resolve without args.
        # Store arguments of parents as leaves of schema tree from path
        # to respective field.
        if STRIP_ARG in args:
            # no need to regrow the tree on every subscription push/delta
            if path_string not in self.tree_paths:
                grow_tree(self.args_tree, info.path, args)
                self.tree_paths.add(path_string)
        else:
            args[STRIP_ARG] = False
            branch = self.args_tree
            for section in info.path:
                branch = branch.get(section, {})
                if not branch:
                    break
                # Only set if present on branch section
                if STRIP_ARG in branch:
                    args[STRIP_ARG] = branch[STRIP_ARG]

        # Now flag empty fields as 'null for stripping
        if args[STRIP_ARG]:
            if (
                    hasattr(root, field_name)
                    and field_name not in self.field_sets.get(
                        parent_path_string, {field_name})
            ):
                return None
            if (
                    info.operation.operation in self.ASYNC_OPS
                    or iscoroutinefunction(next)
            ):
                return self.async_null_setter(next, root, info, **args)
            return null_setter(next(root, info, **args))

        if (
                info.operation.operation in self.ASYNC_OPS
                or iscoroutinefunction(next)
        ):
            return self.async_resolve(next, root, info, **args)
        return next(root, info, **args)

    async def async_resolve(self, next, root, info, **args):
        """Return awaited coroutine"""
        return await next(root, info, **args)

    async def async_null_setter(self, next, root, info, **args):
        """Set type to null after awaited result if empty/null-like."""
        result = await next(root, info, **args)
        return null_setter(result)
