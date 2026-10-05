// src/App.jsx
import React, { Component, Suspense, lazy } from 'react';
import { useEffect, useState } from 'react';
import { StoreProvider, useStore } from './lib/store.jsx';
import { ready, expand, setBackButton, haptic } from './lib/telegram';
import { FullScreenLoader, BottomNav, Toast, AdminBackHeader } from './components/Chrome';

import PhoneCollectScreen from './screens/PhoneCollectScreen';
import OnboardingScreen from './screens/OnboardingScreen';
import HomeScreen from './screens/HomeScreen';
import CardSelectScreen from './screens/CardSelectScreen';
import LiveGameScreen from './screens/LiveGameScreen';
import WalletScreen from './screens/WalletScreen';
import ProfileScreen from './screens/ProfileScreen';

import FadeIn from './components/FadeIn';
import Icon from './components/Icon';

const BROADCAST_ENABLED = import.meta.env.VITE_BROADCAST_ENABLED === 'true';

const AdminDashboard = lazy(() => import('./screens/AdminDashboard'));
const AdminWithdrawals = lazy(() => import('./screens/AdminWithdrawals'));
const AdminAccounts = lazy(() => import('./screens/AdminAccounts'));
const AdminHouseWallet = lazy(() => import('./screens/AdminHouseWallet'));
const AdminBroadcast = BROADCAST_ENABLED ? lazy(() => import('./screens/AdminBroadcast')) : null;

const ADMIN_TABS = ['admin-dashboard', 'admin-withdrawals', 'admin-accounts'];
if (BROADCAST_ENABLED) {
  ADMIN_TABS.push('admin-broadcast');
}
ADMIN_TABS.push('admin-house');
const ADMIN_TAB_TITLES = {
  'admin-dashboard': 'Dashboard',
  'admin-withdrawals': 'Withdrawals',
  'admin-accounts': 'Accounts',
  'admin-broadcast': 'Broadcast',
  'admin-house': 'House Wallet',
};

class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }
  componentDidCatch(error, info) {
    console.error('Screen error:', error, info);
  }
  handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };
  render() {
    if (this.state.hasError) {
      return (
        <div className="screen" style={{ justifyContent: 'center', textAlign: 'center', padding: 24 }}>
          <div style={{ fontSize: 32, marginBottom: 12 }}>😕</div>
          <div style={{ fontWeight: 700, fontSize: 18, marginBottom: 6 }}>Something went wrong</div>
          <div style={{ color: 'var(--color-text-dim)', fontSize: 13, marginBottom: 20 }}>
            {this.state.error?.message || 'An unexpected error occurred.'}
          </div>
          <button className="btn btn-block" onClick={this.handleRetry}>
            Try again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

function AdminScreenLoader() {
  return (
    <div className="screen" style={{ justifyContent: 'center', alignItems: 'center' }}>
      <div className="spinner" />
    </div>
  );
}

function Shell() {
  const { user, loading, init, fatalError, is_admin } = useStore();
  const [view, setView] = useState({ type: 'tab', name: 'home' });
  const [adminView, setAdminView] = useState(null);

  useEffect(() => {
    ready();
    expand();
    init();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const isAdmin = adminView !== null;
    const isRoot = view.type === 'tab' && view.name === 'home';
    if (isAdmin) {
      setBackButton(true, () => setAdminView(null));
      return;
    }
    if (!isRoot) {
      setBackButton(true, () => goHome());
      return;
    }
    setBackButton(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view, adminView]);

  const goHome = () => {
    setView({ type: 'tab', name: 'home' });
    setAdminView(null);
  };
  const enterRoom = (roomFee) => setView({ type: 'push', name: 'cardselect', roomFee });
  const enterGame = (gameId) => setView({ type: 'push', name: 'livegame', gameId });
  const openGame = (gameId) => {
    haptic.light();
    enterGame(gameId);
  };
  const goToAdminTab = (name) => setAdminView(name);

  if (fatalError) {
    return (
      <div className="screen" style={{ justifyContent: 'center', textAlign: 'center' }}>
        <div style={{ display: 'flex', justifyContent: 'center' }}><Icon name="warning" size={32} /></div>
        <div style={{ fontWeight: 700, marginTop: 8 }}>Could not connect</div>
        <div style={{ color: 'var(--color-text-dim)', fontSize: 13, marginTop: 4 }}>{fatalError}</div>
      </div>
    );
  }

  if (loading || !user) return <FullScreenLoader />;

  if (!user.phone) {
    return <PhoneCollectScreen onDone={goHome} />;
  }

  if (!user.onboarding_seen) {
    return <OnboardingScreen onDone={goHome} />;
  }

  const isAdminRoot = ADMIN_TABS.includes(adminView);
  const isRootTab = view.type === 'tab';
  const isAdmin = Boolean(is_admin);

  const renderAdminScreen = () => {
    if (!adminView) return null;
    const onBack = () => setAdminView(null);
    const props = { onBack, key: adminView };
    const screen = (
      <Suspense fallback={<AdminScreenLoader />}>
        {adminView === 'admin-dashboard' && <AdminDashboard {...props} />}
        {adminView === 'admin-withdrawals' && <AdminWithdrawals {...props} />}
        {adminView === 'admin-accounts' && <AdminAccounts {...props} />}
        {adminView === 'admin-broadcast' && AdminBroadcast && <AdminBroadcast {...props} />}
        {adminView === 'admin-house' && <AdminHouseWallet {...props} />}
      </Suspense>
    );
    return <ErrorBoundary>{screen}</ErrorBoundary>;
  };

  return (
    <>
      {isAdminRoot ? (
        <FadeIn key={adminView || 'admin'}>
          {renderAdminScreen()}
        </FadeIn>
      ) : (
        view.name === 'home' && (
          <FadeIn key="home">
            <ErrorBoundary>
              <HomeScreen onEnterRoom={enterRoom} onOpenGame={openGame} />
            </ErrorBoundary>
          </FadeIn>
        )
      )}
      {view.type === 'tab' && view.name === 'wallet' && (
        <ErrorBoundary>
          <WalletScreen />
        </ErrorBoundary>
      )}
      {view.type === 'tab' && view.name === 'profile' && (
        <ErrorBoundary>
          <ProfileScreen />
        </ErrorBoundary>
      )}
      {view.type === 'push' && view.name === 'cardselect' && (
        <ErrorBoundary>
          <CardSelectScreen roomFee={view.roomFee} onBack={goHome} onGameStart={enterGame} />
        </ErrorBoundary>
      )}
      {view.type === 'push' && view.name === 'livegame' && (
        <ErrorBoundary>
          <LiveGameScreen gameId={view.gameId} onFinished={goHome} />
        </ErrorBoundary>
      )}

      {isAdmin && isRootTab && (
        <BottomNav
          active={view.name}
          onChange={(name) => { setView({ type: 'tab', name }); setAdminView(null); }}
          adminActive={adminView}
          onAdminChange={goToAdminTab}
        />
      )}

      {!isAdmin && isRootTab && (
        <BottomNav active={view.name} onChange={(name) => setView({ type: 'tab', name })} />
      )}

      <Toast />
    </>
  );
}

export default function App() {
  return (
    <StoreProvider>
      <Shell />
    </StoreProvider>
  );
}

