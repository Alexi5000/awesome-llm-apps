from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")


class RepositoryContractTests(unittest.TestCase):
    def test_expected_collections_are_present(self):
        collections = {
            "starter_ai_agents",
            "advanced_ai_agents",
            "advanced_llm_apps",
            "ai_agent_framework_crash_course",
            "awesome_agent_skills",
            "mcp_ai_agents",
            "rag_tutorials",
            "voice_ai_agents",
        }
        for collection in collections:
            self.assertTrue((ROOT / collection).is_dir(), f"missing collection: {collection}")

    def test_readme_defines_the_fork_identity_and_safe_start_path(self):
        required_markers = (
            "## Alexi's fork purpose",
            "Alexi5000’s applied agent-engineering reference library",
            "## Verified setup",
            "python3 -m unittest discover -s tests",
            "## Use cases",
            "## Support and contribution path",
            "## Upstream attribution",
        )
        for marker in required_markers:
            self.assertIn(marker, README, f"README is missing: {marker}")

    def test_community_health_and_fork_policy_files_are_present(self):
        for policy in (
            "CODE_OF_CONDUCT.md",
            "CONTRIBUTING.md",
            "FORK_POLICY.md",
            "SECURITY.md",
            "SUPPORT.md",
            "LICENSE",
        ):
            self.assertTrue((ROOT / policy).is_file(), f"missing policy: {policy}")

    def test_catalog_retains_substantial_documentation_and_dependency_coverage(self):
        project_readmes = list(ROOT.glob("**/README.md"))
        requirement_files = list(ROOT.glob("**/requirements*.txt"))
        self.assertGreaterEqual(len(project_readmes), 150)
        self.assertGreaterEqual(len(requirement_files), 120)

    def test_license_and_fork_policy_preserve_attribution_context(self):
        license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        fork_policy = (ROOT / "FORK_POLICY.md").read_text(encoding="utf-8")
        self.assertIn("Apache License", license_text)
        self.assertIn("Shubhamsaboo/awesome-llm-apps", fork_policy)


if __name__ == "__main__":
    unittest.main()
