// src/screens/AdminDashboard.jsx
import { useEffect, useState } from 'react';
import { useStore } from '../lib/store';
import { api } from '../lib/api';
import { AdminBackHeader } from '../components/Chrome';

export default function AdminDashboard({ onBack }) {
  const { runAction, showToast } = useStore();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => { load(); }, []);

  async function load() {
    setLoading(true);
    try {
      const res = await runAction(() => api.getAdminDashboard());
      setData(res);
    } catch {
      showToast('Failed to load dashboard.', 'error');
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="screen">
        <AdminBackHeader title="Admin Dashboard" onBack={onBack} />
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="card" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-sm)' }}>
            <div className="skeleton-line" style={{ width: '45%', height: 14 }} />
            <div className="skeleton-line" style={{ width: '70%', height: 20 }} />
          </div>
        ))}
      </div>
    );
  }

  if (!data) {
    return (
      <div className="screen">
        <AdminBackHeader title="Admin Dashboard" onBack={onBack} />
        <div className="card" style={{ textAlign: 'center', color: 'var(--text-dim)' }}>Nothing to show.</div>
      </div>
    );
  }

  const fmt = (n) => Number(n).toLocaleString();

  const StatCard = ({ label, value, accent }) => (
    <div className="card" style={{ borderLeft: `3px solid ${accent || 'var(--gold)'}` }}>
      <div style={{ fontSize: 12, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--gold-bright)', marginTop: 4 }}>{value}</div>
    </div>
  );

  return (
    <div className="screen">
      <AdminBackHeader title="Admin Dashboard" onBack={onBack} />

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--sp-md)' }}>
        <StatCard label="Total Users" value={fmt(data.total_users)} accent="var(--green-bright)" />
        <StatCard label="Games Played" value={fmt(data.total_games)} accent="var(--gold-bright)" />
        <StatCard label="Total Deposits (ETB)" value={fmt(data.total_deposits)} accent="var(--green-bright)" />
        <StatCard label="House Commission (ETB)" value={fmt(data.total_house_commission)} accent="var(--gold)" />
        <StatCard label="Net Profit (ETB)" value={fmt(data.net_profit)} accent={Number(data.net_profit) >= 0 ? 'var(--green-bright)' : 'var(--danger)'} />
        <StatCard label="House Balance (ETB)" value={fmt(data.house_balance)} accent="var(--gold-bright)" />
      </div>
    </div>
  );
}
