// src/lib/store.js
//
// Tiny global state via React context - no Redux/Zustand needed for an
// app this size. Holds the current user (refreshed after every balance-
// changing action) and a simple toast queue for error/success messages.

import { createContext, useContext, useState, useCallback } from 'react';
import { api } from './api';

const StoreContext = createContext(null);

export function StoreProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState(null);
  const [fatalError, setFatalError] = useState(null);
  const [balanceHidden, setBalanceHidden] = useState(false);
  const [is_admin, setIsAdmin] = useState(false);

  const showToast = useCallback((message, kind = 'error') => {
    setToast({ message, kind, key: Date.now() });
    window.clearTimeout(window.__toastTimer);
    window.__toastTimer = window.setTimeout(() => setToast(null), 3200);
  }, []);

  const refreshUser = useCallback(async () => {
    try {
      const res = await Promise.race([
        api.bootstrap(),
        new Promise((_, rej) => setTimeout(() => rej(new Error('Request timed out')), 10000)),
      ]);
      setUser(res.user);
      setIsAdmin(Boolean(res.is_admin));
      return res;
    } catch (e) {
      setFatalError(e.message || 'Could not connect to the server.');
      throw e;
    }
  }, []);

  // Toggle balance visibility and refresh the balance from the server
  // (so tapping the eye also re-syncs the latest balance). Declared
  // AFTER refreshUser so the dependency array reads an initialized value.
  const toggleBalance = useCallback(async () => {
    setBalanceHidden(v => !v);
    try {
      await refreshUser();
    } catch { /* ignore network errors here */ }
  }, [refreshUser]);

  const init = useCallback(async () => {
    setLoading(true);
    try {
      await refreshUser();
    } finally {
      setLoading(false);
    }
  }, [refreshUser]);

  // Wraps any api.* call: shows a toast on failure, re-throws so the
  // calling screen can also react (e.g. stop a spinner) if it needs to.
  const runAction = useCallback(async (fn) => {
    try {
      return await fn();
    } catch (e) {
      showToast(e.message || 'Something went wrong.');
      throw e;
    }
  }, [showToast]);

  return (
    <StoreContext.Provider value={{
      user, setUser, loading, init, refreshUser, runAction, showToast, toast, fatalError,
      balanceHidden, toggleBalance, is_admin,
    }}>
      {children}
    </StoreContext.Provider>
  );
}

export function useStore() {
  const ctx = useContext(StoreContext);
  if (!ctx) throw new Error('useStore must be used inside StoreProvider');
  return ctx;
}
