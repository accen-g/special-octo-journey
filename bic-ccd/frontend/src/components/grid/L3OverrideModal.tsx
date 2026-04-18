/**
 * L3OverrideModal — heatmap shortcut that runs the **standard** L3 approval
 * workflow (POST /api/maker-checker/{submissionId}/action).
 *
 * USER JOURNEY:
 *   1. L3/SYSTEM_ADMIN clicks a "Pending Approval (L3)" chip in the heatmap.
 *   2. This modal opens, pre-filled with APPROVE / REWORK / REJECT actions —
 *      identical to what the Approvals page offers.
 *   3. User selects an action (required) and enters a comment (required).
 *   4. Submit → calls maker-checker action endpoint → same logic as the
 *      Approvals page, so the item immediately leaves the L3 Pending queue.
 *   5. On success: both ['controls-all'] and ['pending-approvals'] caches are
 *      invalidated → heatmap cell refreshes, Approvals page queue shrinks.
 *   6. Cancel → modal closes, form resets, no API call.
 *
 * Props:
 *   open          – controls Dialog visibility
 *   onClose       – called on cancel and on successful submit
 *   submissionId  – MakerCheckerSubmission.submission_id (path param)
 *   kriCode       – display only (Dialog title)
 *   kriName       – display only (Dialog subtitle)
 */
import { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  FormHelperText,
  CircularProgress,
  Typography,
  Alert,
} from '@mui/material';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { makerCheckerApi } from '../../api/client';

// ─── Action options (mirror the Approvals page) ────────────────────────────
const ACTION_OPTIONS: { value: string; label: string; description: string }[] = [
  { value: 'APPROVED', label: 'Approve',        description: 'Mark as Completed — removes from pending queue' },
  { value: 'REWORK',   label: 'Request Rework', description: 'Send back to L1 for correction'                },
  { value: 'REJECTED', label: 'Reject',         description: 'Reject and return to submitter'                },
];

// ─── Props ─────────────────────────────────────────────────────────────────
interface L3OverrideModalProps {
  open: boolean;
  onClose: () => void;
  submissionId: number;
  kriCode: string;
  kriName: string;
}

// ─── Component ─────────────────────────────────────────────────────────────
export default function L3OverrideModal({
  open,
  onClose,
  submissionId,
  kriCode,
  kriName,
}: L3OverrideModalProps) {
  const queryClient = useQueryClient();

  // ── Form state ────────────────────────────────────────────
  const [action, setAction]         = useState('');
  const [comment, setComment]       = useState('');

  // ── Validation touched flags ───────────────────────────────
  const [actionTouched, setActionTouched]   = useState(false);
  const [commentTouched, setCommentTouched] = useState(false);

  // ── Error state ───────────────────────────────────────────
  const [submitError, setSubmitError] = useState<string>('');

  // Reset form when modal opens
  useEffect(() => {
    if (open) {
      setAction('');
      setComment('');
      setActionTouched(false);
      setCommentTouched(false);
      setSubmitError('');
    }
  }, [open]);

  // ── Submit mutation — uses the standard maker-checker action endpoint ──
  const mutation = useMutation<unknown, Error, void>({
    mutationFn: () =>
      makerCheckerApi
        .action(submissionId, { action, comments: comment.trim() })
        .then((r) => r.data),
    onSuccess: () => {
      // Invalidate both the heatmap and the Approvals pending queue
      queryClient.invalidateQueries({ queryKey: ['controls-all'] });
      queryClient.invalidateQueries({ queryKey: ['pending-approvals'] });
      onClose();
    },
    onError: (err: unknown) => {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        'Action failed. Please try again.';
      setSubmitError(typeof msg === 'string' ? msg : JSON.stringify(msg));
    },
  });

  // ── Derived state ─────────────────────────────────────────
  const actionError  = actionTouched  && !action;
  const commentError = commentTouched && !comment.trim();
  const isFormValid  = !!action && !!comment.trim();
  const isSubmitting = mutation.isPending;

  // ── Submit handler ────────────────────────────────────────
  const handleSubmit = () => {
    setActionTouched(true);
    setCommentTouched(true);
    setSubmitError('');
    if (!isFormValid) return;
    mutation.mutate();
  };

  return (
    <Dialog open={open} onClose={isSubmitting ? undefined : onClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ fontWeight: 700, pb: 0.5 }}>
        L3 Approval — {kriCode}
        <Typography variant="body2" color="text.secondary" sx={{ fontWeight: 400 }}>
          {kriName}
        </Typography>
      </DialogTitle>

      <DialogContent dividers>
        {/* ── Error Alert ─────────────────────────────── */}
        {submitError && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setSubmitError('')}>
            {submitError}
          </Alert>
        )}

        {/* ── Action ─────────────────────────────────── */}
        <FormControl fullWidth required error={actionError} sx={{ mb: 2.5 }}>
          <InputLabel id="l3-action-label">Action</InputLabel>
          <Select
            labelId="l3-action-label"
            value={action}
            label="Action"
            disabled={isSubmitting}
            onChange={(e) => { setAction(e.target.value); setActionTouched(true); }}
          >
            {ACTION_OPTIONS.map((opt) => (
              <MenuItem key={opt.value} value={opt.value}>
                <span>
                  <strong>{opt.label}</strong>
                  <Typography variant="caption" display="block" color="text.secondary">
                    {opt.description}
                  </Typography>
                </span>
              </MenuItem>
            ))}
          </Select>
          {actionError && <FormHelperText>Action is required.</FormHelperText>}
        </FormControl>

        {/* ── Comment ────────────────────────────────── */}
        <TextField
          label="Comments"
          required
          multiline
          minRows={3}
          fullWidth
          value={comment}
          disabled={isSubmitting}
          error={commentError}
          helperText={commentError ? 'Comments are required.' : ''}
          onChange={(e) => { setComment(e.target.value); setCommentTouched(true); }}
        />
      </DialogContent>

      <DialogActions sx={{ px: 3, py: 1.5 }}>
        <Button
          onClick={onClose}
          disabled={isSubmitting}
          sx={{ textTransform: 'none' }}
        >
          Cancel
        </Button>
        <Button
          variant="contained"
          onClick={handleSubmit}
          disabled={isSubmitting}
          startIcon={isSubmitting ? <CircularProgress size={16} color="inherit" /> : undefined}
          sx={{ textTransform: 'none', fontWeight: 600 }}
        >
          {isSubmitting ? 'Submitting…' : 'Submit'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
