import json
import unittest

from delegation_catalog import (
    best_variant,
    describe,
    profile_meta,
    refresh,
    render_show,
)
from router.fakes import Fixture, Provider


class EvidenceVersions(unittest.TestCase):
    def test_restricted_preview_survives_refresh_without_inventing_active_prices(self):
        cat = {
            "catalog_version": "2026-10-28",
            "models": {
                "gemini-4-carbon": {
                    "aa_slug": "gemini-4-carbon",
                    "serving_status": "restricted-preview",
                    "serving_source": "google-carbon-announcement",
                    "context": None,
                }
            },
        }
        rows = [
            {
                "id": "carbon-high",
                "slug": "gemini-4-carbon",
                "name": "Gemini 4 Carbon (High)",
                "evaluations": {"artificial_analysis_intelligence_index": 59.4},
                "pricing": {"price_1m_input_tokens": 4, "price_1m_output_tokens": 20},
            }
        ]
        new, unmatched = refresh(cat, rows, "2026-10-28")
        self.assertEqual(unmatched, [])
        row = new["models"]["gemini-4-carbon"]
        self.assertIsNone(row.get("price"))
        self.assertIsNone(row["context"])
        self.assertEqual(row["serving_status"], "restricted-preview")
        report = describe(new)
        self.assertEqual(
            report["models"][0]["serving_source"], "google-carbon-announcement"
        )
        self.assertIn("[restricted-preview]", "\n".join(render_show(report)))

    def test_unmeasured_effort_and_wrong_suite_have_no_routing_score(self):
        row = {
            "tier": "frontier",
            "evidence": {
                "source": "artificialanalysis",
                "date": "2026-10-28",
                "index_version": "5.0.1",
                "index": 51,
                "variants": {"max": 51},
            },
        }
        cat = {
            "catalog_version": "2026-10-28",
            "tiering": {
                "index_version": "5.0.1",
                "top_index": 58.4,
                "frontier_within": 8,
                "mid_within": 20,
            },
            "models": {"terra": row},
        }
        profile = {
            "model": "terra",
            "adapter": "codex",
            "parameters": {"effort": "low"},
        }
        result = profile_meta("terra", profile, cat)
        self.assertIsNone(result["score"])
        self.assertIsNone(result["tier"])
        profile["parameters"]["effort"] = "max"
        self.assertEqual(profile_meta("terra", profile, cat)["score"], 51)
        saved = row["evidence"].pop("variants")
        self.assertIsNone(profile_meta("terra", profile, cat)["score"])
        self.assertIsNone(profile_meta("terra", profile, cat)["tier"])
        row["evidence"]["variants"] = saved
        row["evidence"]["index_version"] = "4.3.2"
        self.assertIsNone(profile_meta("terra", profile, cat)["score"])

    def test_null_clears_previous_score_and_exact_slug_avoids_name_collision(self):
        cat = {
            "catalog_version": "2026-10-27",
            "tiering": {"index_version": "5.0.1"},
            "models": {
                "flash": {
                    "aa_slug": "flash-1017",
                    "tier": "mid",
                    "price": {"in": 1, "out": 2},
                    "price_source": "official 2026-10-27",
                    "evidence": {"index": 45.1},
                }
            },
        }
        rows = [
            {
                "name": "Flash (Max)",
                "slug": "flash-1017",
                "evaluations": {"artificial_analysis_intelligence_index": None},
            },
            {
                "name": "Flash (Max)",
                "slug": "flash-old",
                "evaluations": {"artificial_analysis_intelligence_index": 99},
            },
        ]
        result, _ = refresh(cat, rows, "2026-10-28")
        self.assertIsNone(result["models"]["flash"]["tier"])
        self.assertIsNone(result["models"]["flash"]["evidence"]["index"])
        self.assertEqual(
            result["models"]["flash"]["price_source"], "official 2026-10-27"
        )

    def test_best_measured_score_can_use_less_effort(self):
        self.assertEqual(
            best_variant({"max": {"index": 49}, "xhigh": {"index": 49.7}})[0], "xhigh"
        )


class OverlayVersions(Fixture):
    def test_newer_legacy_overlay_is_ignored_without_a_provider_call(self):
        local = self.base / "data/config/catalog.local.json"
        local.parent.mkdir(parents=True)
        local.write_text(
            json.dumps(
                {
                    "catalog_version": "2099-01-01",
                    "models": {},
                    "tiering": {
                        "index_version": "4.3.2",
                        "top_index": 100,
                        "frontier_within": 8,
                        "mid_within": 20,
                    },
                }
            )
        )
        result = json.loads(self.run_cli("check", "--json").stdout)
        self.assertEqual(result["catalog_source"], "shipped")
        self.assertTrue(any("local catalog ignored" in w for w in result["warnings"]))
        self.assertEqual(Provider.requests, [])
