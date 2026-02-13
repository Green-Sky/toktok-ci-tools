#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2026 The TokTok team
import unittest
from unittest.mock import MagicMock

from create_release import Config, Releaser
from lib import stage


class TestDashboardRenderer(unittest.TestCase):
    def setUp(self) -> None:
        self.config = Config(
            branch="master",
            main_branch="master",
            dryrun=False,
            force=True,
            github_actions=True,
            issue=1,
            production=True,
            rebase=True,
            resume=False,
            verify=False,
            version="",
            upstream="origin",
        )
        self.releaser = Releaser(self.config, MagicMock(), MagicMock())

    def test_render_initial_state(self) -> None:
        done: set[str] = set()
        rendered = self.releaser.render_progress_list(done, None, None)
        self.assertIn("[ ] Create release branch and PR", rendered)
        self.assertNotIn("**Current Step", rendered)

    def test_render_with_current_task(self) -> None:
        done = {"Preparation"}
        rendered = self.releaser.render_progress_list(
            done, "Review", "Please approve PR"
        )
        self.assertIn("[x] Create release branch and PR", rendered)
        self.assertIn("- [ ] **Current Step: Approve and merge PR**", rendered)
        self.assertIn("> ℹ️ **Action Required:** Please approve PR", rendered)

    def test_render_all_done(self) -> None:
        done = {"Preparation", "Review", "Tagging", "Binaries", "Publication"}
        rendered = self.releaser.render_progress_list(done, None, None)
        self.assertIn("[x] Create release branch and PR", rendered)
        self.assertIn("[x] Approve and merge PR", rendered)
        self.assertIn("[x] Tag and sign the release", rendered)
        self.assertIn("[x] Build and sign binaries", rendered)
        self.assertIn("[x] Finalize release", rendered)


class TestReleaserLogic(unittest.TestCase):
    def setUp(self) -> None:
        self.config = Config(
            branch="master",
            main_branch="master",
            dryrun=False,
            force=True,
            github_actions=True,
            issue=1,
            production=True,
            rebase=True,
            resume=False,
            verify=False,
            version="v1.0.0",
            upstream="origin",
        )
        self.github = MagicMock()
        self.git = MagicMock()
        self.releaser = Releaser(self.config, self.git, self.github)

    def test_run_catches_base_exception(self) -> None:
        # Mock run_stages to raise SystemExit (a BaseException)
        with unittest.mock.patch.object(
            self.releaser, "run_stages", side_effect=SystemExit(1)
        ), unittest.mock.patch.object(
            self.releaser, "report_failure", side_effect=stage.UserAbort("failed")
        ) as mock_report:
            with self.assertRaises(stage.UserAbort):
                self.releaser.run()

            mock_report.assert_called()
            args, kwargs = mock_report.call_args
            self.assertIsInstance(args[1], SystemExit)

    def test_report_failure(self) -> None:
        self.github.actor.return_value = "human"
        self.github.get_issue.return_value = MagicMock(
            body="### Release progress\n[ ] ..."
        )

        with self.assertRaises(stage.UserAbort):
            self.releaser.report_failure("v1.0.0", Exception("Something went wrong"))

        # Check that issue was reassigned
        self.github.issue_unassign.assert_called_with(1, ["toktok-releaser"])
        self.github.issue_assign.assert_called_with(1, ["human"])

        # Check that dashboard was updated
        self.github.change_issue.assert_called()
        args, kwargs = self.github.change_issue.call_args
        self.assertEqual(args[0], 1)
        self.assertIn("❌ **Failure:** Something went wrong", args[1]["body"])


if __name__ == "__main__":
    unittest.main()
