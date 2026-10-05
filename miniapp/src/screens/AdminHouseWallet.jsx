// src/screens/AdminHouseWallet.jsx
import { useEffect, useState } from 'react';
import { useStore } from '../lib/store';
import { api } from '../lib/api';
import { AdminBackHeader } from '../components/Chrome';
import Icon from '../components/Icon';

export default function AdminHouseWallet({ onBack }) {
  const { runAction, showToast } = useStore();
  const [data, setData] = useState(null);
  const [amount, setAmount] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      const res = await runAction(() => api.getAdminHouseWallet());
      setData(res);
    } catch {
      showToast('Failed to load house wallet.', 'error');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function withdraw() {
    const val = Number(amount);
    if (!val || val <= 0) return;
    setBusy(true);
    try {
      const res = await runAction(() => api.withdrawAdminHouse(val));
      showToast(`Withdrawn ${val} ETB. New balance: ${res.new_balance} ETB`, 'success');
      setAmount('');
      await load();
    } catch {
      showToast('Withdrawal failed.', 'error');
    } finally {
      setBusy(false);
    }
  }

  const fmt = (n) => Number(n).toLocaleString();

  return (
    <div className="screen">
      <AdminBackHeader title="House Wallet" onBack={onBack} />

      {loading ? (
        <div className="card" style={{ textAlign: 'center', color: 'var(--text-dim)' }}>Loading…</div>
      ) : data && (
        <>
          <div className="card" style={{ borderLeft: '3px solid var(--gold-bright)' }}>
            <div style={{ fontSize: 12, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Current Balance (withdrawable)</div>
            <div style={{ fontSize: 28, fontWeight: 700, color: 'var(--gold-bright)', marginTop: 4 }}>{fmt(data.balance)} ETB</div>
          </div>

          <div className="card" style={{ borderLeft: '3px solid var(--green-bright)' }}>
            <div style={{ fontSize: 12, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Total Earned (all time)</div>
            <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--green-bright)', marginTop: 4 }}>{fmt(data.total_earned)} ETB</div>
          </div>

          <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-md)' }}>
            <div>
              <label className="label">Withdrawal Amount (ETB)</label>
              <input
                className="input"
                type="number"
                placeholder="Amount"
                value={amount}
                onChange={e => setAmount(e.target.value)}
              />
            </div>
            <button
              className="btn btn-success btn-block"
              onClick={withdraw}
              disabled={busy || !amount || Number(amount) <= 0 || Number(amount) > data.balance}
            >
              {busy ? 'Processing…' : (<span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}><Icon name="bank" size={15} /> Withdraw from House Wallet</span>)}
            </button>
            {data.balance > 0 && (
              <div style={{ fontSize: 11, color: 'var(--text-faint)', textAlign: 'center' }}>
                Available: {fmt(data.balance)} ETB
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
