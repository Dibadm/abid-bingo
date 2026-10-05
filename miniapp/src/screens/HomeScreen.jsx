// src/screens/HomeScreen.jsx
import { useEffect, useState, useCallback } from 'react';
import { useStore } from '../lib/store';
import { usePolling } from '../lib/usePolling';
import { api } from '../lib/api';
import { TopBar, fmt } from '../components/Chrome';
import { haptic } from '../lib/telegram';
import FadeIn from '../components/FadeIn';
import Icon from '../components/Icon';

function timeAgo(isoString) {
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(isoString + 'Z').getTime()) / 1000));
  if (seconds < 60) return 'just now';
  const mins = Math.floor(seconds / 60);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export default function HomeScreen({ onEnterRoom, onOpenGame }) {
  const { user, runAction } = useStore();
  const [rooms, setRooms] = useState(null);
  const [activeGame, setActiveGame] = useState(null);
  const [jackpot, setJackpot] = useState(null);
  const [winners, setWinners] = useState([]);

  const fetchAll = useCallback(async () => {
    const [roomsRes, activeRes, jackpotRes, winnersRes] = await Promise.all([
      api.getRooms(),
      api.getMyActiveGame(),
      api.getJackpot(),
      api.getRecentWinners(),
    ]);
    setRooms(roomsRes.rooms);
    setActiveGame(activeRes.has_game ? activeRes : null);
    setJackpot(jackpotRes.jackpot?.current_amount > 0 ? jackpotRes.jackpot : null);
    setWinners(winnersRes.winners || []);
  });

  const { loading, error } = usePolling(fetchAll, { interval: 10000, backoffMax: 60000 });

  return (
    <FadeIn>
      <div className="screen">
        <TopBar title="ሀበሻ ቤት" />

        {error && (
          <div className="text-sm text-red row" style={{ padding: '8px 12px', background: '#2a0a0a', borderRadius: 8, marginBottom: 8, gap: 6, justifyContent: 'flex-start' }}>
            <Icon name="warning" size={14} /> {error.message || 'Network error'} — retrying…
          </div>
        )}

        {user && (
          <div className="row mt-1">
            <div className="text-sm text-dim">@{user.username || user.user_id}</div>
            <div className="pill pill-gold"><Icon name="streak" size={14} /> {user.daily_streak ?? 0}d streak</div>
          </div>
        )}

        {activeGame && (
          <button
            className="card game-card-active btn-block"
            onClick={() => onOpenGame(activeGame.game_id)}
          >
            <div className="row">
              <div className="text-lg text-bold row" style={{ justifyContent: 'flex-start', gap: 8 }}>
                <Icon name="ball" size={18} /> Open game · Bingo {fmt(activeGame.room_fee)} ETB
              </div>
              <span className={`pill ${activeGame.state === 'running' ? 'pill-live' : ''}`}>
                {activeGame.state === 'running' ? 'Live' : 'Waiting'}
              </span>
            </div>
            <div className="divider" />
            <div className="text-sm text-dim">
              You have {activeGame.my_cards.length} card{activeGame.my_cards.length === 1 ? '' : 's'} in this round — tap to rejoin
            </div>
          </button>
        )}

        {winners.length > 0 && (
          <div className="winners-ticker">
            {winners.slice(0, 5).map((w, i) => (
              <div className="winners-ticker-item" key={i}>
                <Icon name="trophy" size={13} className="text-gold" />
                <span>{w.display_name} won {fmt(w.amount)} ETB · {timeAgo(w.created_at)}</span>
              </div>
            ))}
          </div>
        )}

        <div className="section-title">Pick a room to join the next round</div>

        {!rooms && loading && (
          <div className="empty-state">
            <div className="spinner" />
            <div className="empty-state-title">Loading rooms…</div>
          </div>
        )}

        {!rooms && !loading && (
          <div className="empty-state">
            <div className="empty-state-icon"><Icon name="ball" size={32} /></div>
            <div className="empty-state-title">No rooms available</div>
            <div className="empty-state-body">Check back soon for the next round.</div>
          </div>
        )}

        {rooms && rooms.map(room => (
          <RoomCard
            key={room.room_fee}
            room={room}
            jackpot={room.jackpot}
            onClick={() => {
              haptic.light();
              onEnterRoom(room.room_fee);
            }}
          />
        ))}
      </div>
    </FadeIn>
  );
}

function RoomCard({ room, onClick, jackpot }) {
  const busy = room.state === 'running';
  return (
    <button
      className="card btn-block"
      onClick={onClick}
      disabled={busy}
    >
      <div className="row">
        <div className="text-xl text-bold row" style={{ justifyContent: 'flex-start', gap: 8 }}>
          <Icon name="ball" size={19} className="text-gold" /> Bingo {fmt(room.room_fee)} ETB
        </div>
        {busy ? (
          <span className="pill pill-live">In progress</span>
        ) : (
          <span className="pill pill-green">Open</span>
        )}
      </div>

      <div className="divider" />

      <div className="row">
        <span className="card-meta">Prize pool</span>
        <span className="text-gold text-bold">{fmt(room.prize_pool)} ETB</span>
      </div>
      <div className="row">
        <span className="card-meta">Cards sold</span>
        <span>{room.cards_sold}/{room.card_pool_size}</span>
      </div>
      <div className="row">
        <span className="card-meta">Players</span>
        <span className="row" style={{ gap: 5, justifyContent: 'flex-start' }}><Icon name="users" size={14} className="text-dim" /> {room.player_count}</span>
      </div>
      {jackpot && jackpot.current_amount > 0 && (
        <>
          <div className="jackpot-text">
            <span className="row" style={{ gap: 5, justifyContent: 'flex-start' }}><Icon name="coin" size={14} className="text-gold" /> Jackpot</span>
            <span className="text-gold text-bold">{fmt(jackpot.current_amount)} / 1000 ETB</span>
          </div>
          <div className="jackpot-bar">
            <div className="jackpot-fill" style={{ width: `${Math.min(100, (jackpot.current_amount / 1000) * 100)}%` }} />
          </div>
        </>
      )}
    </button>
  );
}

