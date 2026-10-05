// src/components/Chrome.jsx
import { useStore } from '../lib/store';
import Icon from './Icon';

const BROADCAST_ENABLED = import.meta.env.VITE_BROADCAST_ENABLED === 'true';

export function TopBar({ title }) {
  const { user } = useStore();
  return (
    <div className="row" style={{ paddingBottom: 4 }}>
      <div className="topbar-title">{title}</div>
      {user && <Balance />}
    </div>
  );
}

// Main balance (hideable via an eye toggle that also re-syncs the
// balance) plus a separate bonus-balance pill (referrals / daily /
// signup bonuses). Used in the TopBar and the in-game headers.
export function Balance() {
  const { user, balanceHidden, toggleBalance } = useStore();
  if (!user) return null;
  const main = Number(user.balance) || 0;
  const bonus = Number(user.bonus_balance) || 0;

  return (
    <div className="balance-compact">
      <div className="balance-compact-inner">
        <div className="balance-chip balance-chip-main" onClick={toggleBalance} title={balanceHidden ? 'Show balances' : 'Hide balances'}>
          <span className="balance-chip-label">Main</span>
          <span>{balanceHidden ? '••••' : `${fmt(main)} ETB`}</span>
        </div>
        {bonus > 0 && !balanceHidden && (
          <div className="balance-chip balance-chip-gold">
            <span className="balance-chip-label">Bonus</span>
            <span>+{fmt(bonus)} ETB</span>
          </div>
        )}
      </div>
    </div>
  );
}

export function fmt(n) {
  const num = Number(n);
  return num % 1 === 0 ? String(num) : num.toFixed(2);
}

const TABS = [
  { key: 'home', icon: 'home', label: 'Home' },
  { key: 'wallet', icon: 'wallet', label: 'Wallet' },
  { key: 'profile', icon: 'user', label: 'Profile' },
];

const ADMIN_TABS = [
  { key: 'admin-dashboard', icon: 'dashboard', label: 'Dashboard' },
  { key: 'admin-withdrawals', icon: 'cashOut', label: 'Withdrawals' },
  { key: 'admin-accounts', icon: 'bank', label: 'Accounts' },
];
if (BROADCAST_ENABLED) {
  ADMIN_TABS.push({ key: 'admin-broadcast', icon: 'megaphone', label: 'Broadcast' });
}
ADMIN_TABS.push(
  { key: 'admin-house', icon: 'home', label: 'House' }
);

export function BottomNav({ active, onChange, adminActive, onAdminChange }) {
  return (
    <div className="bottom-nav">
      <div className="nav-row">
        {TABS.map(t => (
          <button
            key={t.key}
            onClick={() => onChange(t.key)}
            className={`btn nav-item ${active === t.key ? 'nav-item-active' : ''}`}
          >
            <span className="nav-icon"><Icon name={t.icon} size={20} /></span>
            <span className="nav-label">{t.label}</span>
          </button>
        ))}
      </div>
      {adminActive !== undefined && (
        <div className="nav-divider nav-row">
          {ADMIN_TABS.map(t => (
            <button
              key={t.key}
              onClick={() => onAdminChange && onAdminChange(t.key)}
              className={`btn nav-item nav-item-admin ${adminActive === t.key ? 'nav-item-active' : ''}`}
            >
              <span className="nav-icon-admin"><Icon name={t.icon} size={16} /></span>
              <span className="nav-label-admin">{t.label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function Toast() {
  const { toast } = useStore();
  if (!toast) return null;
  return (
    <div className="toast" key={toast.key}>
      {toast.message}
    </div>
  );
}

export function FullScreenLoader() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh' }}>
      <div className="spinner" />
    </div>
  );
}

export function AdminBackHeader({ title, onBack }) {
  return (
    <div className="row" style={{ marginBottom: 4 }}>
      <button
        onClick={onBack}
        className="btn btn-secondary"
        style={{ flex: 'none', padding: '8px 12px', fontSize: 13 }}
      >
        <Icon name="back" size={14} /> Back
      </button>
      <div className="admin-title">{title}</div>
    </div>
  );
}
