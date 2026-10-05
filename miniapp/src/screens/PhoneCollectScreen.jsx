// src/screens/PhoneCollectScreen.jsx
import { useState } from 'react';
import { useStore } from '../lib/store';
import { api } from '../lib/api';
import { haptic } from '../lib/telegram';
import FadeIn from '../components/FadeIn';
import Icon from '../components/Icon';

export default function PhoneCollectScreen({ onDone }) {
  const { runAction, refreshUser, showToast } = useStore();
  const [phone, setPhone] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const submit = async () => {
    if (phone.trim().length < 8) {
      showToast('Enter a valid phone number.');
      return;
    }
    setSubmitting(true);
    try {
      await runAction(() => api.setPhone(phone.trim()));
      haptic.success();
      await refreshUser();
      onDone();
    } catch {
      // already toasted
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

        <div className="card">
          <div className="text-sm text-dim mb-2">
            <span className="row" style={{ gap: 6, justifyContent: 'flex-start', alignItems: 'flex-start' }}><Icon name="phone" size={15} style={{ marginTop: 2 }} /> Enter your Telebirr phone number so we can send your withdrawals here.</span>
          </div>
          <input
            className="input"
            placeholder="09XXXXXXXX"
            value={phone}
            onChange={e => setPhone(e.target.value)}
            inputMode="tel"
          />
          <button className="btn btn-primary btn-block mt-2" onClick={submit} disabled={submitting}>
            {submitting ? 'Saving…' : 'Continue'}
          </button>
        </div>
      </div>
    </FadeIn>
  );
}
