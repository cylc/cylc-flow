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


async def test_prompt_for_running_workflow_with_no_changes(
    monkeypatch,
    caplog,
    capsys,
    log_filter,
    one_run,
    capcall,
):
    """It should reinstall and restart the workflow with no changes.

    See: https://github.com/cylc/cylc-flow/issues/6261

    We hope to get users into the habbit of "cylc vip" to create a new run,
    and "cylc vr" to contine an old one (picking up any new changes in the
    process).

    This works fine, unless there are no changes to reinstall, in which case
    the "cylc vr" command exits (nothing to do).

    The "nothing to reinstall" situation can be interpretted two ways:
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

    # answer "y" to all prompts
    def _input(prompt):
        print(prompt)
        return 'y'

    monkeypatch.setattr(
        'cylc.flow.scripts.validate_reinstall._input',
        _input,
    )

    # make it look like we are running this command in a terminal
    monkeypatch.setattr(
        'cylc.flow.scripts.validate_reinstall.is_terminal',
        lambda: True
    )
    monkeypatch.setattr(
        'cylc.flow.scripts.reinstall.is_terminal',
        lambda: True
    )

    # attempt to restart it with "cylc vr"
    ret = await vr_cli(
        vr_gop(), ValidateReinstallOptions(), one_run.id
    )
    # the workflow should reinstall
    assert ret

    # the user should have been warned that there were no changes to reinstall
    assert log_filter(caplog, contains='No changes to reinstall')

    # they should have been presented with a prompt
    # (to which we have hardcoded the response "y")
    assert 'Restart anyway?' in capsys.readouterr()[0]

    # the workflow should have restarted
    assert len(cleanup_sysargv_calls) == 1
