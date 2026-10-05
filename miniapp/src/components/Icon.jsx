// src/components/Icon.jsx
// Small stroke-based icon set (currentColor) to replace emoji glyphs.
// Keeps the same call-site simplicity as an emoji string: <Icon name="home" />

const PATHS = {
  home: 'M4 11.5 12 4l8 7.5M6 10v9a1 1 0 0 0 1 1h3v-6h4v6h3a1 1 0 0 0 1-1v-9',
  wallet: 'M3 7a2 2 0 0 1 2-2h11a2 2 0 0 1 2 2v1h1a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Zm14 6.2a1.3 1.3 0 1 0 0-2.6 1.3 1.3 0 0 0 0 2.6Z',
  user: 'M12 12.5a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm-7 8c0-3.6 3.13-6.5 7-6.5s7 2.9 7 6.5',
  dashboard: 'M4 13h6V4H4v9Zm10 7h6V4h-6v16ZM4 20h6v-5H4v5Z',
  cashOut: 'M12 20V6M12 6l-5 5M12 6l5 5M4 20h16',
  bank: 'M3 21h18M4 10h16M4 10l8-6 8 6M6 10v11M10 10v11M14 10v11M18 10v11',
  megaphone: 'M3 11v2a2 2 0 0 0 2 2h1l2 5h2l-1.5-5H12l7 4V6l-7 4H6a2 2 0 0 0-2 2Z',
  ball: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm0-18v18M3.6 8.5h16.8M3.6 15.5h16.8',
  dice: 'M4 4h16v16H4V4Zm4 4v.01M16 8v.01M8 16v.01M16 16v.01M12 12v.01',
  users: 'M9 12.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Zm7-1.2a2.8 2.8 0 1 0 0-5.6 2.8 2.8 0 0 0 0 5.6ZM2.5 20c0-3.3 2.9-6 6.5-6s6.5 2.7 6.5 6M15 14.3c2.9.3 5 2.6 5 5.7',
  coin: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm0-13v8m-2.6-6.2c.3-.9 1.3-1.5 2.6-1.5 1.7 0 3 .9 3 2.1 0 1-.8 1.6-2 1.9l-1 .3c-1.3.3-2.2 1-2.2 2 0 1.2 1.3 2.1 3 2.1 1.3 0 2.4-.6 2.7-1.5',
  live: 'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8ZM5.6 5.6a11 11 0 0 0 0 12.8M18.4 5.6a11 11 0 0 1 0 12.8M8.5 8.5a6.5 6.5 0 0 0 0 7M15.5 8.5a6.5 6.5 0 0 1 0 7',
  waiting: 'M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20Zm0-15v5l3.5 2',
  trophy: 'M8 4h8v3a4 4 0 0 1-8 0V4Zm-4 1h4v2a4 4 0 0 1-4-4Zm16 0h-4v2a4 4 0 0 0 4-4Zm-8 9v3m-3 3h6m-3 0v-3',
  warning: 'M12 3 2 20h20L12 3Zm0 6v5m0 3v.01',
  streak: 'M12 3c1.6 3 5 5.6 5 9.5A5 5 0 0 1 7 12.5C7 9 9.5 6.5 12 3Zm0 11.5a2.5 2.5 0 0 0 2.5-2.5c0-1.6-1.3-2.7-2.5-4-1.2 1.3-2.5 2.4-2.5 4A2.5 2.5 0 0 0 12 14.5Z',
  star: 'm12 3 2.6 5.9 6.4.6-4.8 4.3 1.4 6.3L12 17l-5.6 3.1 1.4-6.3-4.8-4.3 6.4-.6L12 3Z',
  gift: 'M20 8H4v3h16V8Zm-1 3v9a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1v-9m7-3V21M12 8c-1-2-2-4-4-4S5 6 5 7s1 1 2 1M12 8c1-2 2-4 4-4s3 2 3 3-1 1-2 1',
  check: 'm5 13 4 4L19 7',
  back: 'm15 5-7 7 7 7',
  deposit: 'M12 4v12m0 0-4-4m4 4 4-4M5 20h14',
  withdraw: 'M12 20V8m0 0 4 4m-4-4-4 4M5 4h14',
  refund: 'M9 14 4 9l5-5M4 9h11a5 5 0 0 1 0 10h-1',
  sadFace: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18ZM8.5 9.5v.01M15.5 9.5v.01M9 16c1-1.2 2-1.8 3-1.8s2 .6 3 1.8',
  phone: 'M8 3h8a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H8a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Zm4 15h.01',
  swap: 'm7 8 5-5 5 5M12 3v13M17 16l-5 5-5-5M12 21V8',
  copy: 'M9 9h10v10H9V9Zm-4 4H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h11a1 1 0 0 1 1 1v2',
  globe: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm-9-9h18M12 3a13 13 0 0 1 0 18M12 3a13 13 0 0 0 0 18',
  inbox: 'M4 5h16l-1 13a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2L4 5Zm0 8h5l1.5 2h3L15 13h5',
  speakerOn: 'M4 9v6h4l5 4V5L8 9H4Zm12.5-1.5a5 5 0 0 1 0 9M18.5 5a8.5 8.5 0 0 1 0 14',
  speakerOff: 'M4 9v6h4l5 4V5L8 9H4Zm12 1 5 5m0-5-5 5',
};

export default function Icon({ name, size = 18, className = '', style, strokeWidth = 1.8 }) {
  const d = PATHS[name];
  if (!d) return null;
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`icon ${className}`}
      style={{ flexShrink: 0, ...style }}
      aria-hidden="true"
    >
      <path d={d} />
    </svg>
  );
}
