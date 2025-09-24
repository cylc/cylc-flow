#!/usr/bin/env python3

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

from cylc.flow.option_parsers import Options
from cylc.flow.scripts.validate_reinstall import (
    get_option_parser as vr_gop,
    vr_cli,
)

ValidateReinstallOptions = Options(vr_gop())


def answer_prompts(monkeypatch, *responses):
    """Hardcode responses to "cylc vr" interactive prompts."""
    # make it look like we are running this command in a terminal
    monkeypatch.setattr(
        'cylc.flow.scripts.validate_reinstall.is_terminal',
        lambda: True
    )
    monkeypatch.setattr(
        'cylc.flow.scripts.reinstall.is_terminal',
        lambda: True
    )

    # patch user input
    count = -1

    def _input(prompt):
        nonlocal count, responses
        responses = responses
        count += 1
        print(prompt)  # send the prompt to stdout for testing
        return responses[count]

    monkeypatch.setattr(
        'cylc.flow.scripts.validate_reinstall._input',
        _input,
    )
    monkeypatch.setattr(
        'cylc.flow.scripts.reinstall._input',
        _input,
    )


async def test_prompt_for_running_workflow_with_no_changes(
    monkeypatch,
    capsys,
    one_run,
    capcall,
):
    """It should reinstall and restart the workflow with no changes.

    See: https://github.com/cylc/cylc-flow/issues/6261

    We hope to get users into the habit of "cylc vip" to create a new run,
    and "cylc vr" to contine an old one (picking up any new changes in the
    process).

    If there are no changes to reinstall (or if the user chooses not to
    resintall) the "cylc vr" prompts whether to continue or do nothing.

    The "nothing to reinstall" situation can be interpreted two ways:
    1. Unexpected error, the user expected there to be something to reinstall,
       but there wasn't. E.g, they forgot to press save.
    2. Unexpected annoyance, I wanted to restart the workflow, just do it.

    To handle this we explain that there are no changes to reinstall and
    prompt the user to see if they want to press save or restart the workflow.
    """
    # disable the clean_sysargv logic (this interferes with other tests)
    cleanup_sysargv_calls = capcall(
        'cylc.flow.scripts.validate_reinstall.cleanup_sysargv'
    )

    # answer "y" to prompt
    answer_prompts(monkeypatch, 'n', 'y')

    # attempt to restart it with "cylc vr"
    ret = await vr_cli(
        vr_gop(), ValidateReinstallOptions(), one_run
    )
    # the workflow should reinstall
    assert ret

    # the user should have been warned that there were no changes to reinstall
    outerr = capsys.readouterr()[0]
    assert 'Reinstall would make the above changes' in outerr

    # they should have been presented with a prompt
    # (to which we have hardcoded the response "y")
    assert 'Restart anyway?' in outerr

    # the workflow should have restarted
    assert len(cleanup_sysargv_calls) == 1


async def test_reinstall_abort(
    monkeypatch,
    capsys,
    one_run,
):
    """It should abort reinstallation according to user prompt."""
    # answer 'n' to prompt
    answer_prompts(monkeypatch, 'n', 'n')

    # attempt to restart it with "cylc vr"
    ret = await vr_cli(
        vr_gop(), ValidateReinstallOptions(), one_run
    )
    assert ret is False

    # they should have been presented with a prompt
    # (to which we have hardcoded the response "n")
    assert 'Continue' in capsys.readouterr()[0]
