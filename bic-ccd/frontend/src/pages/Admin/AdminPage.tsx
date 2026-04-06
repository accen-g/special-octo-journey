import React, { useState } from 'react';
import {
  Box, Card, CardContent, Typography, Tabs, Tab, Button, Chip, Grid,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  Dialog, DialogTitle, DialogContent, DialogActions, TextField,
  Select, MenuItem, FormControl, InputLabel, CircularProgress, Alert,
  IconButton, Switch, FormControlLabel, Tooltip,
} from '@mui/material';
import { PersonAdd, Edit, Security, Tune, Delete, Rule } from '@mui/icons-material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { userApi, escalationApi, lookupApi, kriApi, assignmentRuleApi } from '../../api/client';
import { roleLabel } from '../../utils/helpers';

const ROLE_CODES = Object.keys(roleLabel);

const ESCALATION_ROLE_OPTIONS = [
  'L1_APPROVER', 'L2_APPROVER', 'L3_ADMIN', 'SYSTEM_ADMIN', 'MANAGEMENT',
];

const APPROVER_ROLE_OPTIONS = ['L1_APPROVER', 'L2_APPROVER', 'L3_ADMIN'];

const emptyEscForm = {
  escalation_type: '',
  threshold_hours: 72,
  reminder_hours: 24,
  max_reminders: 3,
  escalate_to_role: '',
  region_id: '',
};

const emptyRuleForm = {
  role_code: 'L1_APPROVER',
  user_id: '',
  region_id: '',
  kri_id: '',
  category_id: '',
  priority: 100,
};

export default function AdminPage() {
  const queryClient = useQueryClient();
  const [tab, setTab] = useState(0);

  // ─── User Management state ──────────────────────────────
  const [userDialog, setUserDialog] = useState(false);
  const [editDialog, setEditDialog] = useState<{ open: boolean; user: any | null }>({ open: false, user: null });
  const [deactivateDialog, setDeactivateDialog] = useState<{ open: boolean; user: any | null }>({ open: false, user: null });
  const [roleDialog, setRoleDialog] = useState<{ open: boolean; userId: number | null }>({ open: false, userId: null });
  const [confirmReplace, setConfirmReplace] = useState<{ open: boolean; oldRole?: string; newRole?: string }>({ open: false });
  const [searchTerm, setSearchTerm] = useState('');
  const [newUser, setNewUser] = useState({ soe_id: '', full_name: '', email: '', department: '' });
  const [editUser, setEditUser] = useState({ full_name: '', email: '', department: '', is_active: true });
  const [newRole, setNewRole] = useState({ role_code: '', region_id: '' });
  const [selectedUser, setSelectedUser] = useState<any>(null);

  // ─── Escalation Config state ────────────────────────────
  const [escDialog, setEscDialog] = useState<{ open: boolean; config: any | null }>({ open: false, config: null });
  const [escForm, setEscForm] = useState(emptyEscForm);
  const [escDeleteDialog, setEscDeleteDialog] = useState<{ open: boolean; config: any | null }>({ open: false, config: null });

  // ─── Assignment Rules state ──────────────────────────────
  const [ruleDialog, setRuleDialog] = useState<{ open: boolean; rule: any | null }>({ open: false, rule: null });
  const [ruleForm, setRuleForm] = useState(emptyRuleForm);
  const [ruleDeleteDialog, setRuleDeleteDialog] = useState<{ open: boolean; rule: any | null }>({ open: false, rule: null });

  // ─── Queries ────────────────────────────────────────────
  const { data: users, isLoading: loadingUsers } = useQuery({
    queryKey: ['users'],
    queryFn: () => userApi.list().then((r) => r.data),
  });

  const { data: escalations, isLoading: loadingEsc } = useQuery({
    queryKey: ['escalations'],
    queryFn: () => escalationApi.list().then((r) => r.data),
  });

  const { data: regions = [] } = useQuery({
    queryKey: ['regions'],
    queryFn: () => lookupApi.regions().then((r) => r.data),
  });

  const { data: categories = [] } = useQuery({
    queryKey: ['categories'],
    queryFn: () => lookupApi.categories().then((r) => r.data),
    enabled: tab === 2,
  });

  const { data: krisData } = useQuery({
    queryKey: ['kris-admin'],
    queryFn: () => kriApi.list({ page_size: 200 }).then((r) => r.data),
    enabled: tab === 2,
  });
  const allKris: any[] = krisData?.items || [];

  const { data: assignmentRules = [], isLoading: loadingRules } = useQuery({
    queryKey: ['assignment-rules'],
    queryFn: () => assignmentRuleApi.list().then((r) => r.data),
    enabled: tab === 2,
  });

  // ─── Mutations ──────────────────────────────────────────
  const createUserMutation = useMutation({
    mutationFn: (data: any) => userApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      setUserDialog(false);
      setNewUser({ soe_id: '', full_name: '', email: '', department: '' });
    },
  });

  const editUserMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: any }) => userApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      setEditDialog({ open: false, user: null });
    },
  });

  const deactivateUserMutation = useMutation({
    mutationFn: (userId: number) => userApi.update(userId, { is_active: false }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      setDeactivateDialog({ open: false, user: null });
    },
  });

  const assignRoleMutation = useMutation({
    mutationFn: (data: any) => userApi.assignRole(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      setRoleDialog({ open: false, userId: null });
      setConfirmReplace({ open: false });
      setNewRole({ role_code: '', region_id: '' });
      setSelectedUser(null);
    },
  });

  const createEscMutation = useMutation({
    mutationFn: (data: any) => escalationApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['escalations'] });
      setEscDialog({ open: false, config: null });
      setEscForm(emptyEscForm);
    },
  });

  const updateEscMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: any }) => escalationApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['escalations'] });
      setEscDialog({ open: false, config: null });
      setEscForm(emptyEscForm);
    },
  });

  const deleteEscMutation = useMutation({
    mutationFn: (id: number) => escalationApi.remove(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['escalations'] });
      setEscDeleteDialog({ open: false, config: null });
    },
  });

  const createRuleMutation = useMutation({
    mutationFn: (data: any) => assignmentRuleApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['assignment-rules'] });
      setRuleDialog({ open: false, rule: null });
      setRuleForm(emptyRuleForm);
    },
  });

  const updateRuleMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: any }) => assignmentRuleApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['assignment-rules'] });
      setRuleDialog({ open: false, rule: null });
      setRuleForm(emptyRuleForm);
    },
  });

  const deleteRuleMutation = useMutation({
    mutationFn: (id: number) => assignmentRuleApi.remove(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['assignment-rules'] });
      setRuleDeleteDialog({ open: false, rule: null });
    },
  });

  // ─── Handlers ───────────────────────────────────────────
  const handleAssignRoleClick = (userId: number) => {
    const user = userItems.find((u: any) => u.user_id === userId);
    setSelectedUser(user);
    setRoleDialog({ open: true, userId });
  };

  const handleEditClick = (user: any) => {
    setEditUser({
      full_name: user.full_name,
      email: user.email,
      department: user.department || '',
      is_active: user.is_active,
    });
    setEditDialog({ open: true, user });
  };

  const handleRoleSubmit = () => {
    const userRoles = selectedUser?.roles || [];
    const hasExistingRole = userRoles.length > 0;

    if (hasExistingRole && userRoles[0]?.role_code) {
      setConfirmReplace({
        open: true,
        oldRole: userRoles[0].role_code,
        newRole: newRole.role_code,
      });
    } else {
      assignRoleMutation.mutate({
        user_id: roleDialog.userId,
        role_code: newRole.role_code,
        region_id: Number(newRole.region_id),
        effective_from: new Date().toISOString().split('T')[0],
      });
    }
  };

  const handleOpenEscCreate = () => {
    setEscForm(emptyEscForm);
    setEscDialog({ open: true, config: null });
  };

  const handleOpenEscEdit = (config: any) => {
    setEscForm({
      escalation_type: config.escalation_type,
      threshold_hours: config.threshold_hours,
      reminder_hours: config.reminder_hours,
      max_reminders: config.max_reminders ?? 3,
      escalate_to_role: config.escalate_to_role,
      region_id: config.region_id ?? '',
    });
    setEscDialog({ open: true, config });
  };

  const handleEscSubmit = () => {
    const payload = {
      ...escForm,
      threshold_hours: Number(escForm.threshold_hours),
      reminder_hours: Number(escForm.reminder_hours),
      max_reminders: Number(escForm.max_reminders),
      region_id: escForm.region_id ? Number(escForm.region_id) : null,
    };
    if (escDialog.config) {
      updateEscMutation.mutate({ id: escDialog.config.config_id, data: payload });
    } else {
      createEscMutation.mutate(payload);
    }
  };

  const handleOpenRuleCreate = () => {
    setRuleForm(emptyRuleForm);
    setRuleDialog({ open: true, rule: null });
  };

  const handleOpenRuleEdit = (rule: any) => {
    setRuleForm({
      role_code: rule.role_code,
      user_id: rule.user_id ?? '',
      region_id: rule.region_id ?? '',
      kri_id: rule.kri_id ?? '',
      category_id: rule.category_id ?? '',
      priority: rule.priority,
    });
    setRuleDialog({ open: true, rule });
  };

  const handleRuleSubmit = () => {
    const payload = {
      role_code: ruleForm.role_code,
      user_id: ruleForm.user_id ? Number(ruleForm.user_id) : null,
      region_id: ruleForm.region_id ? Number(ruleForm.region_id) : null,
      kri_id: ruleForm.kri_id ? Number(ruleForm.kri_id) : null,
      category_id: ruleForm.category_id ? Number(ruleForm.category_id) : null,
      priority: Number(ruleForm.priority),
    };
    if (ruleDialog.rule) {
      updateRuleMutation.mutate({ id: ruleDialog.rule.rule_id, data: payload });
    } else {
      createRuleMutation.mutate(payload);
    }
  };

  const userItems = users?.items || [];
  const escItems = escalations || [];

  const filteredUsers = searchTerm
    ? userItems.filter((u: any) =>
        u.soe_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
        u.full_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        u.email.toLowerCase().includes(searchTerm.toLowerCase())
      )
    : userItems;

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 2, fontWeight: 700 }}>Administration</Typography>

      <Card>
        <CardContent sx={{ p: 0 }}>
          <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ borderBottom: '1px solid', borderColor: 'divider' }}>
            <Tab icon={<PersonAdd sx={{ fontSize: 18 }} />} iconPosition="start" label="User Management" />
            <Tab icon={<Tune sx={{ fontSize: 18 }} />} iconPosition="start" label="Escalation Config" />
            <Tab icon={<Rule sx={{ fontSize: 18 }} />} iconPosition="start" label="Assignment Rules" />
          </Tabs>

          {/* ─── User Management ─────────────────────────── */}
          {tab === 0 && (
            <Box sx={{ p: 2 }}>
              <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 2 }}>
                <TextField
                  placeholder="Search by SOE ID, name, or email..."
                  size="small"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  sx={{ flex: 1 }}
                />
                <Button variant="contained" startIcon={<PersonAdd />} onClick={() => setUserDialog(true)}>
                  Add User
                </Button>
              </Box>
              {loadingUsers ? <CircularProgress /> : (
                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell sx={{ fontWeight: 700 }}>SOE ID</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>Full Name</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>Email</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>Department</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>Role</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>Status</TableCell>
                        <TableCell sx={{ fontWeight: 700 }} align="center">Actions</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {filteredUsers.map((u: any) => (
                        <TableRow key={u.user_id} hover>
                          <TableCell sx={{ fontFamily: 'monospace', fontWeight: 600 }}>{u.soe_id}</TableCell>
                          <TableCell>{u.full_name}</TableCell>
                          <TableCell sx={{ fontSize: '0.82rem' }}>{u.email}</TableCell>
                          <TableCell>{u.department}</TableCell>
                          <TableCell>
                            {u.roles && u.roles.length > 0 ? (
                              <Chip
                                label={roleLabel[u.roles[0].role_code as keyof typeof roleLabel] || u.roles[0].role_code}
                                size="small"
                                variant="outlined"
                                sx={{ fontSize: '0.72rem' }}
                              />
                            ) : (
                              <Typography variant="caption" sx={{ color: 'text.disabled' }}>No role</Typography>
                            )}
                          </TableCell>
                          <TableCell>
                            <Chip
                              label={u.is_active ? 'Active' : 'Inactive'}
                              size="small"
                              sx={{
                                bgcolor: u.is_active ? '#e8f8f0' : '#f0f0f0',
                                color: u.is_active ? '#1e8449' : '#7f8c8d',
                                fontWeight: 600, fontSize: '0.72rem',
                              }}
                            />
                          </TableCell>
                          <TableCell align="center">
                            <Box sx={{ display: 'flex', gap: 0.5, justifyContent: 'center' }}>
                              <Tooltip title="Edit user details">
                                <IconButton size="small" onClick={() => handleEditClick(u)}>
                                  <Edit fontSize="small" />
                                </IconButton>
                              </Tooltip>
                              <Button
                                size="small" variant="outlined"
                                onClick={() => handleAssignRoleClick(u.user_id)}
                                sx={{ fontSize: '0.72rem' }}
                              >
                                Assign Role
                              </Button>
                              {u.is_active && (
                                <Tooltip title="Deactivate user">
                                  <IconButton
                                    size="small"
                                    color="error"
                                    onClick={() => setDeactivateDialog({ open: true, user: u })}
                                  >
                                    <Delete fontSize="small" />
                                  </IconButton>
                                </Tooltip>
                              )}
                            </Box>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}
            </Box>
          )}

          {/* ─── Escalation Config ────────────────────────── */}
          {tab === 1 && (
            <Box sx={{ p: 2 }}>
              <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 2 }}>
                <Button variant="contained" startIcon={<Tune />} onClick={handleOpenEscCreate}>
                  Add Rule
                </Button>
              </Box>
              {loadingEsc ? <CircularProgress /> : (
                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell sx={{ fontWeight: 700 }}>Type</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>Threshold (hrs)</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>Reminder (hrs)</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>Max Reminders</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>Escalate To</TableCell>
                        <TableCell sx={{ fontWeight: 700 }} align="center">Actions</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {escItems.map((e: any) => (
                        <TableRow key={e.config_id} hover>
                          <TableCell><Chip label={e.escalation_type} size="small" sx={{ fontWeight: 600 }} /></TableCell>
                          <TableCell>{e.threshold_hours}</TableCell>
                          <TableCell>{e.reminder_hours}</TableCell>
                          <TableCell>{e.max_reminders ?? 3}</TableCell>
                          <TableCell><Chip label={e.escalate_to_role} size="small" variant="outlined" /></TableCell>
                          <TableCell align="center">
                            <Box sx={{ display: 'flex', gap: 0.5, justifyContent: 'center' }}>
                              <Tooltip title="Edit rule">
                                <IconButton size="small" onClick={() => handleOpenEscEdit(e)}>
                                  <Edit fontSize="small" />
                                </IconButton>
                              </Tooltip>
                              <Tooltip title="Delete rule">
                                <IconButton
                                  size="small"
                                  color="error"
                                  onClick={() => setEscDeleteDialog({ open: true, config: e })}
                                >
                                  <Delete fontSize="small" />
                                </IconButton>
                              </Tooltip>
                            </Box>
                          </TableCell>
                        </TableRow>
                      ))}
                      {escItems.length === 0 && (
                        <TableRow>
                          <TableCell colSpan={6} align="center" sx={{ color: 'text.secondary', py: 3 }}>
                            No escalation rules configured. Click "Add Rule" to create one.
                          </TableCell>
                        </TableRow>
                      )}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}
            </Box>
          )}
          {/* ─── Assignment Rules ────────────────────────── */}
          {tab === 2 && (
            <Box sx={{ p: 2 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                  Rules resolve which user approves at each level. Lower priority number = higher precedence.
                  Resolution order: KRI-specific → Category → Region → Global.
                </Typography>
                <Button variant="contained" startIcon={<Rule />} onClick={handleOpenRuleCreate} sx={{ ml: 2, flexShrink: 0 }}>
                  Add Rule
                </Button>
              </Box>
              {loadingRules ? <CircularProgress /> : (
                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell sx={{ fontWeight: 700 }}>Role</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>Approver</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>Scope</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>Priority</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>Status</TableCell>
                        <TableCell sx={{ fontWeight: 700 }} align="center">Actions</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {(assignmentRules as any[]).map((r: any) => {
                        const scope = r.kri_name
                          ? `KRI: ${r.kri_name}`
                          : r.category_name
                          ? `Category: ${r.category_name}`
                          : r.region_name
                          ? `Region: ${r.region_name}`
                          : 'Global';
                        return (
                          <TableRow key={r.rule_id} hover>
                            <TableCell>
                              <Chip label={roleLabel[r.role_code as keyof typeof roleLabel] || r.role_code}
                                size="small" variant="outlined" sx={{ fontSize: '0.72rem' }} />
                            </TableCell>
                            <TableCell sx={{ fontSize: '0.82rem' }}>
                              {r.user_name || <Typography variant="caption" sx={{ color: 'text.disabled' }}>Unassigned</Typography>}
                            </TableCell>
                            <TableCell>
                              <Chip label={scope} size="small" sx={{ fontSize: '0.72rem', fontWeight: 600 }} />
                            </TableCell>
                            <TableCell sx={{ fontWeight: 700, fontSize: '0.82rem' }}>{r.priority}</TableCell>
                            <TableCell>
                              <Chip label={r.is_active ? 'Active' : 'Inactive'} size="small"
                                sx={{ bgcolor: r.is_active ? '#e8f8f0' : '#f0f0f0',
                                  color: r.is_active ? '#1e8449' : '#7f8c8d', fontWeight: 600, fontSize: '0.72rem' }} />
                            </TableCell>
                            <TableCell align="center">
                              <Box sx={{ display: 'flex', gap: 0.5, justifyContent: 'center' }}>
                                <Tooltip title="Edit rule">
                                  <IconButton size="small" onClick={() => handleOpenRuleEdit(r)}><Edit fontSize="small" /></IconButton>
                                </Tooltip>
                                <Tooltip title="Deactivate rule">
                                  <IconButton size="small" color="error"
                                    onClick={() => setRuleDeleteDialog({ open: true, rule: r })}>
                                    <Delete fontSize="small" />
                                  </IconButton>
                                </Tooltip>
                              </Box>
                            </TableCell>
                          </TableRow>
                        );
                      })}
                      {(assignmentRules as any[]).length === 0 && (
                        <TableRow>
                          <TableCell colSpan={6} align="center" sx={{ color: 'text.secondary', py: 3 }}>
                            No assignment rules configured. Click "Add Rule" to create one.
                          </TableCell>
                        </TableRow>
                      )}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}
            </Box>
          )}
        </CardContent>
      </Card>

      {/* ─── Create User Dialog ───────────────────────────── */}
      <Dialog open={userDialog} onClose={() => setUserDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ fontWeight: 700 }}>Add New User</DialogTitle>
        <DialogContent dividers>
          <Grid container spacing={2} sx={{ mt: 0.5 }}>
            <Grid item xs={6}>
              <TextField label="SOE ID" fullWidth size="small" value={newUser.soe_id}
                onChange={(e) => setNewUser({ ...newUser, soe_id: e.target.value })} />
            </Grid>
            <Grid item xs={6}>
              <TextField label="Full Name" fullWidth size="small" value={newUser.full_name}
                onChange={(e) => setNewUser({ ...newUser, full_name: e.target.value })} />
            </Grid>
            <Grid item xs={6}>
              <TextField label="Email" fullWidth size="small" value={newUser.email}
                onChange={(e) => setNewUser({ ...newUser, email: e.target.value })} />
            </Grid>
            <Grid item xs={6}>
              <TextField label="Department" fullWidth size="small" value={newUser.department}
                onChange={(e) => setNewUser({ ...newUser, department: e.target.value })} />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setUserDialog(false)}>Cancel</Button>
          <Button variant="contained" onClick={() => createUserMutation.mutate(newUser)}
            disabled={!newUser.soe_id || !newUser.full_name || !newUser.email || createUserMutation.isPending}>
            Create User
          </Button>
        </DialogActions>
      </Dialog>

      {/* ─── Edit User Dialog ─────────────────────────────── */}
      <Dialog open={editDialog.open} onClose={() => setEditDialog({ open: false, user: null })} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ fontWeight: 700 }}>Edit User — {editDialog.user?.soe_id}</DialogTitle>
        <DialogContent dividers>
          <Grid container spacing={2} sx={{ mt: 0.5 }}>
            <Grid item xs={6}>
              <TextField label="Full Name" fullWidth size="small" value={editUser.full_name}
                onChange={(e) => setEditUser({ ...editUser, full_name: e.target.value })} />
            </Grid>
            <Grid item xs={6}>
              <TextField label="Email" fullWidth size="small" value={editUser.email}
                onChange={(e) => setEditUser({ ...editUser, email: e.target.value })} />
            </Grid>
            <Grid item xs={6}>
              <TextField label="Department" fullWidth size="small" value={editUser.department}
                onChange={(e) => setEditUser({ ...editUser, department: e.target.value })} />
            </Grid>
            <Grid item xs={6} sx={{ display: 'flex', alignItems: 'center' }}>
              <FormControlLabel
                control={
                  <Switch
                    checked={editUser.is_active}
                    onChange={(e) => setEditUser({ ...editUser, is_active: e.target.checked })}
                  />
                }
                label={editUser.is_active ? 'Active' : 'Inactive'}
              />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditDialog({ open: false, user: null })}>Cancel</Button>
          <Button
            variant="contained"
            disabled={!editUser.full_name || !editUser.email || editUserMutation.isPending}
            onClick={() => editUserMutation.mutate({ id: editDialog.user.user_id, data: editUser })}
          >
            Save Changes
          </Button>
        </DialogActions>
      </Dialog>

      {/* ─── Deactivate User Confirmation Dialog ─────────── */}
      <Dialog open={deactivateDialog.open} onClose={() => setDeactivateDialog({ open: false, user: null })} maxWidth="xs" fullWidth>
        <DialogTitle sx={{ fontWeight: 700 }}>Deactivate User?</DialogTitle>
        <DialogContent dividers>
          <Typography>
            Are you sure you want to deactivate <strong>{deactivateDialog.user?.full_name}</strong> ({deactivateDialog.user?.soe_id})?
          </Typography>
          <Typography variant="body2" sx={{ mt: 1, color: 'text.secondary' }}>
            This will revoke their access to the system. Their data and audit history will be preserved.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeactivateDialog({ open: false, user: null })}>Cancel</Button>
          <Button
            variant="contained"
            color="error"
            disabled={deactivateUserMutation.isPending}
            onClick={() => deactivateUserMutation.mutate(deactivateDialog.user.user_id)}
          >
            Deactivate
          </Button>
        </DialogActions>
      </Dialog>

      {/* ─── Assign Role Dialog ───────────────────────────── */}
      <Dialog open={roleDialog.open} onClose={() => setRoleDialog({ open: false, userId: null })} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ fontWeight: 700 }}>Assign Role — {selectedUser?.full_name || `User #${roleDialog.userId}`}</DialogTitle>
        <DialogContent dividers>
          {selectedUser?.roles && selectedUser.roles.length > 0 && (
            <Alert severity="warning" sx={{ mb: 2 }}>
              ⚠️ This user currently has role: <strong>{roleLabel[selectedUser.roles[0].role_code as keyof typeof roleLabel]}</strong>
              <br />
              Assigning a new role will replace the existing one.
            </Alert>
          )}
          <Grid container spacing={2} sx={{ mt: 0.5 }}>
            <Grid item xs={6}>
              <FormControl fullWidth size="small">
                <InputLabel>Role</InputLabel>
                <Select value={newRole.role_code} label="Role"
                  onChange={(e) => setNewRole({ ...newRole, role_code: e.target.value })}>
                  {Object.entries(roleLabel).map(([code, label]) => (
                    <MenuItem key={code} value={code}>{label as string}</MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={6}>
              <FormControl fullWidth size="small">
                <InputLabel>Region</InputLabel>
                <Select value={newRole.region_id} label="Region"
                  onChange={(e) => setNewRole({ ...newRole, region_id: e.target.value })}>
                  {regions.map((r: any) => (
                    <MenuItem key={r.region_id} value={r.region_id}>{r.region_name}</MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => { setRoleDialog({ open: false, userId: null }); setNewRole({ role_code: '', region_id: '' }); }}>Cancel</Button>
          <Button variant="contained" onClick={handleRoleSubmit} disabled={!newRole.role_code || !newRole.region_id}>
            Assign
          </Button>
        </DialogActions>
      </Dialog>

      {/* ─── Confirm Role Replacement Dialog ─────────────── */}
      <Dialog open={confirmReplace.open} onClose={() => setConfirmReplace({ open: false })} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ fontWeight: 700 }}>Replace Role?</DialogTitle>
        <DialogContent dividers>
          <Typography sx={{ mb: 2 }}>
            This user currently has role: <strong>{roleLabel[confirmReplace.oldRole as keyof typeof roleLabel]}</strong>
          </Typography>
          <Typography sx={{ mb: 2 }}>
            Do you want to replace it with: <strong>{roleLabel[confirmReplace.newRole as keyof typeof roleLabel]}</strong>?
          </Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary', fontStyle: 'italic' }}>
            The previous role will be deactivated automatically.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmReplace({ open: false })}>Cancel</Button>
          <Button
            variant="contained"
            color="warning"
            onClick={() => {
              assignRoleMutation.mutate({
                user_id: roleDialog.userId,
                role_code: newRole.role_code,
                region_id: Number(newRole.region_id),
                effective_from: new Date().toISOString().split('T')[0],
              });
            }}
            disabled={assignRoleMutation.isPending}
          >
            Replace Role
          </Button>
        </DialogActions>
      </Dialog>

      {/* ─── Create / Edit Escalation Rule Dialog ─────────── */}
      <Dialog open={escDialog.open} onClose={() => setEscDialog({ open: false, config: null })} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ fontWeight: 700 }}>
          {escDialog.config ? 'Edit Escalation Rule' : 'Add Escalation Rule'}
        </DialogTitle>
        <DialogContent dividers>
          <Grid container spacing={2} sx={{ mt: 0.5 }}>
            <Grid item xs={12}>
              <TextField
                label="Escalation Type"
                fullWidth size="small"
                value={escForm.escalation_type}
                onChange={(e) => setEscForm({ ...escForm, escalation_type: e.target.value })}
                placeholder="e.g. SLA_THRESHOLD, OVERDUE"
              />
            </Grid>
            <Grid item xs={4}>
              <TextField
                label="Threshold (hrs)"
                type="number"
                fullWidth size="small"
                value={escForm.threshold_hours}
                onChange={(e) => setEscForm({ ...escForm, threshold_hours: Number(e.target.value) })}
                inputProps={{ min: 1 }}
              />
            </Grid>
            <Grid item xs={4}>
              <TextField
                label="Reminder (hrs)"
                type="number"
                fullWidth size="small"
                value={escForm.reminder_hours}
                onChange={(e) => setEscForm({ ...escForm, reminder_hours: Number(e.target.value) })}
                inputProps={{ min: 1 }}
              />
            </Grid>
            <Grid item xs={4}>
              <TextField
                label="Max Reminders"
                type="number"
                fullWidth size="small"
                value={escForm.max_reminders}
                onChange={(e) => setEscForm({ ...escForm, max_reminders: Number(e.target.value) })}
                inputProps={{ min: 1 }}
              />
            </Grid>
            <Grid item xs={6}>
              <FormControl fullWidth size="small">
                <InputLabel>Escalate To Role</InputLabel>
                <Select
                  value={escForm.escalate_to_role}
                  label="Escalate To Role"
                  onChange={(e) => setEscForm({ ...escForm, escalate_to_role: e.target.value })}
                >
                  {ESCALATION_ROLE_OPTIONS.map((r) => (
                    <MenuItem key={r} value={r}>{roleLabel[r as keyof typeof roleLabel] || r}</MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={6}>
              <FormControl fullWidth size="small">
                <InputLabel>Region (optional)</InputLabel>
                <Select
                  value={escForm.region_id}
                  label="Region (optional)"
                  onChange={(e) => setEscForm({ ...escForm, region_id: e.target.value })}
                >
                  <MenuItem value="">Global (all regions)</MenuItem>
                  {regions.map((r: any) => (
                    <MenuItem key={r.region_id} value={r.region_id}>{r.region_name}</MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => { setEscDialog({ open: false, config: null }); setEscForm(emptyEscForm); }}>Cancel</Button>
          <Button
            variant="contained"
            disabled={!escForm.escalation_type || !escForm.escalate_to_role || createEscMutation.isPending || updateEscMutation.isPending}
            onClick={handleEscSubmit}
          >
            {escDialog.config ? 'Save Changes' : 'Add Rule'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* ─── Delete Escalation Rule Confirmation ─────────── */}
      <Dialog open={escDeleteDialog.open} onClose={() => setEscDeleteDialog({ open: false, config: null })} maxWidth="xs" fullWidth>
        <DialogTitle sx={{ fontWeight: 700 }}>Delete Rule?</DialogTitle>
        <DialogContent dividers>
          <Typography>
            Are you sure you want to delete the <strong>{escDeleteDialog.config?.escalation_type}</strong> escalation rule?
          </Typography>
          <Typography variant="body2" sx={{ mt: 1, color: 'text.secondary' }}>
            This action cannot be undone.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEscDeleteDialog({ open: false, config: null })}>Cancel</Button>
          <Button variant="contained" color="error" disabled={deleteEscMutation.isPending}
            onClick={() => deleteEscMutation.mutate(escDeleteDialog.config.config_id)}>
            Delete
          </Button>
        </DialogActions>
      </Dialog>

      {/* ─── Create / Edit Assignment Rule Dialog ─────────── */}
      <Dialog open={ruleDialog.open} onClose={() => setRuleDialog({ open: false, rule: null })} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ fontWeight: 700 }}>
          {ruleDialog.rule ? 'Edit Assignment Rule' : 'Add Assignment Rule'}
        </DialogTitle>
        <DialogContent dividers>
          <Grid container spacing={2} sx={{ mt: 0.5 }}>
            <Grid item xs={6}>
              <FormControl fullWidth size="small">
                <InputLabel>Approval Role</InputLabel>
                <Select value={ruleForm.role_code} label="Approval Role"
                  onChange={(e) => setRuleForm({ ...ruleForm, role_code: e.target.value })}>
                  {APPROVER_ROLE_OPTIONS.map((r) => (
                    <MenuItem key={r} value={r}>{roleLabel[r as keyof typeof roleLabel] || r}</MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={6}>
              <FormControl fullWidth size="small">
                <InputLabel>Approver User</InputLabel>
                <Select value={ruleForm.user_id} label="Approver User"
                  onChange={(e) => setRuleForm({ ...ruleForm, user_id: e.target.value as string })}>
                  <MenuItem value="">— Not set —</MenuItem>
                  {(users?.items || []).filter((u: any) => u.is_active).map((u: any) => (
                    <MenuItem key={u.user_id} value={u.user_id}>{u.full_name} ({u.soe_id})</MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={6}>
              <FormControl fullWidth size="small">
                <InputLabel>Region (scope)</InputLabel>
                <Select value={ruleForm.region_id} label="Region (scope)"
                  onChange={(e) => setRuleForm({ ...ruleForm, region_id: e.target.value as string, kri_id: '', category_id: '' })}>
                  <MenuItem value="">Global</MenuItem>
                  {(regions as any[]).map((r: any) => (
                    <MenuItem key={r.region_id} value={r.region_id}>{r.region_name}</MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={6}>
              <FormControl fullWidth size="small">
                <InputLabel>Category (scope)</InputLabel>
                <Select value={ruleForm.category_id} label="Category (scope)"
                  onChange={(e) => setRuleForm({ ...ruleForm, category_id: e.target.value as string, kri_id: '' })}>
                  <MenuItem value="">Any category</MenuItem>
                  {(categories as any[]).map((c: any) => (
                    <MenuItem key={c.category_id} value={c.category_id}>{c.category_name}</MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={6}>
              <FormControl fullWidth size="small">
                <InputLabel>KRI (most specific)</InputLabel>
                <Select value={ruleForm.kri_id} label="KRI (most specific)"
                  onChange={(e) => setRuleForm({ ...ruleForm, kri_id: e.target.value as string })}>
                  <MenuItem value="">Any KRI</MenuItem>
                  {allKris.map((k: any) => (
                    <MenuItem key={k.kri_id} value={k.kri_id}>{k.kri_name}</MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={6}>
              <TextField label="Priority" type="number" fullWidth size="small"
                value={ruleForm.priority}
                onChange={(e) => setRuleForm({ ...ruleForm, priority: Number(e.target.value) })}
                inputProps={{ min: 1 }}
                helperText="Lower = higher precedence" />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => { setRuleDialog({ open: false, rule: null }); setRuleForm(emptyRuleForm); }}>Cancel</Button>
          <Button variant="contained"
            disabled={!ruleForm.role_code || createRuleMutation.isPending || updateRuleMutation.isPending}
            onClick={handleRuleSubmit}>
            {ruleDialog.rule ? 'Save Changes' : 'Add Rule'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* ─── Deactivate Assignment Rule Confirmation ──────── */}
      <Dialog open={ruleDeleteDialog.open} onClose={() => setRuleDeleteDialog({ open: false, rule: null })} maxWidth="xs" fullWidth>
        <DialogTitle sx={{ fontWeight: 700 }}>Deactivate Rule?</DialogTitle>
        <DialogContent dividers>
          <Typography>
            Deactivate the <strong>{roleLabel[ruleDeleteDialog.rule?.role_code as keyof typeof roleLabel]}</strong> assignment rule
            {ruleDeleteDialog.rule?.scope_label ? ` for ${ruleDeleteDialog.rule.scope_label}` : ''}?
          </Typography>
          <Typography variant="body2" sx={{ mt: 1, color: 'text.secondary' }}>
            Submissions matching this rule will fall back to the next matching rule, or remain unassigned.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRuleDeleteDialog({ open: false, rule: null })}>Cancel</Button>
          <Button variant="contained" color="error" disabled={deleteRuleMutation.isPending}
            onClick={() => deleteRuleMutation.mutate(ruleDeleteDialog.rule.rule_id)}>
            Deactivate
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
