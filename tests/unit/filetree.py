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

"""Utilities for testing workflow directory structure.

(There should be no tests in this module.)

A filetree is represented by a dict like so:
    {
        # Dirs are represented by dicts (which are also sub-filetrees):
        'dir': {
            'another-dir': {
                # Files are represented by None:
                'file.txt': None
            }
        },
        # Symlinks are represented by the Symlink class, with the target
        # represented by the relative path from the tmp_path directory:
        'symlink': Symlink('dir/another-dir')
    }
"""

from pathlib import Path, PosixPath
from typing import Any, Dict, List


class Symlink(PosixPath):
    """A class to represent a symlink target."""
    ...


def create_filetree(
    filetree: Dict[str, Any], location: Path, root: Path
) -> None:
    """Create the directory structure represented by the filetree dict.

    Args:
        filetree: The filetree to create.
        location: The absolute path in which to create the filetree.
        root: The top-level dir from which relative symlink targets are
            located (typically tmp_path).
    """
    for name, entry in filetree.items():
        path = location / name
        if isinstance(entry, dict):
            path.mkdir(exist_ok=True)
            create_filetree(entry, path, root)
        elif isinstance(entry, Symlink):
            path.symlink_to(root / entry)
        else:
            path.touch()


def get_filetree_as_list(
    filetree: Dict[str, Any], location: Path
) -> List[str]:
    """Return a list of the paths in a filetree.

    Args:
        filetree: The filetree to listify.
        location: The absolute path to the filetree.
    """
    ret: List[str] = []
    for name, entry in filetree.items():
        path = location / name
        ret.append(str(path))
        if isinstance(entry, dict):
            ret.extend(get_filetree_as_list(entry, path))
    return ret


FILETREE_1 = {
    'cylc-run': {
        'foo': {
            'bar': {
                '.service': {
                    'db': None,
                },
                'flow.cylc': None,
                'log': Symlink('sym/cylc-run/foo/bar/log'),
                'mirkwood': Symlink('you-shall-not-pass/mirkwood'),
                'rincewind.txt': Symlink('you-shall-not-pass/rincewind.txt'),
            },
        },
    },
    'sym': {
        'cylc-run': {
            'foo': {
                'bar': {
                    'log': {
                        'darmok': Symlink('you-shall-not-pass/darmok'),
                        'temba.txt': Symlink('you-shall-not-pass/temba.txt'),
                        'bib': {
                            'fortuna.txt': None,
                        },
                    },
                },
            },
        },
    },
    'you-shall-not-pass': {  # Nothing in here should get deleted
        'darmok': {
            'jalad.txt': None,
        },
        'mirkwood': {
            'spiders.txt': None,
        },
        'rincewind.txt': None,
        'temba.txt': None,
    },
}

FILETREE_2 = {
    'cylc-run': {'foo': {'bar': Symlink('sym-run/cylc-run/foo/bar')}},
    'sym-run': {
        'cylc-run': {
            'foo': {
                'bar': {
                    '.service': {
                        'db': None,
                    },
                    'flow.cylc': None,
                    'share': Symlink('sym-share/cylc-run/foo/bar/share'),
                },
            },
        },
    },
    'sym-share': {
        'cylc-run': {
            'foo': {
                'bar': {
                    'share': {
                        'cycle': Symlink(
                            'sym-cycle/cylc-run/foo/bar/share/cycle'
                        ),
                    },
                },
            },
        },
    },
    'sym-cycle': {
        'cylc-run': {
            'foo': {
                'bar': {
                    'share': {
                        'cycle': {
                            'macklunkey.txt': None,
                        },
                    },
                },
            },
        },
    },
    'you-shall-not-pass': {},
}

FILETREE_3 = {
    'cylc-run': {
        'foo': {
            'bar': Symlink('sym-run/cylc-run/foo/bar'),
        },
    },
    'sym-run': {
        'cylc-run': {
            'foo': {
                'bar': {
                    '.service': {
                        'db': None,
                    },
                    'flow.cylc': None,
                    'share': {
                        'cycle': Symlink(
                            'sym-cycle/cylc-run/foo/bar/share/cycle'
                        ),
                    },
                },
            },
        },
    },
    'sym-cycle': {
        'cylc-run': {
            'foo': {
                'bar': {
                    'share': {
                        'cycle': {
                            'sokath.txt': None,
                        },
                    },
                },
            },
        },
    },
    'you-shall-not-pass': {},
}

FILETREE_4 = {
    'cylc-run': {
        'foo': {
            'bar': {
                '.service': {
                    'db': None,
                },
                'flow.cylc': None,
                'share': {
                    'cycle': Symlink('sym-cycle/cylc-run/foo/bar/share/cycle'),
                },
            },
        },
    },
    'sym-cycle': {
        'cylc-run': {
            'foo': {
                'bar': {
                    'share': {
                        'cycle': {
                            'kiazi.txt': None,
                        },
                    },
                },
            },
        },
    },
    'you-shall-not-pass': {},
}
