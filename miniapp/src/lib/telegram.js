// src/lib/telegram.js
//
// Single point of contact with Telegram's Mini App JS bridge
// (window.Telegram.WebApp, injected by the script tag in index.html).
//
// Every other file in this app should import FROM HERE rather than
// touching window.Telegram directly, so:
//   1. There's one place to add a browser-fallback mock for local dev
//      (see DEV_MOCK below) when not running inside actual Telegram.
//   2. If Telegram's API surface changes, only this file needs updating.

const tg = window.Telegram?.WebApp;

// ---------------------------------------------------------------------
// DEV FALLBACK: when opened in a plain browser (not inside Telegram),
// window.Telegram is undefined. Rather than crash the whole app during
// local development, fall back to a mock that returns harmless defaults
// and logs to console instead of calling real Telegram APIs. The
// real initData signature check on the BACKEND will still reject mock
// data if you try to actually call the API while in this mode - this
// only prevents the FRONTEND from crashing while you work on layout.
// ---------------------------------------------------------------------
const isInsideTelegram = !!tg;

if (!isInsideTelegram) {
  console.warn(
    '[telegram.js] Not running inside Telegram - using mock WebApp bridge. ' +
    'API calls requiring real initData will be rejected by the backend (expected).'
  );
}

export function ready() {
  if (isInsideTelegram) tg.ready();
}

export function expand() {
  if (isInsideTelegram) tg.expand();
}

export function getInitData() {
  return isInsideTelegram ? tg.initData : '';
}

export function getInitDataUnsafe() {
  return isInsideTelegram ? tg.initDataUnsafe : { user: { id: 0, username: 'dev', first_name: 'Dev' } };
}

export function getThemeParams() {
  return isInsideTelegram ? tg.themeParams : {};
}

export function getColorScheme() {
  return isInsideTelegram ? tg.colorScheme : 'dark';
}

export function close() {
  if (isInsideTelegram) tg.close();
}

export function showAlert(message) {
  if (isInsideTelegram && tg.showAlert) {
    tg.showAlert(message);
  } else {
    window.alert(message);
  }
}

export function showConfirm(message) {
  return new Promise((resolve) => {
    if (isInsideTelegram && tg.showConfirm) {
      tg.showConfirm(message, (confirmed) => resolve(confirmed));
    } else {
      resolve(window.confirm(message));
    }
  });
}

// Haptic feedback - subtle but makes button presses and wins feel
// substantially more responsive on real devices. No-op outside Telegram.
export const haptic = {
  light() { isInsideTelegram && tg.HapticFeedback?.impactOccurred('light'); },
  medium() { isInsideTelegram && tg.HapticFeedback?.impactOccurred('medium'); },
  heavy() { isInsideTelegram && tg.HapticFeedback?.impactOccurred('heavy'); },
  success() { isInsideTelegram && tg.HapticFeedback?.notificationOccurred('success'); },
  error() { isInsideTelegram && tg.HapticFeedback?.notificationOccurred('error'); },
};

// Telegram's "back" hardware/gesture button (top-left chevron it
// injects into its own chrome). Screens that aren't the home screen
// should show this and pop back to the previous view rather than
// relying solely on in-app back buttons.
export function setBackButton(visible, onClick) {
  if (!isInsideTelegram) return;
  if (visible) {
    tg.BackButton.show();
    tg.BackButton.onClick(onClick);
  } else {
    tg.BackButton.hide();
  }
}

export function offBackButton(handler) {
  if (isInsideTelegram) tg.BackButton.offClick(handler);
}

// Telegram's bottom "MainButton" - a full-width button it renders
// itself below the WebView content, native-looking and respects the
// user's theme. Used for primary actions like "Buy N Cards - X ETB".
export const mainButton = {
  show(text, onClick) {
    if (!isInsideTelegram) return;
    tg.MainButton.setText(text);
    tg.MainButton.onClick(onClick);
    tg.MainButton.show();
  },
  hide() {
    if (isInsideTelegram) tg.MainButton.hide();
  },
  setText(text) {
    if (isInsideTelegram) tg.MainButton.setText(text);
  },
  offClick(handler) {
    if (isInsideTelegram) tg.MainButton.offClick(handler);
  },
  enable() { isInsideTelegram && tg.MainButton.enable(); },
  disable() { isInsideTelegram && tg.MainButton.disable(); },
  showProgress() { isInsideTelegram && tg.MainButton.showProgress(); },
  hideProgress() { isInsideTelegram && tg.MainButton.hideProgress(); },
};

export { isInsideTelegram };
