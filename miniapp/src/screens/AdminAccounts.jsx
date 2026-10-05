// src/screens/AdminAccounts.jsx
import { useEffect, useState } from 'react';
import { useStore } from '../lib/store';
import { api } from '../lib/api';
import { AdminBackHeader } from '../components/Chrome';
import { haptic } from '../lib/telegram';
import Icon from '../components/Icon';

const TAB_LABELS = ['Deposit Accounts', 'Add New'];

export default function AdminAccounts({ onBack }) {
  const { runAction, showToast } = useStore();
  const [accounts, setAccounts] = useState([]);
  const [tab, setTab] = useState('list');
  const [phone, setPhone] = useState('');
  const [name, setName] = useState('');
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [busyIds, setBusyIds] = useState(new Set());

  async function load() {
    setLoading(true);
    try {
      const res = await runAction(() => api.getAdminDepositAccounts());
      setAccounts(res.accounts || []);
    } catch {
      showToast('Failed to load accounts.', 'error');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  function isBusy(id) {
    return busyIds.has(id);
  }

  function markBusy(id) {
    setBusyIds(prev => new Set(prev).add(id));
  }

  function clearBusy(id) {
    setBusyIds(prev => {
      const next = new Set(prev);
      next.delete(id);
      return next;
    });
  }

  async function addAccount() {
    const trimmed = phone.trim();
    if (!trimmed || !name.trim()) return;
    if (!trimmed.startsWith('251') || trimmed.length !== 12 || !/^\d+$/.test(trimmed)) {
      showToast('Phone must be 12 digits starting with 251 (e.g. 251912345678).', 'error');
      return;
    }
    setSubmitting(true);
    try {
      await runAction(() => api.addAdminDepositAccount(trimmed, name.trim()));
      showToast('Deposit account added.', 'success');
      setPhone('');
      setName('');
      setTab('list');
      await load();
    } catch {
      showToast('Failed to add account.', 'error');
    } finally {
      setSubmitting(false);
    }
  }

  async function removeAccount(acc) {
    haptic.light();
    markBusy(acc.id);
    try {
      await runAction(() => api.removeAdminDepositAccount(acc.id));
      showToast(`Removed account #${acc.id}.`, 'success');
      await load();
    } catch {
      showToast('Failed to remove account.', 'error');
    } finally {
      clearBusy(acc.id);
    }
  }

  async function toggleAccount(acc) {
    haptic.light();
    markBusy(acc.id);
    try {
      await runAction(() => api.toggleAdminDepositAccount(acc.id));
      showToast(`Account #${acc.id} toggled.`, 'success');
      await load();
    } catch {
      showToast('Failed to toggle account.', 'error');
    } finally {
      clearBusy(acc.id);
    }
  }

  return (
    <div className="screen">
      <AdminBackHeader title="Account Management" onBack={onBack} />

      <div style={{ display: 'flex', gap: 'var(--sp-sm)' }}>
        {TAB_LABELS.map((l, i) => (
          <button
            key={l}
            className="btn"
            style={{
              flex: 1, padding: '9px 0', fontSize: 13,
              background: tab === (i === 0 ? 'list' : 'add') ? 'var(--gold)' : 'var(--bg-elevated)',
              color: tab === (i === 0 ? 'list' : 'add') ? '#1a1306' : 'var(--text-dim)',
            }}
            onClick={() => { haptic.light(); setTab(i === 0 ? 'list' : 'add'); }}
          >
            {l}
          </button>
        ))}
      </div>

      {tab === 'list' && (
        <>
          {loading && (
            <div className="card" style={{ textAlign: 'center', color: 'var(--text-dim)' }}>
              Loading accounts…
            </div>
          )}
          {!loading && accounts.length === 0 && (
            <div className="card" style={{ textAlign: 'center', color: 'var(--text-dim)', fontSize: 14 }}>
              No deposit accounts configured.
            </div>
          )}
          {accounts.map(acc => (
            <div key={acc.id} className="card" style={{ opacity: isBusy(acc.id) ? 0.5 : 1 }}>
              <div className="row">
                <div>
                  <div style={{ fontWeight: 700, fontSize: 16, display: 'flex', alignItems: 'center', gap: 6 }}><Icon name="phone" size={15} /> {acc.phone}</div>
                  <div style={{ fontSize: 13, color: 'var(--text-dim)' }}>{acc.recipient_name}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-faint)', marginTop: 2 }}>
                    #{acc.id} · {acc.deposit_count} deposits · {acc.active ? '● Active' : '○ Inactive'}
                  </div>
                </div>
                <button
                  className="btn"
                  disabled={isBusy(acc.id)}
                  style={{ flex: 'none', padding: '6px 10px', fontSize: 12, color: 'var(--danger)', borderColor: 'var(--danger)', background: 'transparent' }}
                  onClick={() => toggleAccount(acc)}
                >
                  {isBusy(acc.id) ? '…' : (acc.active ? 'Deactivate' : 'Activate')}
                </button>
                <button
                  className="btn"
                  disabled={isBusy(acc.id)}
                  style={{ flex: 'none', padding: '6px 10px', fontSize: 12, color: 'var(--danger)', borderColor: 'var(--danger)', background: 'transparent', marginLeft: 4 }}
                  onClick={() => removeAccount(acc)}
                >
                  {isBusy(acc.id) ? '…' : 'Remove'}
                </button>
              </div>
            </div>
          ))}
        </>
      )}

      {tab === 'add' && (
        <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-md)' }}>
          <div>
            <label className="label">Phone (2519xxxxxxx)</label>
            <input
              className="input"
              placeholder="251912345678"
              value={phone}
              onChange={e => setPhone(e.target.value)}
            />
          </div>
          <div>
            <label className="label">Recipient Name</label>
            <input className="input" placeholder="Account holder name" value={name} onChange={e => setName(e.target.value)} />
          </div>
          <button
            className="btn btn-primary btn-block"
            onClick={() => { haptic.light(); addAccount(); }}
            disabled={submitting || !phone.trim() || !name.trim()}
          >
            {submitting ? 'Saving…' : 'Add Account'}
          </button>
        </div>
      )}
    </div>
  );
}
