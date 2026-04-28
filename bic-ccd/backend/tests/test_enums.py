"""
Enum integrity tests.

Ensures enum values remain consistent with what the DB CHECK constraints and
Oracle migrations expect.  A rename or deletion here shows up immediately.
"""
import pytest
from app.enums import (
    ControlStatus, RoleCode, RAGStatus, ApprovalAction,
    SubmissionFinalStatus, EvidenceFileStatus, EscalationType,
    TERMINAL_STATUSES, MANAGEMENT_PASS_STATUSES, MANAGEMENT_FAIL_STATUSES,
    APPROVER_ROLES, enum_values,
)


class TestControlStatus:
    def test_original_bic_7_present(self):
        for v in ("NOT_STARTED", "IN_PROGRESS", "PENDING_APPROVAL",
                  "APPROVED", "REWORK", "SLA_BREACHED", "COMPLETED"):
            assert v in enum_values(ControlStatus), f"Missing: {v}"

    def test_phase1c_additions_present(self):
        for v in ("SLA_MET", "RECEIVED_POST_BREACH", "REJECTED",
                  "RECEIVED", "NOT_RECEIVED", "INSUFFICIENT_MAPPING"):
            assert v in enum_values(ControlStatus), f"Missing: {v}"

    def test_evidence_lifecycle_present(self):
        for v in ("DRAFT", "ACTIVE", "DELETED"):
            assert v in enum_values(ControlStatus)


class TestRoleCode:
    def test_core_7_roles(self):
        for r in ("MANAGEMENT", "L1_APPROVER", "L2_APPROVER", "L3_ADMIN",
                  "DATA_PROVIDER", "METRIC_OWNER", "SYSTEM_ADMIN"):
            assert r in enum_values(RoleCode)

    def test_phase1c_alias_roles(self):
        for r in ("ANC_APPROVER_L1", "ANC_APPROVER_L2", "ANC_APPROVER_L3",
                  "SCORECARD_MAKER", "SCORECARD_CHECKER", "UPLOAD", "DOWNLOAD", "READ"):
            assert r in enum_values(RoleCode)


class TestRAGStatus:
    def test_four_values(self):
        assert set(enum_values(RAGStatus)) == {"GREEN", "AMBER", "RED", "GREY"}


class TestApprovalAction:
    def test_all_levels_covered(self):
        vals = set(enum_values(ApprovalAction))
        for level in ("L1", "L2", "L3"):
            assert f"{level}_APPROVED" in vals
            assert f"{level}_REJECTED" in vals
            assert f"{level}_REWORK"   in vals
        assert "SUBMITTED" in vals
        assert "ESCALATED" in vals
        assert "RECALLED"  in vals
        assert "OVERRIDDEN" in vals


class TestSubmissionFinalStatus:
    def test_pending_levels(self):
        vals = set(enum_values(SubmissionFinalStatus))
        assert "L1_PENDING" in vals
        assert "L2_PENDING" in vals
        assert "L3_PENDING" in vals
        assert "APPROVED"   in vals
        assert "REJECTED"   in vals


class TestEvidenceFileStatus:
    def test_lifecycle(self):
        vals = set(enum_values(EvidenceFileStatus))
        assert vals == {"DRAFT", "ACTIVE", "LOCKED", "DELETED"}


class TestConvenienceGroupings:
    def test_terminal_statuses_are_subset_of_control_status(self):
        all_vals = set(enum_values(ControlStatus))
        for s in TERMINAL_STATUSES:
            assert s.value in all_vals

    def test_approver_roles_are_subset_of_role_code(self):
        all_vals = set(enum_values(RoleCode))
        for r in APPROVER_ROLES:
            assert r.value in all_vals

    def test_management_pass_and_fail_are_disjoint(self):
        overlap = MANAGEMENT_PASS_STATUSES & MANAGEMENT_FAIL_STATUSES
        assert len(overlap) == 0, f"Overlap: {overlap}"


class TestEnumValues:
    def test_returns_list_of_strings(self):
        vals = enum_values(ControlStatus)
        assert isinstance(vals, list)
        assert all(isinstance(v, str) for v in vals)

    def test_no_duplicates(self):
        vals = enum_values(RoleCode)
        assert len(vals) == len(set(vals))
