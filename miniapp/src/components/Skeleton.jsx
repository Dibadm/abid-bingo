// src/components/Skeleton.jsx

export function SkeletonCard() {
  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-sm)' }}>
      <div className="skeleton-line" style={{ width: '60%', height: 18 }} />
      <div className="skeleton-line" style={{ width: '100%', height: 14 }} />
      <div className="skeleton-line" style={{ width: '40%', height: 14 }} />
    </div>
  );
}

export function SkeletonRoomList({ count = 4 }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-md)' }}>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="card" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-sm)' }}>
          <div className="skeleton-line" style={{ width: '50%', height: 18 }} />
          <div className="skeleton-line" style={{ width: '100%', height: 12 }} />
          <div style={{ display: 'flex', gap: 'var(--sp-sm)' }}>
            <div className="skeleton-line" style={{ flex: 1, height: 12 }} />
            <div className="skeleton-line" style={{ flex: 1, height: 12 }} />
          </div>
        </div>
      ))}
    </div>
  );
}
