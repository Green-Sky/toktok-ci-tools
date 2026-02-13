# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2026 The TokTok team
import unittest
import unittest.mock
from typing import Any

import validate_pr
from lib import stage


class TestCheckChangelog(unittest.TestCase):
    @unittest.mock.patch("validate_pr.update_changelog.main")
    @unittest.mock.patch("validate_pr.update_changelog.read_clog_toml", return_value={})
    @unittest.mock.patch("validate_pr.update_changelog.parse_config")
    @unittest.mock.patch("validate_pr.github.head_ref")
    @unittest.mock.patch("validate_pr.has_diff", return_value=False)
    @unittest.mock.patch("validate_pr.stage.Stage")
    def test_check_changelog_production(
        self,
        mock_stage: unittest.mock.MagicMock,
        mock_has_diff: unittest.mock.MagicMock,
        mock_head_ref: unittest.mock.MagicMock,
        mock_parse_config: unittest.mock.MagicMock,
        mock_read_clog_toml: unittest.mock.MagicMock,
        mock_clog_main: unittest.mock.MagicMock,
    ) -> None:
        clog_config = unittest.mock.MagicMock()
        clog_config.production = False
        mock_parse_config.return_value = clog_config

        # 1. Release config set to True
        mock_head_ref.return_value = "some-branch"
        config = validate_pr.Config(commit=False, release=True)
        validate_pr.check_changelog([], config)
        self.assertTrue(clog_config.production)
        mock_clog_main.assert_called_with(clog_config)

        # 2. Release config False, but branch is a production release branch
        clog_config.production = False
        mock_head_ref.return_value = "release/v1.0.0"
        config = validate_pr.Config(commit=False, release=False)
        validate_pr.check_changelog([], config)
        self.assertTrue(clog_config.production)

        # 3. Release config False, branch is an RC release branch
        clog_config.production = False
        mock_head_ref.return_value = "release/v1.0.0-rc.1"
        config = validate_pr.Config(commit=False, release=False)
        validate_pr.check_changelog([], config)
        self.assertFalse(clog_config.production)


class TestValidatePRLogic(unittest.TestCase):
    def test_parse_weblate_prs(self) -> None:
        prs_data = [
            {
                "title": "Translation 1",
                "html_url": "url1",
                "user": {"login": "weblate"},
            },
            {"title": "Other PR", "html_url": "url2", "user": {"login": "human"}},
            {
                "title": "Translation 2",
                "html_url": "url3",
                "user": {"login": "weblate"},
            },
        ]
        expected = [("Translation 1", "url1"), ("Translation 2", "url3")]
        self.assertEqual(validate_pr.parse_weblate_prs(prs_data), expected)

    def test_parse_toxcore_version(self) -> None:
        content = """#!/bin/bash
TOXCORE_VERSION=0.2.20
SOME_OTHER_VAR=val
"""
        self.assertEqual(validate_pr.parse_toxcore_version(content), "0.2.20")
        self.assertIsNone(validate_pr.parse_toxcore_version("no version here"))

    def test_parse_version_diff(self) -> None:
        diff = """--- a/platform/linux/chat.tox.CiTools.appdata.xml
+++ b/platform/linux/chat.tox.CiTools.appdata.xml
-  <release version="1.18.0-rc.3" date="2024-12-29"/>
+  <release version="1.18.0" date="2024-12-29"/>
"""
        minus, plus = validate_pr.parse_version_diff(diff)
        self.assertEqual(minus, ["1.18.0-rc.3"])
        self.assertEqual(plus, ["1.18.0"])

    def test_parse_version_diff_no_changes(self) -> None:
        diff = """some other changes
- <p>line</p>
+ <p>new line</p>"""
        minus, plus = validate_pr.parse_version_diff(diff)
        self.assertEqual(minus, [])
        self.assertEqual(plus, [])


class TestMain(unittest.TestCase):
    @unittest.mock.patch("validate_pr.github.actor", return_value="human")
    @unittest.mock.patch("validate_pr.github.head_ref", return_value="master")
    @unittest.mock.patch("validate_pr.github.api_requests", new_callable=list)
    @unittest.mock.patch("validate_pr.check_github_weblate_prs")
    @unittest.mock.patch("validate_pr.check_flathub_descriptor_dependencies")
    @unittest.mock.patch("validate_pr.check_toxcore_version")
    @unittest.mock.patch("validate_pr.check_package_versions")
    @unittest.mock.patch("validate_pr.check_no_version_changes")
    @unittest.mock.patch("validate_pr.check_changelog")
    def test_main_with_failures_list(
        self,
        mock_check_changelog: unittest.mock.MagicMock,
        mock_check_no_version_changes: unittest.mock.MagicMock,
        mock_check_package_versions: unittest.mock.MagicMock,
        mock_check_toxcore_version: unittest.mock.MagicMock,
        mock_check_flathub_descriptor_dependencies: unittest.mock.MagicMock,
        mock_check_github_weblate_prs: unittest.mock.MagicMock,
        mock_api_requests: list[Any],
        mock_head_ref: unittest.mock.MagicMock,
        mock_actor: unittest.mock.MagicMock,
    ) -> None:
        # Setup: check_changelog appends a failure
        mock_check_changelog.side_effect = lambda f, c: f.append("Changelog failure")

        config = validate_pr.Config(commit=False, release=False)

        # 1. Test with failures=[] -> should raise stage.InvalidState
        with self.assertRaises(stage.InvalidState) as cm:
            validate_pr.main(config, failures=[])
        self.assertIn("1 checks failed", str(cm.exception))

        # 2. Test with failures=None -> should call exit(1)
        with self.assertRaises(SystemExit) as cm_exit:
            validate_pr.main(config, failures=None)
        self.assertEqual(cm_exit.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
