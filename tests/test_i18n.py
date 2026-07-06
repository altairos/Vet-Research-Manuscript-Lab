from __future__ import annotations

import unittest

from vet_manuscript_lab.ui.i18n import (
    DEFAULT_LANGUAGE,
    LANGUAGE_LABELS,
    STRINGS,
    SUPPORTED_LANGUAGES,
    gate_field,
    stage_label,
    status_label,
    translate,
)


class I18nTests(unittest.TestCase):
    def test_supported_languages_match_labels(self) -> None:
        self.assertEqual(set(SUPPORTED_LANGUAGES), set(LANGUAGE_LABELS))

    def test_every_string_has_both_languages(self) -> None:
        # catalog completeness: no key may leave a language blank
        missing = [
            key
            for key, entry in STRINGS.items()
            for language in SUPPORTED_LANGUAGES
            if not entry.get(language)
        ]
        self.assertEqual(missing, [], f"Missing translations for: {missing}")

    def test_translate_returns_localized_text(self) -> None:
        self.assertEqual(
            translate("app_title", lang="en"), "Vet Research Manuscript Lab"
        )
        self.assertEqual(translate("app_title", lang="zh"), "兽医科研稿件实验室")

    def test_translate_falls_back_to_key_for_unknown(self) -> None:
        self.assertEqual(translate("does.not.exist", lang="en"), "does.not.exist")

    def test_translate_rejects_unsupported_language(self) -> None:
        with self.assertRaises(ValueError):
            translate("app_title", lang="fr")

    def test_translate_applies_format_kwargs(self) -> None:
        self.assertEqual(
            translate("success_project_created", lang="en", id="abc"),
            "Created project abc",
        )
        self.assertEqual(
            translate("success_project_created", lang="zh", id="abc"),
            "已创建项目 abc",
        )

    def test_default_language_is_chinese(self) -> None:
        # outside a running Streamlit script context, the default language applies
        self.assertEqual(DEFAULT_LANGUAGE, "zh")
        self.assertEqual(
            translate("workflow_header"), translate("workflow_header", lang="zh")
        )

    def test_stage_label_translates_known_and_unknown(self) -> None:
        self.assertEqual(stage_label("protocol_lock", lang="en"), "Protocol lock")
        self.assertEqual(stage_label("protocol_lock", lang="zh"), "方案锁定")
        self.assertEqual(stage_label("unknown_stage", lang="en"), "unknown_stage")
        self.assertEqual(stage_label(None), "")

    def test_status_label_translates_known_and_unknown(self) -> None:
        self.assertEqual(status_label("waiting_for_human", lang="zh"), "等待人工")
        self.assertEqual(status_label("nope", lang="en"), "nope")
        self.assertEqual(status_label(None), "")

    def test_gate_field_translates(self) -> None:
        self.assertEqual(
            gate_field("question", "title", lang="zh"),
            "审批研究问题与研究类型",
        )
        self.assertEqual(
            gate_field("protocol", "summary", lang="en"),
            "Review endpoints, eligibility, and STROBE-Vet mapping.",
        )


if __name__ == "__main__":
    unittest.main()
