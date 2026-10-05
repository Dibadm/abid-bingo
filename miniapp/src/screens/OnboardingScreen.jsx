// src/screens/OnboardingScreen.jsx
import { useState } from 'react';
import { useStore } from '../lib/store';
import { api } from '../lib/api';
import { haptic } from '../lib/telegram';
import FadeIn from '../components/FadeIn';
import Icon from '../components/Icon';

const STEPS = [
  {
    icon: 'ball',
    title: 'How it works',
    body: 'Pick a room, buy a bingo card, and wait for numbers to be called. Match a full line on your card to win a share of the prize pool.',
  },
  {
    icon: 'dice',
    title: 'Auto or manual — your choice',
    body: 'In Auto rooms, your card marks itself as numbers are called. In Manual rooms, you mark your own numbers and tap Bingo! when you\u2019ve won — a bit more skill, same prize pool.',
  },
  {
    icon: 'coin',
    title: 'Jackpot & your wallet',
    body: 'A share of every room feeds a shared jackpot — when it hits 1000 ETB, it\u2019s added straight into that game\u2019s prize pool. Deposit and withdraw anytime via Telebirr in the Wallet tab.',
  },
];

export default function OnboardingScreen({ onDone }) {
  const { runAction, refreshUser } = useStore();
  const [step, setStep] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const isLast = step === STEPS.length - 1;
  const current = STEPS[step];

  const next = async () => {
    haptic.light();
    if (!isLast) {
      setStep(s => s + 1);
      return;
    }
    setSubmitting(true);
    try {
      await runAction(() => api.markOnboardingSeen());
      await refreshUser();
      onDone();
    } catch {
      // already toasted by runAction; let them try again
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <FadeIn>
      <div className="screen screen-center">
        <div className="text-center mb-1">
          <div className="brand-mark">ሀበሻ ቤት</div>
          <div className="text-sm text-dim mt-1">Habesha Bet</div>
        </div>

        <div className="card" style={{ padding: 24, textAlign: 'center' }}>
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 14 }}>
            <Icon name={current.icon} size={40} className="text-gold" />
          </div>
          <div className="text-xl text-bold" style={{ marginBottom: 8 }}>{current.title}</div>
          <div className="text-sm text-dim" style={{ lineHeight: 1.5 }}>{current.body}</div>

          <div className="onboarding-dots">
            {STEPS.map((_, i) => (
              <span key={i} className={`onboarding-dot ${i === step ? 'onboarding-dot-active' : ''}`} />
            ))}
          </div>

          <button className="btn btn-primary btn-block mt-2" onClick={next} disabled={submitting}>
            {submitting ? 'Loading…' : isLast ? 'Get started' : 'Next'}
          </button>
        </div>
      </div>
    </FadeIn>
  );
}
