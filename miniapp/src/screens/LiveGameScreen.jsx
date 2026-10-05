// src/screens/LiveGameScreen.jsx
import { useEffect, useState, useRef, useCallback } from 'react';
import { useStore } from '../lib/store';
import { usePolling } from '../lib/usePolling';
import { api } from '../lib/api';
import { fmt, Balance } from '../components/Chrome';
import { haptic, mainButton, showAlert } from '../lib/telegram';
import FadeIn from '../components/FadeIn';
import Icon from '../components/Icon';

const LETTERS = ['B', 'I', 'N', 'G', 'O'];

export default function LiveGameScreen({ gameId, onFinished }) {
  const { runAction, refreshUser } = useStore();
  const [state, setState] = useState(null);
  const [audioOn, setAudioOn] = useState(true);
  const lastSpokenRef = useRef(null);
  const currentAudioRef = useRef(null);
  const gameStartAnnouncedForRef = useRef(null);

  const speakAmharic = useCallback((text, onEnd) => {
    try {
      const synth = window.speechSynthesis;
      if (!synth) { if (onEnd) onEnd(); return; }
      const u = new SpeechSynthesisUtterance(text);
      u.lang = 'am-ET';
      u.rate = 0.95;
      if (onEnd) u.onend = onEnd;
      synth.cancel();
      synth.speak(u);
    } catch { if (onEnd) onEnd(); }
  }, []);

  const playGameStart = useCallback((afterFn) => {
    if (!audioOn) { if (afterFn) afterFn(); return; }
    if (currentAudioRef.current) {
      currentAudioRef.current.pause();
      currentAudioRef.current = null;
    }
    let done = false;
    const proceed = () => {
      if (done) return;
      done = true;
      if (afterFn) afterFn();
    };
    const fallback = () => speakAmharic('ጨዋታው ይጀምራል! መልካም እድል!', proceed);
    const audio = new Audio('/audio/game_started.mp3');
    currentAudioRef.current = audio;
    audio.onended = proceed;
    audio.onerror = fallback;
    audio.play().catch(fallback);
  }, [audioOn, speakAmharic]);

  const playAnnouncement = useCallback((number, lastCall) => {
    if (currentAudioRef.current) {
      currentAudioRef.current.pause();
      currentAudioRef.current = null;
    }
    if (!audioOn) return;
    let fellBack = false;
    const fallback = () => {
      if (!fellBack && lastCall) {
        fellBack = true;
        speakAmharic(`${lastCall.letter} ${lastCall.amharic}`);
      }
    };
    const audio = new Audio(`/audio/${number}.mp3`);
    currentAudioRef.current = audio;
    audio.onerror = fallback;
    audio.play().catch(fallback);
  }, [audioOn, speakAmharic]);

  const fetchGameState = useCallback(async () => {
    const res = await api.getGameState(gameId);
    setState(res);
    if (res.state === 'running') {
      if (gameStartAnnouncedForRef.current !== gameId) {
        gameStartAnnouncedForRef.current = gameId;
        const announceFirstCall = () => {
          if (res.last_call) {
            lastSpokenRef.current = res.last_call.number;
            playAnnouncement(res.last_call.number, res.last_call);
          }
        };
        playGameStart(announceFirstCall);
      } else if (res.last_call) {
        const n = res.last_call.number;
        if (lastSpokenRef.current !== n) {
          lastSpokenRef.current = n;
          playAnnouncement(n, res.last_call);
        }
      }
    }
    if (res.state === 'finished') {
      await refreshUser();
    }
    return res;
  }, [gameId, refreshUser, playAnnouncement, playGameStart]);

  const baseInterval = state === 'running' ? 1500 : 2500;
  const { data, error, loading, resetBackoff } = usePolling(fetchGameState, {
    interval: baseInterval,
    backoffMax: 30000,
    immediate: true,
  });

  useEffect(() => {
    resetBackoff();
  }, [gameId, resetBackoff]);

  const effectiveState = state || data;

  const toggleAuto = async () => {
    if (!effectiveState) return;
    const next = !effectiveState.auto_win;
    haptic.light();
    await runAction(() => api.toggleAutoWin(gameId, next));
    const fresh = await runAction(() => api.getGameState(gameId));
    setState(fresh);
  };

  const claimBingo = async () => {
    haptic.medium();
    try {
      const res = await runAction(() => api.claimBingo(gameId));
      if (res.won) haptic.success();
      // The backend resolves a valid claim synchronously now — don't wait
      // for the next scheduled poll (up to 3s away) to find out. Refresh
      // immediately so the result screen appears right away.
      await fetchGameState();
    } catch {
      // already toasted; still worth refreshing in case the game state
      // moved on anyway (e.g. someone else's claim resolved it first).
      await fetchGameState();
    }
  };

  const markNumber = async (cardIndex, number) => {
    if (!effectiveState) return;

    setState(prev => {
      if (!prev) return prev;
      const nextCards = prev.my_cards.map(card => {
        const hasNumber = (card.grid || []).some(col => col.includes(number));
        if (!hasNumber) return card;
        const isMarked = (card.marked || []).includes(number);
        const newMarked = isMarked
          ? card.marked
          : [...(card.marked || []), number];
        return { ...card, marked: newMarked };
      });
      return { ...prev, my_cards: nextCards };
    });

    haptic.light();
    try {
      const res = await runAction(() => api.markNumber(gameId, cardIndex, number));
      if (res.cards) {
        setState(prev => {
          if (!prev) return prev;
          const byIndex = new Map(res.cards.map(c => [c.card_index, c.marked]));
          const nextCards = prev.my_cards.map(card =>
            byIndex.has(card.card_index) ? { ...card, marked: byIndex.get(card.card_index) } : card
          );
          return { ...prev, my_cards: nextCards };
        });
      }
    } catch {
      // fire-and-forget; next poll reconciles from server
    }
  };

  useEffect(() => {
    // Each card now has its own inline Bingo button, so the native
    // Telegram main button would just be a duplicate of the same action.
    // Make sure it's hidden here instead (it may still be showing from
    // the card-select screen's "Buy" button).
    mainButton.hide();
  }, [effectiveState?.state]);

  if (!effectiveState) {
    return (
      <FadeIn>
        <div className="screen">
          <div className="empty-state">
            <div className="spinner" />
            <div className="empty-state-title">Loading game…</div>
          </div>
        </div>
      </FadeIn>
    );
  }

  if (effectiveState.state === 'waiting') {
    const remaining = effectiveState.countdown_seconds_remaining ?? null;
    const total = effectiveState.countdown_total_seconds || 60;
    return (
      <FadeIn>
        <div className="screen">
          <div className="card waiting-card">
            <div className="text-xl text-bold mb-1">⏳ Waiting for players…</div>
            {remaining !== null && remaining > 0 && (
              <>
                <div className="row mt-2 mb-1">
                  <span className="card-meta">Starting in</span>
                  <span className="text-gold text-bold countdown-text">{remaining}s</span>
                </div>
                <div className="waiting-timer">
                  <div className="waiting-timer-bar" style={{ width: `${(remaining / total) * 100}%` }} />
                </div>
              </>
            )}
            <div className="text-dim text-sm mt-2">Prize pool: {fmt(effectiveState.prize_pool)} ETB</div>
          </div>
        </div>
      </FadeIn>
    );
  }

  if (effectiveState.state === 'finished') {
    return <ResultScreen state={effectiveState} onDone={onFinished} />;
  }

  return (
    <FadeIn>
      <div className="screen">
        <div className="row">
          <div className="text-bold">Bingo {fmt(effectiveState.room_fee)} ETB</div>
          <button
            onClick={() => setAudioOn(v => !v)}
            title={audioOn ? 'Mute number call' : 'Unmute number call'}
            className={`btn-icon ${audioOn ? 'btn-icon-audio-on' : 'btn-icon-audio-off'}`}
          >
            <Icon name={audioOn ? 'speakerOn' : 'speakerOff'} size={17} />
          </button>
          <Balance />
        </div>

        <div className="card">
          <div className="text-xs text-dim mb-1">Call {effectiveState.call_count}/{effectiveState.max_calls}</div>
          {effectiveState.last_call && (
            <div
              className="live-call-number"
              key={`${effectiveState.last_call.letter}-${effectiveState.last_call.number}-${effectiveState.calls?.length ?? 0}`}
            >
              {effectiveState.last_call.letter}-{effectiveState.last_call.number}
            </div>
          )}
          {effectiveState.last_call && (
            <div className="live-call-amharic">{effectiveState.last_call.amharic}</div>
          )}
          {effectiveState.recent_calls && effectiveState.recent_calls.length > 1 && (
            <div className="call-history-strip">
              {effectiveState.recent_calls.slice(1).map((c) => (
                <div className="call-history-pill" key={c.number}>{c.letter}{c.number}</div>
              ))}
            </div>
          )}
          <div className="live-call-meta">
            <span className="row" style={{ gap: 4, justifyContent: 'flex-start', display: 'inline-flex' }}><Icon name="trophy" size={13} className="text-gold" /> Pool: {fmt(effectiveState.prize_pool)} ETB</span>
            {' · '}
            <span className="row" style={{ gap: 4, justifyContent: 'flex-start', display: 'inline-flex' }}><Icon name="users" size={13} /> {effectiveState.player_count} players</span>
            {effectiveState.jackpot && effectiveState.jackpot.current_amount > 0 && (
              <>
                <div className="jackpot-text">
                  <span className="row" style={{ gap: 5, justifyContent: 'flex-start' }}><Icon name="coin" size={14} className="text-gold" /> Jackpot</span>
                  <span className="text-gold">{fmt(effectiveState.jackpot.current_amount)} / 1000 ETB</span>
                </div>
                <div className="jackpot-bar">
                  <div className="jackpot-fill" style={{ width: `${Math.min(100, (effectiveState.jackpot.current_amount / 1000) * 100)}%` }} />
                </div>
              </>
            )}
          </div>
        </div>

        <NumberGrid called={effectiveState.called_numbers} />

        <button
          className={`btn ${effectiveState.auto_win ? 'btn-success' : 'btn-secondary'} btn-block`}
          onClick={toggleAuto}
        >
          <Icon name="ball" size={16} /> Auto-win: {effectiveState.auto_win ? 'ON' : 'OFF'}
        </button>

        {effectiveState.my_cards.map(card => (
          <CardView key={card.card_index} card={card} gameId={gameId} autoWin={effectiveState.auto_win} onMark={markNumber} onClaim={claimBingo} calledNumbers={effectiveState.called_numbers} />
        ))}
      </div>
    </FadeIn>
  );
}

function NumberGrid({ called }) {
  const calledSet = new Set(called);
  const cells = [];
  for (let n = 1; n <= 75; n++) {
    cells.push(
      <div
        key={n}
        className={`number-cell ${calledSet.has(n) ? 'number-cell-called' : ''}`}
      >
        {n}
      </div>
    );
  }
  return (
    <div className="card">
      <div className="number-grid">
        {cells}
      </div>
    </div>
  );
}

function CardView({ card, gameId, autoWin, onMark, onClaim, calledNumbers = [] }) {
  const renderCalledSet = new Set(card.called || []);
  const allowedSet = new Set(calledNumbers);
  const markedSet = new Set(card.marked || []);

  const handleCellClick = async (value) => {
    if (autoWin || value === 0) return;
    if (!allowedSet.has(value)) return;
    await onMark(card.card_index, value);
  };

  const getCellClass = (isFree, isCalled, isMarked) => {
    if (isFree) return 'bingo-cell bingo-cell-free';
    if (isMarked) return 'bingo-cell bingo-cell-marked';
    if (isCalled) return 'bingo-cell bingo-cell-called';
    return 'bingo-cell';
  };

  return (
    <div className="card">
      <div className="text-xs text-dim mb-1">Cartela #{card.card_number}</div>
      <div className="bingo-grid">
        {LETTERS.map(l => (
          <div key={l} className="cell-letter">{l}</div>
        ))}
        {[0, 1, 2, 3, 4].map(row => (
          card.grid.map((col, colIdx) => {
            const value = col[row];
            const isFree = value === 0;
            const isCalled = !isFree && renderCalledSet.has(value);
            const isMarked = !isFree && markedSet.has(value);

            return (
              <div
                key={`${colIdx}-${row}`}
                onClick={() => handleCellClick(value)}
                className={`${getCellClass(isFree, isCalled, isMarked)} ${!isFree && autoWin ? 'bingo-cell-readonly' : ''}`}
              >
                {isFree ? <Icon name="star" size={11} /> : value}
              </div>
            );
          })
        ))}
      </div>
      <button className="btn btn-primary btn-block mt-2" onClick={onClaim}>
        <Icon name="trophy" size={15} /> Bingo!
      </button>
    </div>
  );
}

function ResultScreen({ state, onDone }) {
  const won = state.i_won;
  const winners = state.winner_details && state.winner_details.length
    ? state.winner_details
    : (state.winners || []).map(uid => ({ user_id: uid, username_masked: `User ${uid}`, cards: [] }));

  const confettiColors = ['#f5c94a', '#4be8c0', '#15a854', '#e0b03c'];
  const confettiPieces = won
    ? Array.from({ length: 16 }, (_, i) => ({
        left: (i * 37) % 100,
        delay: (i % 8) * 0.12,
        duration: 1.6 + (i % 5) * 0.2,
        rotate: (i * 53) % 360,
        color: confettiColors[i % confettiColors.length],
      }))
    : [];

  return (
    <FadeIn>
      <div className="screen">
        <div
          className={`card ${won ? 'result-win' : 'result-lose'}`}
          style={{ padding: 28, textAlign: 'center', position: 'relative', overflow: 'hidden' }}
        >
          {won && (
            <div className="confetti-burst" aria-hidden="true">
              {confettiPieces.map((p, i) => (
                <span
                  key={i}
                  className="confetti-piece"
                  style={{
                    left: `${p.left}%`,
                    animationDelay: `${p.delay}s`,
                    animationDuration: `${p.duration}s`,
                    background: p.color,
                    transform: `rotate(${p.rotate}deg)`,
                  }}
                />
              ))}
            </div>
          )}
          <div className="text-3xl" style={{ display: 'flex', justifyContent: 'center', position: 'relative' }}>
            {won
              ? <Icon name="trophy" size={44} className="text-gold result-pop" />
              : <Icon name="sadFace" size={44} className="text-dim" />}
          </div>
          <div className="text-xl text-bold" style={{ marginTop: 8, position: 'relative' }}>
            {won ? 'You won!' : winners.length > 0 ? 'Round over' : 'No winner — refunded'}
          </div>
          {won && (
            <div className="text-gold text-bold result-pop" style={{ fontSize: 28, marginTop: 6, animationDelay: '0.12s', position: 'relative' }}>
              +{fmt(state.per_winner_amount)} ETB
            </div>
          )}
          {!won && winners.length > 0 && (
            <div className="text-dim text-sm mt-1">
              {winners.length} winner{winners.length > 1 ? 's' : ''} took {fmt(state.per_winner_amount)} ETB each
            </div>
          )}
        </div>

        {winners.length > 0 && (
          <div className="card">
            <div className="text-dim text-sm mb-1" style={{ fontWeight: 700 }}>
              <span className="row" style={{ gap: 5, justifyContent: 'flex-start' }}><Icon name="trophy" size={13} className="text-gold" /> Winning card{winners.length > 1 || (winners[0] && winners[0].cards.length > 1) ? 's' : ''}</span>
            </div>
            {winners.map(w => (
              <div key={w.user_id} style={{ paddingTop: 8, borderTop: '1px solid var(--border)' }}>
                <div className="row mb-1">
                  <div className="text-gold text-bold">{w.username_masked}</div>
                </div>
                {(w.cards || []).map(card => (
                  <div key={card.card_number} style={{ marginBottom: 8 }}>
                    <div className="text-dim text-xs mb-1">
                      Cartela #{card.card_number} · {card.pattern}
                    </div>
                    <WinnerCardPreview grid={card.grid} winning={card.winning_numbers} />
                  </div>
                ))}
              </div>
            ))}
          </div>
        )}

        <button className="btn btn-primary btn-block" onClick={onDone}>Back to Lobby</button>
      </div>
    </FadeIn>
  );
}

function WinnerCardPreview({ grid, winning = [] }) {
  const winSet = new Set(winning);
  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 6, padding: 6, background: 'var(--bg-card)' }}>
      <div className="mini-grid">
        {LETTERS.map(l => (
          <div key={l} className="mini-grid-letter">{l}</div>
        ))}
        {[0, 1, 2, 3, 4].map(row => (
          grid.map((col, colIdx) => {
            const value = col[row];
            const isFree = value === 0;
            const won = !isFree && winSet.has(value);
            const cellClass = isFree ? 'mini-grid-cell-free' : won ? 'mini-grid-cell-win' : 'mini-grid-cell';
            return (
              <div key={`${colIdx}-${row}`} className={cellClass}>
                {isFree ? <Icon name="star" size={11} /> : value}
              </div>
            );
          })
        ))}
      </div>
    </div>
  );
}
