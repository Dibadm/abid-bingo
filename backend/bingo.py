
# bingo.py
# ============================================
# HABESHA BET - BINGO GAME LOGIC
#
# Covers:
#   - 200-card deterministic pool (same cards every restart)
#   - Win detection: Line (row/col/diagonal) + Corners only
#   - Amharic number names 1-75
#   - Text card renderer (monospace, for <pre> tags)
#   - Number-grid renderer (1-75 overview)
#   - Ball sequence generator
#   - Username masking helper
# ============================================

import secrets
import random

COLUMNS = [
    ("B",  1, 15),
    ("I", 16, 30),
    ("N", 31, 45),
    ("G", 46, 60),
    ("O", 61, 75),
]
LETTERS = [c[0] for c in COLUMNS]
FREE_SPACE = 0  # center cell (col index 2, row index 2)


# =====================================================================
# CARD GENERATION
# =====================================================================

def _generate_one_card(rng: random.Random) -> list:
    """card[col][row], 0-indexed. card[2][2] = FREE_SPACE."""
    card = []
    for i, (_, low, high) in enumerate(COLUMNS):
        nums = rng.sample(range(low, high + 1), 5)
        if i == 2:
            nums[2] = FREE_SPACE
        card.append(nums)
    return card


def generate_card_pool(size: int = 200, seed: int = None) -> list:
    """Generate a fixed-seed pool of unique bingo cards.
    Same seed = same 200 cards every time the bot restarts.
    Default seed is cryptographically random if not provided."""
    if seed is None:
        seed = secrets.randbits(64)
    rng = random.Random(seed)
    pool = []
    seen = set()
    attempts = 0

    while len(pool) < size and attempts < size * 50:
        card = _generate_one_card(rng)
        fp = tuple(sorted(n for col in card for n in col if n != FREE_SPACE))
        if fp not in seen:
            seen.add(fp)
            pool.append(card)
        attempts += 1

    while len(pool) < size:
        pool.append(_generate_one_card(rng))

    return pool


# Fixed on purpose — this is what makes "card #42" mean the exact same
# 25 numbers in every process (the API server and the bot run as separate
# processes in production) and across every restart/redeploy. A random
# seed here would let the API and the bot silently disagree about what
# each card contains, which breaks manual BINGO claims: the claim looks
# valid against whatever card the player is staring at, but the bot's own
# copy of "card #42" — used to resolve the claim — could be a completely
# different set of numbers.
CARD_POOL_SEED = 20260101
CARD_POOL = generate_card_pool(200, seed=CARD_POOL_SEED)


def get_card(card_index: int) -> list:
    return CARD_POOL[card_index]


# =====================================================================
# WIN DETECTION
# =====================================================================

def _marked(value: int, called: set) -> bool:
    return value == FREE_SPACE or value in called


def check_line_win(card: list, called: set) -> bool:
    for col in range(5):
        if all(_marked(card[col][row], called) for row in range(5)):
            return True
    for row in range(5):
        if all(_marked(card[col][row], called) for col in range(5)):
            return True
    if all(_marked(card[i][i], called) for i in range(5)):
        return True
    if all(_marked(card[4 - i][i], called) for i in range(5)):
        return True
    return False


def check_corners_win(card: list, called: set) -> bool:
    return all(_marked(card[c][r], called) for c, r in [(0, 0), (4, 0), (0, 4), (4, 4)])


def check_win(card: list, called: set) -> bool:
    return check_corners_win(card, called) or check_line_win(card, called)


def get_win_type(card: list, called: set) -> str:
    if check_corners_win(card, called):
        return "corners"
    if check_line_win(card, called):
        return "line"
    return "none"


def get_winning_lines(card: list, called: set) -> list:
    """Return the specific winning line(s) on a card as a list of
    (label, [(col, row), ...]) tuples, so the UI can show exactly which
    pattern the player won and highlight those cells.

    Labels: 'B column'..'O column', 'Row 1'..'Row 5',
    'Diagonal ↘', 'Diagonal ↗', 'Corners'."""
    lines = []
    for col in range(5):
        cells = [(col, row) for row in range(5)]
        if all(_marked(card[c][r], called) for c, r in cells):
            lines.append((f"{LETTERS[col]} column", cells))
    for row in range(5):
        cells = [(col, row) for col in range(5)]
        if all(_marked(card[c][r], called) for c, r in cells):
            lines.append((f"Row {row + 1}", cells))
    diag1 = [(i, i) for i in range(5)]
    if all(_marked(card[i][i], called) for i in range(5)):
        lines.append(("Diagonal ↘", diag1))
    diag2 = [(4 - i, i) for i in range(5)]
    if all(_marked(card[4 - i][i], called) for i in range(5)):
        lines.append(("Diagonal ↗", diag2))
    corners = [(0, 0), (4, 0), (0, 4), (4, 4)]
    if all(_marked(card[c][r], called) for c, r in corners):
        lines.append(("Corners", corners))
    return lines


def evaluate_player_cards(card_indices: list, called_numbers: list) -> list:
    called_set = set(called_numbers)
    return [idx for idx in card_indices if check_win(get_card(idx), called_set)]


def evaluate_player_cards_detailed(card_indices: list, called_numbers: list) -> dict:
    called_set = set(called_numbers)
    winners = {}
    for idx in card_indices:
        win_type = get_win_type(get_card(idx), called_set)
        if win_type != "none":
            winners[idx] = win_type
    return winners


# =====================================================================
# AMHARIC NUMBER NAMES (1-75)
# =====================================================================

_ONES = {
    1: "አንድ",  2: "ሁለት",  3: "ሶስት",  4: "አራት",
    5: "አምስት", 6: "ስድስት", 7: "ሰባት",  8: "ስምንት", 9: "ዘጠኝ",
}
_TEENS = {
    10: "አስር",       11: "አስራ አንድ",  12: "አስራ ሁለት",
    13: "አስራ ሶስት",  14: "አስራ አራት",  15: "አስራ አምስት",
    16: "አስራ ስድስት", 17: "አስራ ሰባት",  18: "አስራ ስምንት",
    19: "አስራ ዘጠኝ",
}
_TENS = {
    20: "ሃያ",  30: "ሰላሳ", 40: "አርባ",
    50: "ሃምሳ", 60: "ስድሳ", 70: "ሰባ",
}


def number_to_amharic(n: int) -> str:
    if n in _ONES:
        return _ONES[n]
    if n in _TEENS:
        return _TEENS[n]
    tens, ones = (n // 10) * 10, n % 10
    if ones == 0:
        return _TENS[tens]
    return f"{_TENS[tens]} {_ONES[ones]}"


def number_to_letter(n: int) -> str:
    for letter, low, high in COLUMNS:
        if low <= n <= high:
            return letter
    return "?"


def format_call_announcement(n: int) -> str:
    return f"{number_to_letter(n)}-{n} ({number_to_amharic(n)})"


# =====================================================================
# CARD RENDERERS
# =====================================================================

def render_card_text(card: list, called_numbers: list, marked_numbers: list = None) -> str:
    called_set = set(called_numbers)
    marked_set = set(marked_numbers or [])
    header = "  ".join(f"{l:^4}" for l in LETTERS)
    divider = "─" * len(header)
    lines = [header, divider]
    for row in range(5):
        cells = []
        for col in range(5):
            v = card[col][row]
            if v == FREE_SPACE:
                cells.append(" FR ")
            elif v in called_set:
                cells.append(f"[{v:2}]")
            elif v in marked_set:
                cells.append(f"*{v:2}*")
            else:
                cells.append(f" {v:2} ")
        lines.append("  ".join(cells))
    return "\n".join(lines)


def render_card_with_label(card_index: int, card: list, called_numbers: list, marked_numbers: list = None) -> str:
    return f"── Cartela #{card_index + 1} ──\n{render_card_text(card, called_numbers, marked_numbers)}"


def render_card_html(card: list, called_numbers: list, marked_numbers: list = None) -> str:
    called_set = set(called_numbers)
    marked_set = set(marked_numbers or [])
    header = "  ".join(f"<b>{l:^4}</b>" for l in LETTERS)
    lines = [header]
    for row in range(5):
        cells = []
        for col in range(5):
            v = card[col][row]
            if v == FREE_SPACE:
                cells.append(" FR ")
            elif v in called_set and v in marked_set:
                cells.append(f"[<b>{v:2}</b>]")
            elif v in called_set:
                cells.append(f" <b>{v:2}</b> ")
            else:
                cells.append(f" {v:2} ")
        lines.append("  ".join(cells))
    return "<pre>" + "\n".join(lines) + "</pre>"


def render_card_html_with_label(card_index: int, card: list, called_numbers: list, marked_numbers: list = None) -> str:
    return f"<b>Cartela #{card_index + 1}</b>\n{render_card_html(card, called_numbers, marked_numbers)}"


def render_number_grid(called_numbers: list) -> str:
    called_set = set(called_numbers)
    lines = []
    for row_start in range(1, 76, 15):
        cells = []
        for n in range(row_start, min(row_start + 15, 76)):
            cells.append(f"[{n:2}]" if n in called_set else f" {n:2} ")
        lines.append(" ".join(cells))
    return "\n".join(lines)


def render_number_grid_html(called_numbers: list) -> str:
    called_set = set(called_numbers)
    lines = []
    for row_start in range(1, 76, 15):
        cells = []
        for n in range(row_start, min(row_start + 15, 76)):
            cells.append(f"<b>{n:2}</b>" if n in called_set else f"{n:2}")
        lines.append(" ".join(cells))
    return "<pre>" + "\n".join(lines) + "</pre>"


# =====================================================================
# BALL SEQUENCE
# =====================================================================

def generate_call_sequence(seed: int = None) -> list:
    nums = list(range(1, 76))
    if seed is None:
        seed = secrets.randbits(64)
    rng = random.Random(seed)
    rng.shuffle(nums)
    return nums


# =====================================================================
# USERNAME MASKING
# =====================================================================

def mask_username(username: str, visible: int = 3) -> str:
    if not username:
        return "@***"
    username = username.lstrip("@")
    return f"@{username[:visible]}***"
