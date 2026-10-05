// src/lib/api.js
//
// Thin fetch wrapper for every /api/* route in api_server.py. Every call
// attaches X-Init-Data (verified server-side) and X-Username (display
// hint only, never trusted for authorization - see api_server.py).

import { getInitData, getInitDataUnsafe } from './telegram';

const BASE_URL = ''; // same-origin: API server and Mini App are served
                      // from the same host/deployment (one-host setup)

// call() prepends '/api', so paths MUST start with '/' to produce correct URLs:
//   '/bootstrap'  -> /api/bootstrap
//   '/set-phone'  -> /api/set-phone

async function call(method, path, body) {
  const initData = getInitData();
  const unsafe = getInitDataUnsafe();
  const username = unsafe?.user?.username || '';

  let devUserId = null;
  if (!initData || initData.trim() === '') {
    if (!window.__habeshaDevUserId) {
      window.__habeshaDevUserId = 100000 + Math.floor(Math.random() * 900000);
    }
    devUserId = String(window.__habeshaDevUserId);
  }

  const headers = {
    'Content-Type': 'application/json',
    'X-Init-Data': initData || '',
    'X-Username': username,
  };
  if (devUserId) {
    headers['X-Dev-User-Id'] = devUserId;
  }

  const res = await Promise.race([
    fetch(`${BASE_URL}/api${path}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    }),
    new Promise((_, rej) => setTimeout(() => rej(new Error('Network timeout — check your connection')), 15000)),
  ]);

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = data.detail || data;
    const message = typeof detail === 'object' ? (detail.message || detail.error || 'Request failed') : detail;
    const err = new Error(message);
    err.status = res.status;
    err.body = detail;
    throw err;
  }

  return data;
}

export const api = {
  bootstrap: () => call('GET', '/bootstrap'),
  setPhone: (phone) => call('POST', '/set-phone', { phone }),
  setLanguage: (language) => call('POST', '/set-language', { language }),
  markOnboardingSeen: () => call('POST', '/onboarding-seen'),

  getRooms: () => call('GET', '/rooms'),
  getMyActiveGame: () => call('GET', '/my-active-game'),
  getRoomCards: (roomFee) => call('GET', `/rooms/${roomFee}/cards`),
  buyCards: (roomFee, cardIndices) => call('POST', '/buy-cards', { room_fee: roomFee, card_indices: cardIndices }),
  getCardPreview: (cardIndex) => call('GET', `/cards/${cardIndex}/preview`),

  getGameState: (gameId) => call('GET', `/games/${gameId}/state`),
  toggleAutoWin: (gameId, enabled) => call('POST', '/toggle-auto-win', { game_id: gameId, enabled }),
  markNumber: (gameId, cardIndex, number) => call('POST', '/mark-number', { game_id: gameId, card_index: cardIndex, number }),
  claimBingo: (gameId) => call('POST', '/claim-bingo', { game_id: gameId }),

  getDepositAccount: () => call('GET', '/deposit-account'),
  submitDepositSms: (smsText, expectedAmount) => call('POST', '/submit-deposit-sms', { sms_text: smsText, expected_amount: expectedAmount }),
  withdraw: (amount) => call('POST', '/withdraw', { amount }),
  transfer: (toUsername, amount) => call('POST', '/transfer', { to_username: toUsername, amount }),

  getProfile: () => call('GET', '/profile'),
  getTransactions: (limit = 20) => call('GET', `/transactions?limit=${limit}`),
  getReferral: () => call('GET', '/referral'),
  claimDailyBonus: () => call('POST', '/daily-bonus'),
  getJackpot: () => call('GET', '/jackpot'),
  getRecentWinners: () => call('GET', '/recent-winners'),

  // Admin
  getAdminDashboard: () => call('GET', '/admin/dashboard'),
  getAdminWithdrawals: () => call('GET', '/admin/withdrawals'),
  approveWithdrawal: (id) => call('POST', `/admin/withdrawals/${id}/approve`),
  rejectWithdrawal: (id) => call('POST', `/admin/withdrawals/${id}/reject`),
  getAdminDepositAccounts: () => call('GET', '/admin/deposit-accounts'),
  addAdminDepositAccount: (phone, name) => call('POST', '/admin/deposit-accounts', { phone, recipient_name: name }),
  removeAdminDepositAccount: (id) => call('DELETE', `/admin/deposit-accounts/${id}`),
  toggleAdminDepositAccount: (id) => call('POST', `/admin/deposit-accounts/${id}/toggle`),
  adminBroadcast: (message) => call('POST', '/admin/broadcast', { message }),
  adminBroadcastImage: (message, imageUrl, imageFileId) => call('POST', '/admin/broadcast/image', { message, image_url: imageUrl, image_file_id: imageFileId }),
  getAdminHouseWallet: () => call('GET', '/admin/house-wallet'),
  withdrawAdminHouse: (amount) => call('POST', '/admin/house-wallet/withdraw', { amount }),
  forceFinishStuckGame: (gameId) => call('POST', `/admin/games/${gameId}/force-finish`),
};
