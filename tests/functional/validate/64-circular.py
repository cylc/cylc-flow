#!/usr/bin/env bash
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
# ----------------------------------------------------------------------------
# Test validation fails on bad task event handler templates.
import pytest
from cylc.flow.exceptions import (
    WorkflowConfigError,
)


def test_circular_simple_1(flow, validate):
    id_ = flow({
        'scheduler': {
            'allow implicit tasks': 'True',
        },
        'scheduling': {
            'graph': {
                'R1': 'a => a',
            },
        },
    })
    with pytest.raises(WorkflowConfigError, match=(
        r'self-edge detected: a:succeeded => a.*'
    )):
        validate(id_)


def test_circular_simple_2(flow, validate):
    id_ = flow({
        'scheduler': {
            'allow implicit tasks': 'True',
        },
        'scheduling': {
            'graph': {
                'R1': 'a => b => c => d => a => z',
            },
        },
    })
    with pytest.raises(WorkflowConfigError, match=(
        r'circular edges detected:.*'
    )):
        validate(id_)


def test_circular_simple_fam(flow, validate):
    id_ = flow({
        'scheduler': {
            'allow implicit tasks': 'True',
        },
        'scheduling': {
            'graph': {
                'R1': 'FAM:succeed-all => f & g => z',
            },
        },
        'runtime': {
            'FAM': {
            },
            'f,g,h': {
                'inherit': 'FAM',
            },
        },
    })
    with pytest.raises(WorkflowConfigError, match=(
        r'self-edge detected:.*'
    )):
        validate(id_)


def test_circular_intercycle_1(flow, validate):
    id_ = flow({
        'scheduler': {
            'allow implicit tasks': 'True',
            'cycle point format': '%Y',
        },
        'scheduling': {
            'initial cycle point': '2001',
            'final cycle point': '2010',
            'graph': {
                'P1Y': ("'''"
                        "\na[-P1Y] => a"
                        "\na[+P1Y] => a"
                        "\n'''"),
            },
        },
    })
    with pytest.raises(WorkflowConfigError, match=(
        r'circular edges detected:.*'
    )):
        validate(id_)
