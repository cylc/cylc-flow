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

import cylc
from cylc.flow.task_remote_mgr import (
    REMOTE_FILE_INSTALL_DONE,
    REMOTE_FILE_INSTALL_FAILED
)


async def test_remote_tidy(
    flow,
    scheduler,
    start,
    mock_glbl_cfg,
    one_conf,
    monkeypatch
):
    """Remote tidy gets platforms for install targets.

    In particular, referencing https://github.com/cylc/cylc-flow/issues/5429,
    ensure that install targets defined implicitly by platform name are found.

    Mock remote init map:
        - Include an install target (quiz) with
          message != REMOTE_FILE_INSTALL_DONE to ensure that
          this is picked out.
        - Install targets where we can get a platform
          - foo - Install target is implicitly the platfrom name.
          - bar9 - The install target is implicitly the plaform name,
            and the platform name matches a platform regex.
          - baz - Install target is set explicitly.
        - An install target (qux) where we cannot get a platform: Ensure
          that we get the desired error.

    Test that platforms with no good hosts (no host not in bad hosts).
    """
    # Monkeypatch away subprocess.Popen calls - prevent any interaction with
    # remotes actually happening:
    class MockProc:
        def __init__(self, *args, **kwargs):
            self.poll = lambda: True
            if (
                'baum' in args[0]
                or 'bay' in args[0]
            ):
                self.returncode = 255
            else:
                self.returncode = 0
            self.communicate = lambda: ('out', 'err')

    monkeypatch.setattr(
        cylc.flow.task_remote_mgr,
        'Popen',
        lambda *args, **kwargs: MockProc(*args, **kwargs)
    )

    # Monkeypath function to add a sort order which we don't need in the
    # real code but rely to prevent the test becoming flaky:
    def mock_get_install_target_platforms_map(*args, **kwargs):
        """Add sort to original function to ensure test consistency"""
        from cylc.flow.platforms import get_install_target_to_platforms_map
        result = get_install_target_to_platforms_map(*args, **kwargs)
        sorted_result = {}
        for key in sorted(result):
            sorted_result[key] = sorted(
                result[key], key=lambda x: x['name'], reverse=True)
        return sorted_result

    monkeypatch.setattr(
        cylc.flow.task_remote_mgr,
        'get_install_target_to_platforms_map',
        mock_get_install_target_platforms_map
    )

    # Set up global config
    mock_glbl_cfg(
        'cylc.flow.platforms.glbl_cfg',
        '''
            [platforms]
                [[foo]]
                    # install target = foo  (implicit)
                    # hosts = foo  (implicit)
                [[bar.]]
                    # install target = bar1 to bar9 (implicit)
                    # hosts = bar1 to bar9 (implicit)
                [[baz]]
                    install target = baz
                    # baum and bay should be uncontactable:
                    hosts = baum, bay, baz
                    [[[selection]]]
                        method = definition order
                [[notthisone]]
                    install target = baz
                    hosts = baum, bay
                [[bay]]
        ''',
    )

    # Get a scheduler:
    id_ = flow(one_conf)
    schd = scheduler(id_)
    async with start(schd) as log:
        # Write database with 6 tasks using 3 platforms:
        platforms = ['baz', 'bar9', 'foo', 'notthisone', 'bay']
        line = r"('', '', {}, 0, 1, '', '', 0,'', '', '', 0, '', '{}', 4, '')"
        stmt = r"INSERT INTO task_jobs VALUES" + r','.join([
            line.format(i, platform) for i, platform in enumerate(platforms)
        ])
        schd.workflow_db_mgr.pri_dao.connect().execute(stmt)
        schd.workflow_db_mgr.pri_dao.connect().commit()

        # Mock a remote init map.
        schd.task_job_mgr.task_remote_mgr.remote_init_map = {
            'baz': REMOTE_FILE_INSTALL_DONE,      # Should match platform baz
            'bar9': REMOTE_FILE_INSTALL_DONE,     # Should match platform bar.
            'foo': REMOTE_FILE_INSTALL_DONE,      # Should match plaform foo
            'qux': REMOTE_FILE_INSTALL_DONE,      # Should not match a plaform
            'quiz': REMOTE_FILE_INSTALL_FAILED,   # Should not be considered
            'bay': REMOTE_FILE_INSTALL_DONE,      # Should return NoPlatforms
        }

        # Clear the log, run the test:
        log.clear()
        schd.task_job_mgr.task_remote_mgr.bad_hosts.update(['baum', 'bay'])
        schd.task_job_mgr.task_remote_mgr.remote_tidy()
        pass

    records = [str(r.msg) for r in log.records]

    # We can't get qux, no defined platform has a matching install target:
    qux_msg = 'No platforms available to remote tidy install targets:\n * qux'
    assert qux_msg in records

    # We can get foo bar baz, and we try to remote tidy them.
    # (This will ultimately fail, but past the point we are testing).
    for target in ['foo', 'bar9', 'baz']:
        msg = f'platform: {target} - remote tidy (on {target})'
        assert msg in records

    # We haven't done anything with Quiz because we're only looking
    # at cases where platform == REMOTE_FILE_INSTALL_DONE
    assert not [r for r in records if 'quiz' in r]

    notthisone_msg = (
        'platform: notthisone - clean up did not complete'
        '\nUnable to find valid host for notthisone'
    )
    assert notthisone_msg in records

    assert 'Unable to find a platform from install target bay.' in records
