// src/screens/AdminBroadcast.jsx
import { useState } from 'react';
import { useStore } from '../lib/store';
import { api } from '../lib/api';
import { AdminBackHeader } from '../components/Chrome';
import Icon from '../components/Icon';

export default function AdminBroadcast({ onBack }) {
  const { runAction, showToast } = useStore();
  const [message, setMessage] = useState('');
  const [sendImage, setSendImage] = useState(false);
  const [imageUrl, setImageUrl] = useState('');
  const [imageFileId, setImageFileId] = useState('');
  const [submitting, setSubmitting] = useState(false);

  async function send() {
    if (!message.trim() && !sendImage) return;
    setSubmitting(true);
    try {
      const res = await runAction(() => api.adminBroadcastImage(
        message.trim(),
        sendImage ? imageUrl.trim() : undefined,
        sendImage ? imageFileId.trim() : undefined
      ));
      showToast(`Broadcast sent: ${res.sent} delivered, ${res.failed} failed.`, 'success');
      setMessage('');
      setImageUrl('');
      setImageFileId('');
    } catch {
      showToast('Broadcast failed.', 'error');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="screen">
      <AdminBackHeader title="Broadcast Message" onBack={onBack} />

      <div className="card" style={{ borderLeft: '3px solid var(--gold)' }}>
        <div style={{ fontSize: 13, color: 'var(--text-dim)', marginBottom: 'var(--sp-sm)' }}>
          Send a message to ALL registered users. This is sent through the bot — do NOT abuse this feature.
        </div>
        <div style={{ fontSize: 12, color: 'var(--text-faint)' }}>
          The bot must be online and running for broadcasts to deliver.
        </div>
      </div>

      <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-md)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <input
            type="checkbox"
            id="sendImage"
            checked={sendImage}
            onChange={e => setSendImage(e.target.checked)}
          />
          <label htmlFor="sendImage" style={{ fontSize: 14, color: 'var(--text)' }}>Send image</label>
        </div>

        {sendImage && (
          <>
            <div>
              <label className="label">Image URL (or Telegram file_id)</label>
              <input
                className="input"
                placeholder="https://example.com/image.jpg or file_id"
                value={imageFileId || imageUrl}
                onChange={e => {
                  const val = e.target.value;
                  if (val.startsWith('http')) {
                    setImageUrl(val);
                    setImageFileId('');
                  } else {
                    setImageFileId(val);
                    setImageUrl('');
                  }
                }}
              />
            </div>
            {imageUrl && (
              <div>
                <label className="label">Preview</label>
                <img src={imageUrl} alt="Preview" style={{ maxWidth: '100%', borderRadius: 8, border: '1px solid var(--border)' }} onError={e => { e.target.style.display = 'none'; }} />
              </div>
            )}
          </>
        )}

        <div>
          <label className="label">Message</label>
          <textarea
            className="input"
            placeholder="Hello everyone! 🎉"
            value={message}
            onChange={e => setMessage(e.target.value)}
            rows={6}
          />
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: 12, color: 'var(--text-faint)' }}>
            {message.length} characters
          </span>
          <button
            className="btn btn-primary"
            onClick={send}
            disabled={submitting || (!message.trim() && !sendImage)}
            style={{ minWidth: 120 }}
          >
            {submitting ? 'Sending…' : (<span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}><Icon name="megaphone" size={15} /> Broadcast</span>)}
          </button>
        </div>
      </div>
    </div>
  );
}
