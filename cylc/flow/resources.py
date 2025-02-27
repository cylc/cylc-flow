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

"""Extract named resources from the cylc.flow package."""

from ansimarkup import parse
from contextlib import suppress
from pathlib import Path
from random import choice
import shutil
import sys
from typing import Optional

import cylc.flow
from cylc.flow import LOG
from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.exceptions import InputError
from cylc.flow.wallclock import get_current_time_string


RESOURCE_DIR = Path(cylc.flow.__file__).parent / 'etc'
TUTORIAL_DIR = RESOURCE_DIR / 'tutorial'
EXAMPLE_DIR = RESOURCE_DIR / 'examples'


# {resource: brief description}
RESOURCE_NAMES = {
    'syntax/cylc-mode.el': 'Emacs syntax highlighting.',
    'syntax/cylc.lang': 'Gedit (gtksourceview) syntax highlighting.',
    'syntax/cylc.xml': 'Kate syntax highlighting.',
    'cylc-completion.bash': 'Bash auto-completion for Cylc commands.',
    'cylc': 'Cylc wrapper script.',
    '!syntax/cylc.vim': 'Obsolete- use https://github.com/cylc/cylc.vim',
}
API_KEY = 'api-key'


def list_resources(write=print, headers=True):
    """Print resource names to stdout."""
    tutorials = [
        path.relative_to(RESOURCE_DIR)
        for path in TUTORIAL_DIR.iterdir()
        if path.is_dir()
    ]
    examples = [
        path.relative_to(RESOURCE_DIR)
        for path in EXAMPLE_DIR.iterdir()
        if path.is_dir()
    ]
    if headers:
        write('Resources:')
    max_len = max(len(res) for res in RESOURCE_NAMES)
    for resource, desc in RESOURCE_NAMES.items():
        if resource[0] == '!':
            # Use ! to indicated that resource is deprecated:
            resource = resource[1:]
            write(parse(
                f'<yellow>  {resource}  {" " * (max_len - len(resource))}'
                f'  # {desc}</yellow>'
            ))
        else:
            write(f'  {resource}  {" " * (max_len - len(resource))}  # {desc}')
    if headers:
        write('\nTutorials:')
    for tutorial in tutorials:
        write(f'  {tutorial}')
    write(f'  {API_KEY}')
    if headers:
        write('\nExamples:')
    for example in examples:
        write(f'  {example}')


def path_is_source_workflow(src: Path) -> bool:
    """Returns True if the src path is a Cylc workflow."""
    with suppress(ValueError):
        src.relative_to(TUTORIAL_DIR)
        return True
    with suppress(ValueError):
        src.relative_to(EXAMPLE_DIR)
        return True
    return False


def get_resources(resource: str, tgt_dir: Optional[str]):
    """Extract cylc.flow resources and write them to a target directory.

    Arguments:
        resource: path relative to RESOURCE_DIR.
        target_dir: Where to put extracted resources, created if necessary.

    """
    # get the resource path
    resource_path = Path(resource)

    if resource in ('api-key', 'tutorial/api-key'):
        print(get_api_key())
        return

    src = RESOURCE_DIR / resource_path
    if not src.exists():
        raise InputError(
            f'No such resources {resource}.'
            '\nRun `cylc get-resources --list` for resource names.'
        )

    is_source_workflow = path_is_source_workflow(src)

    # get the target path
    if not tgt_dir:
        if is_source_workflow:
            # this is a tutorial => use the primary source dir
            _tgt_dir = Path(glbl_cfg().get(['install', 'source dirs'])[0])
        else:
            # this is a regular resource => use $PWD
            _tgt_dir = Path.cwd()
    else:
        _tgt_dir = Path(tgt_dir).resolve()
    tgt = _tgt_dir / resource_path.name

    tgt = tgt.expanduser()
    tgt = tgt.resolve()

    # extract resources
    extract_resource(src, tgt, is_source_workflow)
    if is_source_workflow:
        set_api_key(tgt)


def _backup(tgt: Path) -> None:
    """Make a timestamped backup of a dir or file."""
    tstamp = get_current_time_string(use_basic_format=True)
    backup = Path(tgt).parent / (tgt.name + f'.{tstamp}')
    LOG.warning(
        'Replacing an existing cylc-tutorials folder which will'
        f' be copied to {backup}'
    )
    # NOTE: shutil interfaces don't fully support Path objects at all
    # python versions
    shutil.move(str(tgt), str(backup))


def extract_resource(
    src: Path,
    tgt: Path,
    is_source_workflow: bool = False,
) -> None:
    """Extract src into tgt.

    NOTE: src can be a dir or a file.
    """
    LOG.info(f"Extracting {src.relative_to(RESOURCE_DIR)} to {tgt}")
    if is_source_workflow and tgt.exists():
        # target exists, back up the old copy
        _backup(tgt)

    # files to exclude
    if is_source_workflow:
        excludes = [
            # test files
            '.validate',
            'reftest',
            # documentation files
            'index.rst',
        ]
    else:
        excludes = []

    # create the target directory
    try:
        tgt.parent.mkdir(parents=True, exist_ok=True)

        # NOTE: shutil interfaces don't fully support Path objects at all
        # python versions
        if src.is_dir():
            shutil.copytree(str(src), str(tgt))
        else:
            shutil.copyfile(str(src), str(tgt))
        for exclude in excludes:
            path = tgt / exclude
            if path.exists():
                path.unlink()
    except IsADirectoryError as exc:
        LOG.error(
            f'Cannot extract file {exc.filename} as there is an '
            'existing directory with the same name'
        )
        sys.exit(1)
    except FileExistsError as exc:
        LOG.error(
            f'Cannot extract directory {exc.filename} as there is an '
            'existing file with the same name'
        )
        sys.exit(1)


def get_api_key() -> str:
    """Return a DataPoint API key for tutorial use.

    Picks an API key from the file "api-keys" at random so as to spread the
    load over a larger number of keys to prevent hitting the cap with group
    sessions.
    """
    with open((TUTORIAL_DIR / 'api-keys'), 'r') as api_keys:
        return choice(list(api_keys)).strip()  # nosec
        # (the randomness of this choice is not a security concern)


def set_api_key(tgt):
    """Replace a placeholder with a real API key.

    Replaces the placeholder DATAPOINT_API_KEY with a value chosen at random
    from the file api-keys chosen.
    """
    # get the api key
    api_key = get_api_key()
    # go through all the top level files
    for path in tgt.glob('*'):
        if not path.is_dir():
            # write the file out one line at a time to a temp file
            tmp_path = path.parent / (path.name + '.tmp')
            with open(path, 'rb') as _src, open(tmp_path, 'wb+') as _tmp:
                # NOTE: open the file in bytes mode for safety
                # (prevents decode errors surfacing here)
                for line in _src:
                    _tmp.write(
                        # perform the replacement line by line
                        # (some things are easier with sed!)
                        line.replace(
                            b'DATAPOINT_API_KEY',
                            api_key.encode(),
                        )
                    )

            # then move the tmpfile over the original
            # NOTE: shutil interfaces don't fully support Path objects at all
            # python versions
            path.unlink()
            shutil.move(str(tmp_path), str(path))
