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

import asyncio
import sys
from typing import (
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
    Type,
    Union,
)

from ansimarkup import ansiprint

from cylc.flow.async_util import unordered_map
from cylc.flow.exceptions import (
    CylcError,
    WorkflowStopped,
)
import cylc.flow.flags
from cylc.flow.id_cli import parse_ids_async
from cylc.flow.terminal import DIM


def call_multi(*args, **kwargs):
    """Call a function for each workflow in a list of IDs.

    See call_multi_async for arg docs.
    """
    return asyncio.run(call_multi_async(*args, **kwargs))


async def call_multi_async(
    fcn,
    *ids,
    constraint='tasks',
    report: Optional[
        # report(response: dict) -> (stdout, stderr, success)
        Callable[[dict], Tuple[Optional[str], Optional[str], bool]]
    ] = None,
    max_workflows=None,
    max_tasks=None,
    success_exceptions: Optional[Tuple[Type]] = None,
) -> Dict[str, bool]:
    """Call a function for each workflow in a list of IDs.

    Args:
        fcn:
            The function to call for each workflow.
        ids:
            The list of universal identifiers to parse.
        constraint:
            The type of objects IDs must identify.

            tasks:
                For task-like objects i.e. cycles/tasks/jobs.
            workflow:
                For workflow-like objects i.e. [user/]workflows.
            mixed:
                No constraint.
        report:
            The default reporter inspects the returned GraphQL status
            extracting command outcome from the "response" field.
            This reporter can be overwritten using the report kwarg.

            Reporter functions are provided with the "response". They must
            return the outcome of the operation and may also return stdout/err
            text which will be written to the terminal.
        success_exceptions:
            An optional tuple of exceptions that can convey success outcomes.
            E.G. a "WorkflowStopped" exception indicates an error state for
            "cylc broadcast" but a success state for "cylc stop".

    Returns:
        {workflow_id: outcome}

    """
    # parse ids
    workflow_args, multi_mode = await parse_ids_async(
        *ids,
        src=False,
        constraint=constraint,
        max_workflows=max_workflows,
        max_tasks=max_tasks,
        match_workflows=True,
    )

    # configure reporting
    if not report:
        report = _report
    if multi_mode:
        reporter = _report_multi
    else:
        reporter = _report_single

    if constraint == 'workflows':
        workflow_args = {
            workflow_id: []
            for workflow_id in workflow_args
        }

    # run coros
    results: Dict[str, bool] = {}
    async for (workflow_id, *args), response in unordered_map(
        fcn,
        (
            (workflow_id, *args)
            for workflow_id, args in workflow_args.items()
        ),
        # return exceptions rather than raising them
        # (this way if one command errors, others may still run)
        wrap_exceptions=True,
    ):
        # get outcome
        out, err, outcome = _process_response(
            report, response, success_exceptions
        )
        # report outcome
        reporter(workflow_id, out, err)
        results[workflow_id] = outcome

    return results


def _report_multi(
    workflow: str, out: Optional[str], err: Optional[str]
) -> None:
    """Report a response for a multi-workflow operation.

    This is called once for each workflow the operation is called against.
    """
    msg = f'<b>{workflow}</b>:'
    if out:
        out = out.replace('\n', '\n    ')  # indent
        msg += ' ' + out
        ansiprint(msg)

    if err:
        err = err.replace('\n', '\n    ')  # indent
        if not out:
            err = f'{msg} {err}'
        ansiprint(err, file=sys.stdout)


def _report_single(
    workflow: str, out: Optional[str], err: Optional[str]
) -> None:
    """Report the response for a single-workflow operation."""
    if out:
        ansiprint(out)
    if err:
        ansiprint(err, file=sys.stderr)


def _process_response(
    report: Callable,
    response: Union[dict, Exception],
    success_exceptions: Optional[Tuple[Type]] = None,
) -> Tuple[Optional[str], Optional[str], bool]:
    """Handle exceptions and return processed results.

    If the response is an exception, return an appropriate error message,
    otherwise run the reporter and return the result.

    Args:
        response:
            The GraphQL response.
        report:
            The reporter function for extracting the result from the provided
            response.
        success_exceptions:
            An optional tuple of exceptions that can convey success outcomes.
            E.G. a "WorkflowStopped" exception indicates an error state for
            "cylc broadcast" but a success state for "cylc stop".

    Returns:
        (stdout, stderr, outcome)

    """
    if success_exceptions and isinstance(response, success_exceptions):
        # an exception was raised, however, that exception indicates a success
        # outcome in this case
        out = f'<green>{response.__class__.__name__}: {response}</green>'
        err = None
        outcome = True

    elif isinstance(response, WorkflowStopped):
        # workflow stopped -> report differently to other CylcErrors
        out = None
        err = f'<yellow>{response.__class__.__name__}: {response}</yellow>'
        outcome = False

    elif isinstance(response, CylcError):
        # exception -> report error
        if cylc.flow.flags.verbosity > 1:  # debug mode
            raise response from None
        out = None
        err = f'<red>{response.__class__.__name__}: {response}</red>'
        outcome = False

    elif isinstance(response, Exception):
        # unexpected error -> raise
        raise response

    else:
        try:
            # run the reporter to extract the operation outcome
            out, err, outcome = report(response)
        except Exception as exc:
            # an exception was raised in the reporter -> report this error the
            # same was as an error in the response
            return _process_response(report, exc, success_exceptions)

    return out, err, outcome


def _report(
    response: Union[dict, list],
) -> Tuple[Optional[str], Optional[str], bool]:
    """Report the result of a GraphQL operation.

    This analyses GraphQL mutation responses to determine the outcome.

    Args:
        response: The workflow server response (NOT necessarily conforming to
        GraphQL execution result spec).

    Returns:
        (stdout, stderr, outcome)

    """
    try:
        ret: List[Tuple[Optional[str], Optional[str], bool]] = []
        if not isinstance(response, dict):
            if isinstance(response, list) and response[0].get('error'):
                # If operating on workflow running in older Cylc version,
                # may get a error response like [{'error': '...'}]
                raise Exception(response)
            raise Exception(f"Unexpected response: {response}")
        for mutation_response in response.values():
            # extract the result of each mutation result in the response
            success, msg = mutation_response['result'][0]['response']
            out = None
            err = None
            if success:
                # mutation succeeded
                out = '<green>Command queued</green>'
                if cylc.flow.flags.verbosity > 0:  # verbose mode
                    out += f' <{DIM}>id={msg}</{DIM}>'
            else:
                # mutation failed
                err = f'<red>{msg}</red>'
            ret.append((out, err, success))

        if len(ret) > 1:
            # NOTE: at present we only support one mutation per operation at
            # cylc-flow, however, multi-mutation operations can be actioned via
            # cylc-uiserver
            raise NotImplementedError(
                'Cannot process multiple mutations in one operation.'
            )

        if len(ret) == 1:
            return ret[0]

        # error extracting result from GraphQL response
        raise Exception(response)

    except Exception as exc:
        # response returned is not in the expected format - this shouldn't
        # happen but we need to protect against it
        err_msg = ''
        if cylc.flow.flags.verbosity > 0:  # verbose mode
            # print the full result to stderr
            err_msg += f'\n    <{DIM}>response={response}</{DIM}>'
        return (
            None,
            (
                '<red>Error processing command:\n'
                + f'    {exc.__class__.__name__}: {exc}</red>'
                + err_msg
            ),
            False,
        )
