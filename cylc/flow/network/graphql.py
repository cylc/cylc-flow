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
"""

GraphQL Middleware defined here also.

"""

from functools import partial
from inspect import isclass, iscoroutinefunction
import logging
from typing import TYPE_CHECKING, Any, Dict, Tuple, Union

from graphene.utils.str_converters import to_snake_case
from graphql.execution.utils import (
    get_operation_root_type, get_field_def
)
from graphql.execution import ExecutionResult
from graphql.execution.values import get_argument_values, get_variable_values
from graphql.language.base import parse, print_ast
from graphql.language import ast
from graphql.backend.base import GraphQLBackend, GraphQLDocument
from graphql.backend.core import execute_and_validate
from graphql.utils.base import type_from_ast
from graphql.type.definition import get_named_type
from promise import Promise
from rx import Observable

from cylc.flow.network.schema import NODE_MAP

if TYPE_CHECKING:
    from graphql.language.ast import Document
    from graphql.type.schema import GraphQLSchema


logger = logging.getLogger(__name__)

STRIP_ARG = 'strip_null'
NULL_VALUE = None
EMPTY_VALUES: Tuple[list, dict] = ([], {})
STRIP_OPS = {'query', 'subscription'}


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
    for loc, key in enumerate(path):
        if key in tree_loc[loc % 2]:  # noqa: SIM401
            tree_loc[(loc + 1) % 2] = tree_loc[loc % 2][key]
        else:
            tree_loc[loc % 2][key] = tree_loc[(loc + 1) % 2]
        tree_loc[loc % 2] = {}
    if leaves:
        tree_loc[len(path) % 2].update({'leaves': leaves})


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
    try:
        if result in EMPTY_VALUES:
            return NULL_VALUE
    except TypeError:
        # If field is a repeated composite field convert to list.
        if not result:
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


def format_execution_result(
    result: Union[ExecutionResult, Dict[str, Any]]
) -> Dict[str, Any]:
    if isinstance(result, ExecutionResult):
        result = result.to_dict()
    return strip_null(result)


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
                definition_variables = defn.variable_definitions or []
                if definition_variables:
                    def_var_names = {
                        v.variable.name.value
                        for v in definition_variables
                    }
                    var_names_diff = def_var_names.difference({
                        k
                        for k in variable_values
                        if k in def_var_names
                    })
                    # check if we are missing some of the definition variables
                    if var_names_diff:
                        msg = (f'Please check your query variables. The '
                               f'following variables are missing: '
                               f'[{", ".join(var_names_diff)}]')
                        raise ValueError(msg)
                self.operation_defs[getattr(defn.name, 'value', root_type)] = {
                    'definition': defn,
                    'parent_type': root_type,
                    'variables': get_variable_values(
                        schema,
                        definition_variables,
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
        for components in self.operation_defs.values():
            defn = components['definition']
            if (
                    defn.operation not in STRIP_OPS
                    or getattr(
                        defn.name, 'value', None) == 'IntrospectionQuery'
            ):
                continue
            if self.args_selection_search(
                    components['definition'].selection_set,
                    components['variables'],
                    components['parent_type'],
                    arg_name,
                    arg_value,
            ):
                return True
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


def execute_and_validate_and_strip(
    schema: 'GraphQLSchema',
    document_ast: 'Document',
    *args: Any,
    **kwargs: Any
) -> Union[ExecutionResult, Observable]:
    """Wrapper around graphql ``execute_and_validate()`` that adds
    null stripping."""
    result = execute_and_validate(schema, document_ast, *args, **kwargs)
    # Search request document to determine if 'stripNull: true' is set
    # as and argument. It can not be done in the middleware, as they
    # can be Promises/futures (so may not been resolved at this point).
    variable_values = kwargs['variable_values'] or {}
    doc_args = AstDocArguments(schema, document_ast, variable_values)
    if doc_args.has_arg_val(STRIP_ARG, True):
        if kwargs.get('return_promise', False) and hasattr(result, 'then'):
            return result.then(null_stripper)  # type: ignore[union-attr]
        return null_stripper(result)
    return result


class CylcGraphQLBackend(GraphQLBackend):
    """Return a GraphQL document using the default
    graphql executor with optional null-stripping of result.

    The null value stripping of result is triggered by the presence
    of argument & value "stripNull: true" in any field.

    This is a modification of GraphQLCoreBackend found within:
        https://github.com/graphql-python/graphql-core-legacy
    (graphql-core==2.3.2)

    Args:

        executor (object): Executor used in evaluating the resolvers.

    """

    def __init__(self, executor=None):
        self.execute_params = {"executor": executor}

    def document_from_string(self, schema, document_string):
        """Parse string and setup request document for execution.

        Args:

            schema (graphql.GraphQLSchema):
                Schema definition object
            document_string (str):
                Request query/mutation/subscription document.

        Returns:

            graphql.GraphQLDocument

        """
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
                execute_and_validate_and_strip,
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

    def resolve(self, next_, root, info, **args):
        """Middleware resolver; handles field according to operation."""
        # GraphiQL introspection is 'query' but not async
        if getattr(info.operation.name, 'value', None) == 'IntrospectionQuery':
            return next_(root, info, **args)

        if info.operation.operation in STRIP_OPS:
            path_string = f'{info.path}'
            # Needed for child fields that resolve without args.
            # Store arguments of parents as leaves of schema tree from path
            # to respective field.
            # no need to regrow the tree on every subscription push/delta
            if args and path_string not in self.tree_paths:
                grow_tree(self.args_tree, info.path, args)
                self.tree_paths.add(path_string)
            if STRIP_ARG not in args:
                branch = self.args_tree
                for section in info.path:
                    if section not in branch:
                        break
                    branch = branch[section]
                    # Only set if present on branch section
                    if 'leaves' in branch and STRIP_ARG in branch['leaves']:
                        args[STRIP_ARG] = branch['leaves'][STRIP_ARG]

            # Now flag empty fields as null for stripping
            if args.get(STRIP_ARG, False):
                field_name = to_snake_case(info.field_name)

                # Clear field set so recreated via first child field,
                # as path may be a parent.
                # Done here as parent may be in NODE_MAP
                if path_string in self.field_sets:
                    del self.field_sets[path_string]

                # Avoid using the protobuf default if field isn't set.
                if (
                    hasattr(root, 'ListFields')
                    and hasattr(root, field_name)
                    and get_named_type(info.return_type).name not in NODE_MAP
                ):

                    # Gather fields set in root
                    parent_path_string = f'{info.path[:-1:]}'
                    stamp = getattr(root, 'stamp', '')
                    if (
                        parent_path_string not in self.field_sets
                        or self.field_sets[
                            parent_path_string]['stamp'] != stamp
                    ):
                        self.field_sets[parent_path_string] = {
                            'stamp': stamp,
                            'fields': {
                                field.name
                                for field, _ in root.ListFields()
                            }
                        }

                    if (
                        parent_path_string in self.field_sets
                        and field_name not in self.field_sets[
                            parent_path_string]['fields']
                    ):
                        return None
                # Do not resolve subfields of an empty type
                # by setting as null in parent/root.
                elif isinstance(root, dict) and field_name in root:
                    field_value = root[field_name]
                    if (
                        field_value in EMPTY_VALUES
                        or (
                            hasattr(field_value, 'ListFields')
                            and not field_value.ListFields()
                        )
                    ):
                        return None
                if (
                    info.operation.operation in self.ASYNC_OPS
                    or iscoroutinefunction(next_)
                ):
                    return self.async_null_setter(next_, root, info, **args)
                return null_setter(next_(root, info, **args))

        if (
            info.operation.operation in self.ASYNC_OPS
            or iscoroutinefunction(next_)
        ):
            return self.async_resolve(next_, root, info, **args)
        return next_(root, info, **args)

    async def async_resolve(self, next_, root, info, **args):
        """Return awaited coroutine"""
        return await next_(root, info, **args)

    async def async_null_setter(self, next_, root, info, **args):
        """Set type to null after awaited result if empty/null-like."""
        result = await next_(root, info, **args)
        return null_setter(result)
