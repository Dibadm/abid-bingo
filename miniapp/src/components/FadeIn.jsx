// src/components/FadeIn.jsx
import { useEffect, useRef } from 'react';

export default function FadeIn({ children, className = '', delay = 0 }) {
  const ref = useRef(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.opacity = '0';
    el.style.transform = 'translateY(6px)';
    const t = setTimeout(() => {
      el.style.transition = 'opacity 0.22s ease-out, transform 0.22s ease-out';
      el.style.opacity = '1';
      el.style.transform = 'translateY(0)';
    }, delay);
    return () => clearTimeout(t);
  }, [delay]);

  return (
    <div ref={ref} className={className}>
      {children}
    </div>
  );
}
