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


import os.path
from pathlib import Path
from typing import Optional

import pytest

from cylc.flow.scripts.install import get_source_location


@pytest.mark.parametrize(
    'path, expected',
    [
        pytest.param(
            'isla/nublar', '{cylc_src}/isla/nublar',
            id="implicit relative"
        ),
        pytest.param(
            './isla/nublar', '{cwd}/isla/nublar',
            id="explicit relative"
        ),
        pytest.param(
            '/welcome/to/jurassic/park', '/welcome/to/jurassic/park',
            id="absolute"
        ),
        pytest.param(
            None, '{cwd}',
            id="None"
        ),
        pytest.param(
            '.', '{cwd}',
            id="dot"
        ),
        pytest.param(
            '$GENNARO/coupon-day', '{env_var}/coupon-day',
            id="env var expanded"
        ),
    ]
)
def test_get_source_location(
    path: Optional[str],
    expected: str,
    monkeypatch: pytest.MonkeyPatch
):
    # Setup
    mock_cylc_src = '/ingen/cylc-src'
    monkeypatch.setattr(
        'cylc.flow.scripts.install.search_install_source_dirs',
        lambda x: Path(mock_cylc_src, x)
    )
    mock_env_var = '/donald/gennaro'
    monkeypatch.setenv('GENNARO', mock_env_var)
    expected = expected.format(
        cwd=Path.cwd(),
        cylc_src=mock_cylc_src,
        env_var=mock_env_var,
    )
    # Test
    assert get_source_location(path) == Path(expected)
    assert os.path.isabs(expected)
