# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import imp
import os
import mock

from conftest import hg_out

mozphab = imp.load_source(
    "mozphab", os.path.join(os.path.dirname(__file__), os.path.pardir, "moz-phab")
)
mozphab.SHOW_SPINNER = False


arc_call_conduit = mock.Mock()
arc_call_conduit.return_value = [{"userName": "alice", "phid": "PHID-USER-1"}]

call_conduit = mock.Mock()
call_conduit.side_effect = ({}, [{"userName": "alice", "phid": "PHID-USER-1"}])

check_call_by_line = mock.Mock()
check_call_by_line.return_value = ["Revision URI: http://example.test/D123"]


def test_submit_create(in_process, hg_repo_path):
    testfile = hg_repo_path / "X"
    testfile.write_text(u"a")
    hg_out("add")
    hg_out("commit", "--message", "A r?alice")

    mozphab.main(["submit", "--yes", "--bug", "1"])

    log = hg_out("log", "--template", r"{desc}\n", "--rev", ".")
    expected = """
Bug 1 - A r?alice

Differential Revision: http://example.test/D123
"""
    assert log.strip() == expected.strip()


def test_submit_update(in_process, hg_repo_path):
    call_conduit.reset_mock()
    call_conduit.side_effect = (
        {},
        {
            "data": [
                {
                    "id": 123,
                    "phid": "PHID-REV-1",
                    "fields": {"bugzilla.bug-id": "1"},
                    "attachments": {"reviewers": {"reviewers": []}},
                }
            ]
        },  # get reviewers for updated revision
        {
            "data": [
                {
                    "id": "123",
                    "phid": "PHID-REV-1",
                    "fields": {"bugzilla.bug-id": "1"},
                    "attachments": {
                        "reviewers": {"reviewers": [{"reviewerPHID": "PHID-USER-1"}]}
                    },
                }
            ]
        },  # get reviewers for updated revision
    )
    check_call_by_line.reset_mock()
    testfile = hg_repo_path / "X"
    testfile.write_text(u"a")
    hg_out("add")

    # Write out our commit message as if the program had already run and appended
    # a Differential Revision keyword to the commit body for tracking.
    hg_out(
        "commit",
        "--message",
        """\
Bug 1 - A

Differential Revision: http://example.test/D123
""",
    )

    mozphab.main(["submit", "--yes", "--bug", "1"])

    log = hg_out("log", "--template", r"{desc}\n", "--rev", ".")
    expected = """\
Bug 1 - A

Differential Revision: http://example.test/D123
"""
    assert log == expected
    assert call_conduit.call_count == 2
    arc_call_conduit.assert_not_called()
    check_call_by_line.assert_called_once()  # update


def test_submit_update_reviewers_not_updated(in_process, hg_repo_path):
    call_conduit.reset_mock()
    call_conduit.side_effect = (
        {},
        {
            "data": [
                {
                    "id": 123,
                    "phid": "PHID-REV-1",
                    "fields": {"bugzilla.bug-id": "1"},
                    "attachments": {
                        "reviewers": {"reviewers": [{"reviewerPHID": "PHID-USER-1"}]}
                    },
                }
            ]
        },  # get reviewers for updated revision
        [{"userName": "alice", "phid": "PHID-USER-1"}],
    )
    arc_call_conduit.reset_mock()
    check_call_by_line.reset_mock()
    testfile = hg_repo_path / "X"
    testfile.write_text(u"a")
    hg_out("add")

    # Write out our commit message as if the program had already run and appended
    # a Differential Revision keyword to the commit body for tracking.
    hg_out(
        "commit",
        "--message",
        """\
Bug 1 - A

Differential Revision: http://example.test/D123
""",
    )

    mozphab.main(["submit", "--yes", "--bug", "1", "-r", "alice"])

    arc_call_conduit.assert_not_called()
    check_call_by_line.assert_called_once()


def test_submit_update_no_new_reviewers(in_process, hg_repo_path):
    call_conduit.reset_mock()
    call_conduit.side_effect = (
        {},
        {
            "data": [
                {
                    "id": 123,
                    "phid": "PHID-REV-1",
                    "fields": {"bugzilla.bug-id": "1"},
                    "attachments": {"reviewers": {"reviewers": []}},
                }
            ]
        },  # get reviewers for updated revision
        [{"userName": "alice", "phid": "PHID-USER-1"}],
    )
    arc_call_conduit.reset_mock()
    arc_call_conduit.side_effect = ({"data": {}},)  # set reviewers response
    check_call_by_line.reset_mock()
    testfile = hg_repo_path / "X"
    testfile.write_text(u"a")
    hg_out("add")

    # Write out our commit message as if the program had already run and appended
    # a Differential Revision keyword to the commit body for tracking.
    hg_out(
        "commit",
        "--message",
        """\
Bug 1 - A

Differential Revision: http://example.test/D123
""",
    )

    mozphab.main(["submit", "--yes", "--bug", "1", "-r", "alice"])
    arc_call_conduit.assert_called_with(
        "differential.revision.edit",
        {
            "objectIdentifier": "D123",
            "transactions": [{"type": "reviewers.set", "value": ["PHID-USER-1"]}],
        },
        mock.ANY,
    )
    check_call_by_line.assert_called_once()
    # [
    #     mock.ANY,  # arc command with full path
    #     '--trace',
    #     'diff',
    #     '--base',
    #     'arc:this',
    #     '--allow-untracked',
    #     '--no-amend',
    #     '--no-ansi',
    #     '--message-file',
    #     mock.ANY,  # temp message file
    #     '--message',
    #     'Revision updated.',
    #     '--update',
    #     '123'
    # ],
    # cwd=mock.ANY,
    # never_log=True


def test_submit_update_bug_id(in_process, hg_repo_path):
    call_conduit.reset_mock()
    call_conduit.side_effect = (
        {},
        {
            "data": [
                {
                    "id": 123,
                    "phid": "PHID-REV-1",
                    "fields": {"bugzilla.bug-id": "1"},
                    "attachments": {
                        "reviewers": {"reviewers": [{"reviewerPHID": "PHID-USER-1"}]}
                    },
                }
            ]
        },  # get reviewers for updated revision
        [{"userName": "alice", "phid": "PHID-USER-1"}],
    )
    arc_call_conduit.reset_mock()
    arc_call_conduit.side_effect = ({"data": {}},)  # response from setting the bug id
    testfile = hg_repo_path / "X"
    testfile.write_text(u"a")
    hg_out("add")

    # Write out our commit message as if the program had already run and appended
    # a Differential Revision keyword to the commit body for tracking.
    hg_out(
        "commit",
        "--message",
        """\
Bug 1 - A

Differential Revision: http://example.test/D123
""",
    )

    mozphab.main(["submit", "--yes", "--bug", "2", "-r", "alice"])

    arc_call_conduit.assert_called_once_with(
        "differential.revision.edit",
        {
            "objectIdentifier": "D123",
            "transactions": [{"type": "bugzilla.bug-id", "value": "2"}],
        },
        mock.ANY,
    )
    assert call_conduit.call_count == 3
