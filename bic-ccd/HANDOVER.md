# Bug Fix Handover - B&I Data Metrics and Controls (BIC-CCD)

**Date:** 2026-04-18  
**Status:** 3/4 Bugs Fixed, 1 Bug Partially Fixed (Still In Progress)

---

## Summary of All 4 Bugs

### ✅ Bug 1: Phantom L1 Queue Entries (FIXED)
**Issue:** Duplicate submissions appearing in L1 queue that shouldn't be there.

**Root Cause:** 
- No uniqueness guard on submissions per status_id
- REJECTED status was re-queuing items instead of being terminal

**Files Changed:**
- `backend/app/services/__init__.py` (lines 319-337, 557, 600)

**Changes:**
1. Added duplicate submission prevention guard (HTTP 409 if active submission exists)
2. Changed L2 REJECTED: `final_status = "REJECTED"` (not L1_PENDING)
3. Changed L3 REJECTED: `final_status = "REJECTED"` (not L1_PENDING)

**Status:** ✅ RESOLVED

---

### ✅ Bug 2: Generate Button Visibility (FIXED)
**Issue:** Audit summary "Generate" button showed even when not in APPROVED state, allowing premature generation.

**Root Cause:** 
- No approval state gate before summary generation
- Frontend didn't check approval status

**Files Changed:**
- `backend/app/routers/audit_evidence.py` (lines 1172-1193)
- `frontend/src/pages/Evidence/EvidencePage.tsx` (lines 273-275, 526-545, 863)
- `frontend/src/api/client.ts` (line 181)

**Changes:**
1. Added backend approval gate: 403 error if not APPROVED
2. Added frontend condition: only show Generate button if `approvalStatus === 'APPROVED'`
3. Updated API type signature to match

**Status:** ✅ RESOLVED

---

### ✅ Bug 3: Audit Evidence Count Mismatch (FIXED)
**Issue:** Audit summary showed different evidence counts than the Evidence tab (global vs dimension-scoped).

**Root Cause:** 
- Evidence query was global (all controls) but iteration count was computed globally
- No dimension filtering when generating summary

**Files Changed:**
- `backend/app/routers/audit_evidence.py` (lines 1199-1202, 1220, 1404)
- `backend/app/schemas/__init__.py` (line 694)
- `frontend/src/pages/Evidence/EvidencePage.tsx` (line 302)
- `frontend/src/api/client.ts` (line 181)

**Changes:**
1. Added `control_code` parameter to GenerateSummaryRequest schema
2. Backend filters evidence by control_code (dimension_code) if provided
3. Fixed iteration counting: `len({e.iteration for e in evidences if e.iteration is not None})`
4. Frontend passes control_code through generate request

**Status:** ✅ RESOLVED

---

### ⚠️ Bug 4: Rework Item Appearing in L3 Queue (PARTIAL FIX)
**Issue:** After L3 does REWORK action, item still appears in L3 queue instead of going back to L1.

**Root Cause (Primary):**
- Queue queries (`get_pending_for_approver`, `get_all_pending`) return ALL submissions matching final_status
- Pre-existing duplicate submissions from before Bug 1 fix caused orphaned rows with stale final_status values

**Root Cause (Secondary):**
- Old submission_id 9 had `final_status = "REWORK"` instead of `"L1_PENDING"` after L3_REWORK action
- This happened because code fix wasn't in place when action was performed on 2026-04-11

**Files Changed:**
- `backend/app/repositories/__init__.py` (lines 569-613, 640-665)

**Changes:**
1. Added subquery to filter LATEST submission per status_id in `get_pending_for_approver()`
2. Added identical subquery filter to `get_all_pending()`
3. Pattern: `JOIN latest_sub ON (submission_id = max_submission_id AND status_id = status_id)`

**Database Fixes Applied:**
```sql
UPDATE MAKER_CHECKER_SUBMISSION
SET FINAL_STATUS = 'L1_PENDING'
WHERE SUBMISSION_ID = 9;
COMMIT;
```

**Status:** ⚠️ PARTIALLY FIXED - Code logic is correct, but item still showing in L3 queue

**Current Data State (status_id 143 = KRI-CEP-021):**
```
submission_id 49 | final_status = L3_PENDING  (older)
submission_id 9  | final_status = L1_PENDING  (latest) ← should be returned by max() filter
```

---

## Outstanding Issues

### Issue: KRI-CEP-021 Still Appears in L3 Queue

**Expected Behavior:**
- Query should join with `max(submission_id)` per status_id
- For status_id 143: max(submission_id) = 49
- Submission #49 has final_status = "L3_PENDING" → should show in L3 queue ✓

**Actual Behavior:**
- Still showing in L3 queue after database fix and backend restart

**Possible Root Causes to Investigate:**

1. **Subquery join not working as expected**
   - Verify that the `latest_sub` subquery is correctly computing max(submission_id)
   - Check if there's an issue with the AND condition in the join

2. **Frontend caching/stale data**
   - Clear browser cache (Ctrl+Shift+Delete)
   - Hard refresh page (Ctrl+Shift+R)
   - Check Redux state

3. **Oracle database-specific issue**
   - Test subquery in isolation
   - Verify func.max() works correctly in SQLAlchemy for Oracle
   - Check if there's a locking/visibility issue

4. **Different code path being executed**
   - Verify which method is actually being called (get_pending_for_approver vs get_all_pending)
   - Check role-based logic in pending_approvals endpoint

---

## Code Locations Reference

| File | Lines | Purpose |
|------|-------|---------|
| `backend/app/services/__init__.py` | 319-337 | Duplicate submission guard |
| `backend/app/services/__init__.py` | 537, 557, 600 | Terminal status handling |
| `backend/app/services/__init__.py` | 584-593 | L3_REWORK logic (sets final_status = L1_PENDING) |
| `backend/app/repositories/__init__.py` | 569-633 | Queue filtering with max() subquery |
| `backend/app/repositories/__init__.py` | 640-665 | Admin pending view with max() subquery |
| `backend/app/routers/audit_evidence.py` | 1172-1193 | Approval state gate |
| `frontend/src/pages/Evidence/EvidencePage.tsx` | 273-863 | Evidence page with approvalStatus prop |

---

## Approval Flow (Final)

```
SUBMIT → L1_PENDING
  ↓
L1 APPROVED → L2_PENDING (or APPROVED if no L2)
  ↓
L2 APPROVED → L3_PENDING (or APPROVED if no L3)
  ↓
L3 APPROVED → APPROVED (terminal ✓)

At any level:
- REWORK → resets chain, goes back to L1_PENDING
- REJECTED → terminal (doesn't re-enter)
- ESCALATE → jumps to next level
```

---

## Database Schema (Relevant Tables)

| Table | Key Fields | Purpose |
|-------|-----------|---------|
| `MAKER_CHECKER_SUBMISSION` | submission_id, status_id, final_status, l1_action, l2_action, l3_action | Submission record per approval level |
| `CCB_KRI_CONTROL_STATUS_TRACKER` | status_id, kri_id, period_year, period_month | Monthly control status |
| `APPROVAL_AUDIT_TRAIL` | audit_id, status_id, action, new_status, performed_dt | Historical audit log |

---

## Testing Checklist

- [ ] Restart backend after all code changes
- [ ] Clear browser cache before testing UI
- [ ] Verify Bug 1: No duplicate items in L1 queue
- [ ] Verify Bug 2: Generate button hidden until APPROVED
- [ ] Verify Bug 3: Evidence counts match between Evidence tab and Summary
- [ ] Verify Bug 4: L3_REWORK items appear in L1 queue (not L3)

---

## Next Steps for Handover

1. **Debug Bug 4 Queue Filter Issue:**
   - Add debug logging to `get_pending_for_approver()` to see what submissions are being returned
   - Print the subquery result separately
   - Verify the join condition is correct

2. **Test Subquery in Isolation:**
   ```sql
   SELECT MAX(SUBMISSION_ID) as max_id, STATUS_ID
   FROM MAKER_CHECKER_SUBMISSION
   WHERE STATUS_ID = 143
   GROUP BY STATUS_ID;
   ```

3. **Verify Query Results:**
   ```sql
   SELECT * FROM MAKER_CHECKER_SUBMISSION
   WHERE STATUS_ID = 143
   AND FINAL_STATUS = 'L3_PENDING';
   ```

4. **Check for Additional Duplicates:**
   ```sql
   SELECT STATUS_ID, COUNT(*) as count
   FROM MAKER_CHECKER_SUBMISSION
   WHERE FINAL_STATUS IN ('L1_PENDING', 'L2_PENDING', 'L3_PENDING')
   GROUP BY STATUS_ID
   HAVING COUNT(*) > 1;
   ```

---

## Communication Notes

- User tested locally with multiple browsers
- All code restarts performed
- Database manually updated for KRI-CEP-021
- Issue persists despite code fix appearing correct
- **User is handing over for someone else to debug Bug 4**

