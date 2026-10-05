// src/screens/ProfileScreen.jsx
import { useEffect, useState } from 'react';
import { useStore } from '../lib/store';
import { api } from '../lib/api';
import { TopBar, fmt } from '../components/Chrome';
import { haptic } from '../lib/telegram';
import FadeIn from '../components/FadeIn';
import Icon from '../components/Icon';

const TX_ICON = {
  deposit: 'deposit', withdraw: 'withdraw', withdraw_refund: 'refund', transfer_in: 'deposit', transfer_out: 'withdraw',
  bingo_bet: 'dice', bingo_win: 'trophy', bingo_refund: 'refund',
  referral_bonus: 'users', signup_bonus: 'gift', daily_bonus: 'gift',
};

const MILESTONES = [1, 2, 3, 5, 7, 14, 30];
const STREAK_BONUSES = {1: 5, 2: 10, 3: 15, 5: 25, 7: 50, 14: 100, 30: 250};

export default function ProfileScreen() {
  const { user, runAction, refreshUser, showToast } = useStore();
  const [profile, setProfile] = useState(null);
  const [referral, setReferral] = useState(null);
  const [transactions, setTransactions] = useState(null);

  useEffect(() => {
    runAction(() => api.getProfile()).then(setProfile).catch(() => {});
    runAction(() => api.getReferral()).then(setReferral).catch(() => {});
    runAction(() => api.getTransactions(15)).then(r => setTransactions(r.transactions)).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const claimBonus = async () => {
    haptic.light();
    try {
      const res = await runAction(() => api.claimDailyBonus());
      haptic.success();
      showToast(`+${fmt(res.amount)} ETB daily bonus claimed! Streak: ${res.streak_days} day${res.streak_days === 1 ? '' : 's'}`, 'success');
      await refreshUser();
    } catch {
      // already toasted
    }
  };

  const toggleLanguage = async () => {
    const next = user.language === 'am' ? 'en' : 'am';
    await runAction(() => api.setLanguage(next));
    await refreshUser();
  };

  const copyReferralLink = async () => {
    if (!referral) return;
    const message = user.language === 'am'
      ? `🎉 በ ሀበሻ ቤት ቢንጎ ላይ ተቀላቀለኝ! በዚህ ሊንክ ተመዝገብና ${fmt(referral.signup_bonus)} ብር በነፃ አግኝ፦ ${referral.link}`
      : `🎉 Join me on Habesha Bet Bingo! Sign up with my link and get ${fmt(referral.signup_bonus)} ETB free: ${referral.link}`;
    try {
      await navigator.clipboard.writeText(message);
      showToast('Referral message copied!', 'success');
    } catch {
      showToast(message, 'success');
    }
  };

  return (
    <FadeIn>
      <div className="screen">
        <TopBar title="Profile" />

        <div className="card">
          <div className="text-lg text-bold">@{user?.username || user?.user_id}</div>
          <div className="text-sm text-dim mt-1 row" style={{ gap: 5, justifyContent: 'flex-start' }}><Icon name="phone" size={14} /> {user?.phone || 'No phone on file'}</div>
          {profile && <div className="text-xs text-faint mt-1">Joined {profile.joined?.slice(0, 10)}</div>}
        </div>

        {user && (
          <div className="card">
            <div className="text-bold mb-1 row" style={{ gap: 6, justifyContent: 'flex-start' }}><Icon name="streak" size={16} className="text-gold" /> Daily Streak</div>
            <div className="streak-grid">
              {Array.from({ length: 30 }, (_, i) => {
                const day = i + 1;
                const streakDays = user?.daily_streak || 0;
                const isActive = day <= streakDays;
                const isMilestone = MILESTONES.includes(day);
                const nextMilestone = MILESTONES.find(d => d > streakDays);
                const isNext = day === nextMilestone;

                let cls = 'streak-day';
                if (isActive) cls += ' streak-day-active';
                if (isActive && isMilestone) cls += ' streak-day-milestone';

                let label = day;
                if (isActive && isMilestone) label = <Icon name="star" size={12} />;

                return (
                  <div key={day} className={cls} title={`Day ${day}${isMilestone ? ' 🏆' : ''}${isActive ? ' ✓' : ''}`}>
                    {label}
                  </div>
                );
              })}
            </div>
            {user?.next_streak_day && user.next_streak_day <= 30 && (
              <div className="streak-next">
                Next: Day {user.next_streak_day} — <strong>{fmt(user.next_bonus_amount)} ETB</strong>
              </div>
            )}
          </div>
        )}

        <button
          className="btn btn-success btn-block mt-2"
          onClick={claimBonus}
          disabled={!user?.can_claim_bonus}
        >
          {user?.can_claim_bonus ? (
            <span className="row" style={{ gap: 6, justifyContent: 'center' }}><Icon name="gift" size={16} /> Claim Day {user.claim_streak_day} bonus — {fmt(user.claim_bonus_amount)} ETB</span>
          ) : (
            <span className="row" style={{ gap: 6, justifyContent: 'center' }}><Icon name="check" size={16} /> Claimed Streak: {user?.daily_streak ?? 0} day{(user?.daily_streak ?? 0) === 1 ? '' : 's'}</span>
          )}
        </button>

        {referral && (
          <div className="card">
            <div className="text-bold mb-1 row" style={{ gap: 6, justifyContent: 'flex-start' }}><Icon name="users" size={16} className="text-gold" /> Invite Friends</div>
            <div className="text-sm text-dim">
              They get {fmt(referral.signup_bonus)} ETB on joining. You get {fmt(referral.referral_bonus)} ETB when they deposit.
            </div>
            <div className="text-sm mt-1">Referrals so far: <b>{referral.referral_count}</b></div>
            <button className="btn btn-secondary btn-block mt-2" onClick={copyReferralLink}>
              <Icon name="copy" size={15} /> Copy referral link
            </button>
          </div>
        )}

        <button className="btn btn-secondary btn-block" onClick={toggleLanguage}>
          <Icon name="globe" size={15} /> Language: {user?.language === 'am' ? 'አማርኛ' : 'English'} (tap to switch)
        </button>

        <div className="card">
          <div className="text-bold mb-2">Recent Transactions</div>
          {!transactions && (
            <div className="empty-state" style={{ padding: 16 }}>
              <div className="spinner" />
              <div className="text-sm">Loading…</div>
            </div>
          )}
          {transactions?.length === 0 && (
            <div className="empty-state" style={{ padding: 16 }}>
              <div className="empty-state-icon"><Icon name="inbox" size={30} /></div>
              <div className="empty-state-title">No transactions yet.</div>
            </div>
          )}
          {transactions?.map((tx, i) => (
            <div key={i} className="tx-item">
              <span className="text-sm row" style={{ gap: 6, justifyContent: 'flex-start' }}>{TX_ICON[tx.type] ? <Icon name={TX_ICON[tx.type]} size={14} /> : null} {tx.type.replace(/_/g, ' ')}</span>
              <span className={`text-sm ${tx.amount >= 0 ? 'tx-amount-positive' : 'tx-amount-negative'}`}>
                {tx.amount >= 0 ? '+' : ''}{fmt(tx.amount)} ETB
              </span>
            </div>
          ))}
        </div>
      </div>
    </FadeIn>
  );
}
