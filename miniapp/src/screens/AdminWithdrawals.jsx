// src/screens/AdminWithdrawals.jsx
import { useEffect, useState } from 'react';
import { useStore } from '../lib/store';
import { api } from '../lib/api';
import { AdminBackHeader, fmt } from '../components/Chrome';
import Icon from '../components/Icon';

export default function AdminWithdrawals({ onBack }) {
  const { runAction, showToast } = useStore();
  const [list, setList] = useState(null);
  const [busy, setBusy] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const res = await runAction(() => api.getAdminWithdrawals());
      setList(res.withdrawals || []);
    } catch {
      showToast('Failed to load withdrawals.', 'error');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function refresh() {
    setRefreshing(true);
    await load();
    setRefreshing(false);
    showToast('Withdrawals refreshed.', 'success');
  }

  function statusColor(s) {
    if (s === 'completed') return 'var(--green-bright)';
    if (s === 'rejected') return 'var(--danger)';
    return 'var(--gold)';
  }

  async function approve(wd) {
    setBusy(wd.id);
    try {
      await runAction(() => api.approveWithdrawal(wd.id));
      showToast(`Approved withdrawal #${wd.id}`, 'success');
      await load();
    } catch {
      showToast('Approve failed.', 'error');
    } finally {
      setBusy(null);
    }
  }

  async function reject(wd) {
    setBusy(wd.id);
    try {
      await runAction(() => api.rejectWithdrawal(wd.id));
      showToast(`Rejected withdrawal #${wd.id}`, 'success');
      await load();
    } catch {
      showToast('Reject failed.', 'error');
    } finally {
      setBusy(null);
    }
  }

  const pending = (list || []).filter(w => w.status === 'pending');

  return (
    <div className="screen">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <AdminBackHeader title="Withdrawals" onBack={onBack} />
        <button
          className="btn btn-icon"
          onClick={refresh}
          disabled={refreshing || loading}
          style={{ marginBottom: 8 }}
        >
          {refreshing ? '…' : '↻'}
        </button>
      </div>

      {loading && (
        <div className="card" style={{ textAlign: 'center', color: 'var(--text-dim)' }}>
          <div className="skeleton-line" style={{ width: '80%', height: 14, margin: '0 auto' }} />
        </div>
      )}

      {!loading && pending.length === 0 && (
        <div className="card" style={{ textAlign: 'center', color: 'var(--text-dim)', fontSize: 14 }}>
          ✓ No pending withdrawals.
        </div>
      )}

      {pending.map(wd => (
        <div key={wd.id} className="card" style={{ opacity: busy === wd.id ? 0.6 : 1, borderLeft: '3px solid var(--gold)' }}>
          <div className="row">
            <div>
              <div style={{ fontWeight: 700, display: 'flex', alignItems: 'center', gap: 6 }}><Icon name="user" size={14} /> User #{wd.user_id}</div>
              <div style={{ fontSize: 12, color: 'var(--text-dim)' }}>{wd.phone}</div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontWeight: 700, color: 'var(--gold-bright)', fontSize: 16 }}>{fmt(wd.amount)} ETB</div>
              <div style={{ fontSize: 11, color: statusColor(wd.status) }}>{wd.status}</div>
            </div>
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-faint)', marginTop: 4 }}>#{wd.id} · {wd.created_at?.slice(0, 19)}</div>
          <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
            <button
              className="btn btn-success"
              style={{ flex: 1, padding: '9px 0', fontSize: 13 }}
              onClick={() => approve(wd)}
              disabled={busy === wd.id}
            >
              {busy === wd.id ? '…' : '✓ Approve'}
            </button>
            <button
              className="btn btn-secondary"
              style={{ flex: 1, padding: '9px 0', fontSize: 13, color: 'var(--danger)', borderColor: 'var(--danger)' }}
              onClick={() => reject(wd)}
              disabled={busy === wd.id}
            >
              {busy === wd.id ? '…' : '✗ Reject'}
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
