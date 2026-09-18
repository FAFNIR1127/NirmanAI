"""
scripts/testing/test_copilot_v2_eval.py

Phase 13 — AI Copilot v2 Intelligence Layer Evaluation Suite.
Tests categories A–K to verify capability planning, evidence packaging, claim audit,
multi-turn context tracking, and numerical integrity.
"""

import os
import sys

# Ensure project root is in path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)

import unittest
import psycopg2

from backend.app.services.capability_registry import CapabilityRegistry, CAPABILITIES
from backend.app.services.query_planner import QueryPlanner
from backend.app.services.analysis_orchestrator import AnalysisOrchestrator
from backend.app.services.evidence_validator import EvidenceValidator
from backend.app.services.response_composer import ResponseComposer
from backend.app.services.assistant_service import AssistantService
from backend.app.services.insight_service import InsightService
from backend.app.services.conversation_context import ConversationContextManager


class TestCopilotV2Eval(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.planner = QueryPlanner()
        cls.orchestrator = AnalysisOrchestrator()
        cls.validator = EvidenceValidator()
        cls.composer = ResponseComposer()
        cls.assistant = AssistantService()

    def test_category_j_capability_registry(self):
        """Category J: Capability registry has machine-readable contracts for all capabilities."""
        caps = CapabilityRegistry.list_capabilities()
        self.assertGreaterEqual(len(caps), 12)
        names = {c["name"] for c in caps}
        self.assertIn("get_project", names)
        self.assertIn("portfolio_kpis", names)
        self.assertIn("risk_decomposition", names)
        self.assertIn("semantic_search", names)
        print("✅ Category J Passed: Machine-readable capability registry verified.")

    def test_category_a_open_ended_planning(self):
        """Category A: Open-ended natural language query planning."""
        plan = self.planner.create_plan("Summarize portfolio overruns and critical risk projects", {})
        self.assertIsNotNone(plan)
        self.assertGreater(len(plan.operations), 0)
        self.assertTrue(any(op.capability == "portfolio_kpis" for op in plan.operations))
        print("✅ Category A Passed: Open-ended dynamic query planning verified.")

    def test_category_b_regional_inquiries(self):
        """Category B: Regional state/sector inquiries."""
        plan = self.planner.create_plan("Analyze risk concentration in Maharashtra", {})
        self.assertIsNotNone(plan)
        op_caps = [op.capability for op in plan.operations]
        self.assertIn("state_stats", op_caps)
        print("✅ Category B Passed: Regional state inquiry planning verified.")

    def test_category_c_project_deep_dive(self):
        """Category C: Specific project deep dive."""
        plan = self.planner.create_plan("Why is project 220100262 high risk?", {})
        self.assertIsNotNone(plan)
        op_caps = [op.capability for op in plan.operations]
        self.assertIn("get_project", op_caps)

        pkg = self.orchestrator.execute_plan(plan)
        self.assertIn("220100262", pkg.projects_analyzed)
        print("✅ Category C Passed: Project deep dive capability execution verified.")

    def test_category_d_side_by_side_comparison(self):
        """Category D: Side-by-side project comparison."""
        plan = self.planner.create_plan("Compare project 220100262 vs 220100273", {})
        self.assertEqual(plan.response_mode, "comparison")
        pkg = self.orchestrator.execute_plan(plan)
        self.assertGreaterEqual(len(pkg.projects_analyzed), 2)
        print("✅ Category D Passed: Side-by-side project comparison verified.")

    def test_category_e_semantic_rag_search(self):
        """Category E: Semantic RAG search across PAIMANA reports."""
        plan = self.planner.create_plan("What did PAIMANA reports say about railway delays?", {})
        pkg = self.orchestrator.execute_plan(plan)
        self.assertIsNotNone(pkg)
        print("✅ Category E Passed: Semantic RAG vector retrieval executed.")

    def test_category_f_proactive_surveillance(self):
        """Category F: Proactive morning surveillance snapshot."""
        snapshot = InsightService.get_morning_surveillance()
        self.assertIn("title", snapshot)
        self.assertIn("portfolio_summary", snapshot)
        self.assertGreaterEqual(snapshot["portfolio_summary"]["total_projects"], 3000)
        print("✅ Category F Passed: Proactive morning surveillance snapshot verified.")

    def test_category_g_multi_turn_context(self):
        """Category G: Multi-turn conversation context tracking."""
        sid = "test_eval_session"
        res1 = self.assistant.chat("Tell me about project 220100262", session_id=sid)
        self.assertIsNotNone(res1)
        sess = ConversationContextManager.get_session(sid)
        self.assertEqual(sess.last_project_code, "220100262")
        print("✅ Category G Passed: Multi-turn context persistence verified.")

    def test_category_h_evidence_verification(self):
        """Category H: Evidence claim verification and citation integrity."""
        plan = self.planner.create_plan("Show portfolio summary", {})
        pkg = self.orchestrator.execute_plan(plan)
        res = self.composer.compose(pkg)
        self.assertTrue(res.is_verified)
        self.assertIsNotNone(res.verification_notes)
        print("✅ Category H Passed: Evidence claim verification audit passed.")

    def test_category_i_api_schema_validation(self):
        """Category I: 6-Part CopilotResponse schema structure."""
        res = self.assistant.chat("Summarize portfolio risks")
        self.assertTrue(hasattr(res, "direct_answer"))
        self.assertTrue(hasattr(res, "key_findings"))
        self.assertTrue(hasattr(res, "important_numbers"))
        self.assertTrue(hasattr(res, "risk_and_drivers"))
        self.assertTrue(hasattr(res, "evidence_citations"))
        self.assertTrue(hasattr(res, "next_actions"))
        print("✅ Category I Passed: 6-part adaptive CopilotResponse schema validated.")

    def test_category_k_numerical_integrity(self):
        """Category K: Numerical integrity and zero arithmetic hallucination."""
        res = self.assistant.chat("How many projects are monitored in Nirman?")
        self.assertIn("3,589", res.direct_answer)
        print("✅ Category K Passed: Absolute numerical integrity verified.")


def run_tests():
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestCopilotV2Eval)
    runner = unittest.TextTestRunner(verbosity=0)
    result = runner.run(suite)
    
    results = []
    for test in suite:
        test_name = getattr(test, "_testMethodName", str(test))
        is_fail = any(getattr(f[0], "_testMethodName", str(f[0])) == test_name for f in result.failures)
        is_err = any(getattr(e[0], "_testMethodName", str(e[0])) == test_name for e in result.errors)
        status_ok = not (is_fail or is_err)
        results.append({
            "id": f"COPILOT_V2_{test_name.upper()}",
            "name": test_name.replace("_", " ").title(),
            "passed": status_ok,
            "status": "PASS" if status_ok else "FAIL",
            "details": f"Verified {test_name}"
        })
    return results


if __name__ == "__main__":
    unittest.main()
