// src/screens/CardSelectScreen.jsx
import { useEffect, useState, useCallback } from 'react';
import { useStore } from '../lib/store';
import { usePolling } from '../lib/usePolling';
import { api } from '../lib/api';
import { fmt, Balance } from '../components/Chrome';
import { haptic, mainButton, showAlert } from '../lib/telegram';
import FadeIn from '../components/FadeIn';
import Icon from '../components/Icon';

const LETTERS = ['B', 'I', 'N', 'G', 'O'];

export default function CardSelectScreen({ roomFee, onBack, onGameStart }) {
  const { user, runAction, refreshUser } = useStore();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(new Set());
  const [buying, setBuying] = useState(false);
  const [countdown, setCountdown] = useState(null);
  const [previewCard, setPreviewCard] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  const load = useCallback(async () => {
    const res = await api.getRoomCards(roomFee);
    setData(res);
    setCountdown(res.countdown_seconds_remaining ?? null);
    if (res.state === 'running') {
      onGameStart(res.game_id);
    }
    return res;
  }, [roomFee, onGameStart]);

  const { data: pollData, error: pollError, loading } = usePolling(load, {
    interval: 2000,
    backoffMax: 30000,
  });

  useEffect(() => {
    if (countdown === null) return;
    const t = setInterval(() => {
      setCountdown(c => {
        if (c === null || c <= 0) {
          clearInterval(t);
          return c;
        }
        return c - 1;
      });
    }, 1000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [countdown !== null]);

  if (pollError && !data) {
    return (
      <FadeIn>
        <div className="screen">
          <div className="empty-state">
            <div className="empty-state-icon"><Icon name="warning" size={32} /></div>
            <div className="empty-state-title">Could not load room</div>
            <div className="empty-state-body">{pollError.message || 'Failed to load room'}</div>
            <button className="btn btn-secondary mt-2" onClick={load}>Retry</button>
          </div>
        </div>
      </FadeIn>
    );
  }

  const effectiveData = pollData || data;

  const showPreview = async (idx) => {
    setPreviewLoading(true);
    try {
      const res = await api.getCardPreview(idx);
      setPreviewCard(res);
    } catch {
      setPreviewCard({ card_index: idx, card_number: idx + 1, grid: null });
    } finally {
      setPreviewLoading(false);
    }
  };

  const randomPick = (count) => {
    if (!effectiveData) return;
    const taken = new Set([...effectiveData.taken_cards, ...effectiveData.my_cards, ...selected]);
    const available = [];
    for (let i = 0; i < effectiveData.card_pool_size; i++) {
      if (!taken.has(i)) available.push(i);
    }
    available.sort(() => Math.random() - 0.5);
    const roomLeft = effectiveData.max_cards_per_player - effectiveData.my_cards.length - selected.size;
    const toAdd = available.slice(0, Math.min(count, roomLeft));
    if (toAdd.length === 0) {
      showAlert(`You can hold at most ${effectiveData.max_cards_per_player} cards per round.`);
      return;
    }
    setSelected(prev => new Set([...prev, ...toAdd]));
    haptic.medium();
  };

  const confirmPurchase = useCallback(async (indices) => {
    const toBuy = indices ?? [...selected];
    if (toBuy.length === 0) return;
    setBuying(true);
    try {
      await runAction(() => api.buyCards(roomFee, toBuy));
      haptic.success();
      setSelected(prev => {
        const next = new Set(prev);
        toBuy.forEach(i => next.delete(i));
        return next;
      });
      await refreshUser();
      const fresh = await load();
      if (fresh.state === 'running') onGameStart(fresh.game_id);
    } catch {
      await load();
    } finally {
      setBuying(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected, roomFee]);

  useEffect(() => {
    if (!effectiveData) return;
    const cost = selected.size * roomFee;
    if (selected.size === 0) {
      mainButton.hide();
      return;
    }
    mainButton.show(`Buy ${selected.size} card${selected.size > 1 ? 's' : ''} — ${fmt(cost)} ETB`, confirmPurchase);
    return () => mainButton.offClick(confirmPurchase);
  }, [effectiveData, selected, roomFee, confirmPurchase]);

  if (!effectiveData && !error) {
    return (
      <FadeIn>
        <div className="screen">
          <div className="empty-state">
            <div className="spinner" />
            <div className="empty-state-title">Loading…</div>
          </div>
        </div>
      </FadeIn>
    );
  }

  if (!effectiveData) {
    return (
      <FadeIn>
        <div className="screen">
          <div className="empty-state">
            <div className="empty-state-icon"><Icon name="warning" size={32} /></div>
            <div className="empty-state-title">Could not load room</div>
            <div className="empty-state-body">{error?.message || 'Failed to load room'}</div>
            <button className="btn btn-secondary mt-2" onClick={load}>Retry</button>
          </div>
        </div>
      </FadeIn>
    );
  }

  return (
    <FadeIn>
      <div className="screen">
        <div className="row">
          <button className="btn btn-secondary btn-sm" onClick={onBack}><Icon name="back" size={15} /> Back</button>
          <div className="text-bold">Bingo {fmt(roomFee)} ETB</div>
          <Balance />
        </div>

        <div className="card">
          <div className="row">
            <span className="card-meta">Prize Pool</span>
            <span className="text-gold text-bold">{fmt(effectiveData.prize_pool)} ETB</span>
          </div>
          <div className="row">
            <span className="card-meta">Cards sold</span>
            <span>{effectiveData.cards_sold}/{effectiveData.card_pool_size}</span>
          </div>
          {effectiveData.jackpot && effectiveData.jackpot.current_amount > 0 && (
            <>
              <div className="jackpot-text">
                <span className="row" style={{ gap: 5, justifyContent: 'flex-start' }}><Icon name="coin" size={14} className="text-gold" /> Jackpot</span>
                <span className="text-gold text-bold">{fmt(effectiveData.jackpot.current_amount)} / 1000 ETB</span>
              </div>
              <div className="jackpot-bar">
                <div className="jackpot-fill" style={{ width: `${Math.min(100, (effectiveData.jackpot.current_amount / 1000) * 100)}%` }} />
              </div>
            </>
          )}
        </div>

        {effectiveData.my_cards.length > 0 && (
          <div className="pill pill-gold">You already hold {effectiveData.my_cards.length} card{effectiveData.my_cards.length > 1 ? 's' : ''} this round</div>
        )}

        {effectiveData.my_cards.length > 0 && (
          <button className="btn btn-primary btn-block mb-1" onClick={() => onGameStart(effectiveData.game_id)}>
            <Icon name="ball" size={17} /> Open My Game
          </button>
        )}

        {countdown !== null && countdown > 0 && (
          <div className="card waiting-card">
            <div className="row mb-1">
              <span className="card-meta">Game starting in</span>
              <span className="text-live text-bold countdown-text">{countdown}s</span>
            </div>
            <div className="waiting-timer">
              <div
                className="waiting-timer-bar"
                style={{ width: `${(countdown / (effectiveData?.countdown_total_seconds || 60)) * 100}%` }}
              />
            </div>
          </div>
        )}

        {countdown === 0 && effectiveData?.state === 'waiting' && (
          <div className="card waiting-card">
            <span className="text-live text-bold">Starting…</span>
          </div>
        )}

        <div className="btn-row">
          <button className="btn btn-secondary flex-1" onClick={() => randomPick(1)}><Icon name="dice" size={16} /> Random x1</button>
          <button className="btn btn-secondary flex-1" onClick={() => randomPick(2)}><Icon name="dice" size={16} /> Random x2</button>
        </div>

        <CardGrid
          poolSize={effectiveData.card_pool_size}
          taken={effectiveData.taken_cards}
          mine={effectiveData.my_cards}
          selected={selected}
          onToggle={toggle}
          onPreview={showPreview}
        />

        {previewCard && (
          <div className="modal-overlay" onClick={() => setPreviewCard(null)}>
            <div className="modal-card" onClick={(e) => e.stopPropagation()}>
              <div className="text-bold mb-1">Card #{previewCard.card_number}</div>
              {previewCard.grid ? (
                <div className="mini-grid">
                  {LETTERS.map(l => (
                    <div key={l} className="mini-grid-letter">{l}</div>
                  ))}
                  {[0, 1, 2, 3, 4].map(row =>
                    previewCard.grid.map((col, colIdx) => {
                      const value = col[row];
                      const isFree = value === 0;
                      return (
                        <div
                          key={`${colIdx}-${row}`}
                          className={`mini-grid-cell ${isFree ? 'mini-grid-cell-free' : ''}`}
                        >
                          {isFree ? <Icon name="star" size={11} /> : value}
                        </div>
                      );
                    })
                  )}
                </div>
              ) : previewLoading ? (
                <div className="empty-state" style={{ padding: 16 }}>
                  <div className="spinner" />
                  <div className="text-sm">Loading preview…</div>
                </div>
              ) : (
                <div className="text-dim text-sm text-center">Preview unavailable</div>
              )}
              <div className="btn-row mt-2">
                <button className="btn btn-secondary" onClick={() => setPreviewCard(null)}>Cancel</button>
                {!effectiveData.taken_cards.includes(previewCard.card_index) && !effectiveData.my_cards.includes(previewCard.card_index) && (
                  <button
                    className="btn btn-primary"
                    disabled={buying}
                    onClick={() => {
                      const idx = previewCard.card_index;
                      setPreviewCard(null);
                      confirmPurchase([idx]);
                    }}
                  >
                    {buying ? 'Buying…' : `Buy — ${fmt(roomFee)} ETB`}
                  </button>
                )}
              </div>
            </div>
          </div>
        )}

        {buying && (
          <div className="empty-state" style={{ padding: 12 }}>
            <div className="spinner" />
            <div className="text-sm">Processing purchase…</div>
          </div>
        )}
      </div>
    </FadeIn>
  );
}

function CardGrid({ poolSize, taken, mine, selected, onToggle, onPreview }) {
  const takenSet = new Set(taken);
  const mineSet = new Set(mine);

  const cells = [];
  for (let i = 0; i < poolSize; i++) {
    const isTaken = takenSet.has(i);
    const isMine = mineSet.has(i);
    const isSelected = selected.has(i);

    let cellClass = 'card-cell';
    if (isMine) cellClass = 'card-cell-mine';
    else if (isTaken) cellClass = 'card-cell-taken';
    else if (isSelected) cellClass = 'card-cell-selected';

    const handleClick = () => {
      if (isTaken || isMine) return;
      if (onPreview) {
        onPreview(i);
      } else if (onToggle) {
        onToggle(i);
      }
    };

    cells.push(
      <button
        key={i}
        onClick={handleClick}
        disabled={isTaken || isMine}
        className={cellClass}
      >
        {i + 1}
      </button>
    );
  }

  return <div className="card-grid">{cells}</div>;
}
