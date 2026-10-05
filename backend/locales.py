# locales.py
# ============================================
# HABESHA BET - BILINGUAL TEXT DICTIONARY
#
# All user-facing strings in English ("en") and Amharic ("am").
# Use get_text(key, lang, **kwargs) everywhere in bot.py.
# {placeholders} in values are filled by format(**kwargs).
# ============================================

STRINGS = {

    # ──────────────────────────────────────────
    # ONBOARDING
    # ──────────────────────────────────────────
    "welcome_new": {
        "en": (
            "👋 Welcome to <b>Habesha Bet</b>!\n\n"
            "To get started, please share your phone number so we can\n"
            "process withdrawals to your Telebirr account.\n\n"
            "Tap the button below 👇"
        ),
        "am": (
            "👋 እንኳን ደህና መጡ ወደ <b>ሀበሻ ቤት</b>!\n\n"
            "ለመጀመር፣ ገንዘብ ወደ ቴሌብር አካውንትዎ ለማስተላለፍ\n"
            "የስልክ ቁጥርዎን ያጋሩን።\n\n"
            "ከታች ያለውን ቁልፍ ይጫኑ 👇"
        ),
    },
    "share_phone_button": {
        "en": "📱 Share Phone Number",
        "am": "📱 ስልክ ቁጥር አጋራ",
    },
    "phone_saved": {
        "en": "✅ Phone number saved! Welcome to Habesha Bet 🎉",
        "am": "✅ ስልክ ቁጥር ተቀምጧል! ወደ ሀበሻ ቤት እንኳን ደህና መጡ 🎉",
    },
    "signup_bonus_received": {
        "en": "🎁 You received <b>{amount} ETB</b> signup bonus!\n",
        "am": "🎁 <b>{amount} ብር</b> ጀማሪ ቦነስ አግኝተዋል!\n",
    },

    # ──────────────────────────────────────────
    # MAIN MENU
    # ──────────────────────────────────────────
    "main_menu_text": {
        "en": (
            "🏠 <b>Main Menu</b>\n\n"
            "👤 {username}\n"
            "💰 Balance: <b>{balance} ETB</b>\n\n"
            "Choose an option below:"
        ),
        "am": (
            "🏠 <b>ዋና ምናሌ</b>\n\n"
            "👤 {username}\n"
            "💰 ቀሪ ሂሳብ: <b>{balance} ብር</b>\n\n"
            "ከታች ይምረጡ:"
        ),
    },
    "btn_open_app":      {"en": "🎮 Open Habesha Bet",  "am": "🎮 ሀበሻ ቤት ክፈት"},
    "btn_play_games":    {"en": "🎮 Play Games",      "am": "🎮 ጨዋታ ተጫዋቱ"},
    "btn_deposit":       {"en": "💳 Deposit",          "am": "💳 ገንዘብ ያስገቡ"},
    "btn_withdraw":      {"en": "💸 Withdraw",         "am": "💸 ገንዘብ ያውጡ"},
    "btn_transfer":      {"en": "↔️ Transfer",         "am": "↔️ ዝውውር"},
    "btn_balance":       {"en": "💰 Balance",          "am": "💰 ቀሪ ሂሳብ"},
    "btn_profile":       {"en": "👤 My Profile",       "am": "👤 መገለጫዬ"},
    "btn_transactions":  {"en": "📋 Transactions",     "am": "📋 ግብይቶች"},
    "btn_join_group":    {"en": "👥 Join Group",       "am": "👥 ቡድን ይቀላቀሉ"},
    "btn_contact":       {"en": "📞 Contact Us",       "am": "📞 ያግኙን"},
    "btn_refer":         {"en": "🎁 Refer & Earn",     "am": "🎁 ጓደኛ ጋብዝ"},
    "btn_daily_bonus":   {"en": "🎁 Daily Bonus",      "am": "🎁 የቀን ቦነስ"},
    "btn_language":      {"en": "🌐 Switch to Amharic","am": "🌐 English ቀይር"},
    "btn_back":          {"en": "🔙 Back",             "am": "🔙 ተመለስ"},
    "btn_cancel":        {"en": "❌ Cancel",           "am": "❌ ሰርዝ"},
    "btn_main_menu":     {"en": "🏠 Main Menu",        "am": "🏠 ዋና ምናሌ"},

    # ──────────────────────────────────────────
    # LANGUAGE TOGGLE
    # ──────────────────────────────────────────
    "language_switched_am": {
        "en": "🌐 Language switched to Amharic.",
        "am": "🌐 ቋንቋ ወደ አማርኛ ተቀይሯል።",
    },
    "language_switched_en": {
        "en": "🌐 Language switched to English.",
        "am": "🌐 ቋንቋ ወደ እንግሊዝኛ ተቀይሯል።",
    },

    # ──────────────────────────────────────────
    # GAMES MENU
    # ──────────────────────────────────────────
    "games_menu_text": {
        "en": "🎮 <b>Games</b>\n\nChoose a game to play:",
        "am": "🎮 <b>ጨዋታዎች</b>\n\nጨዋታ ይምረጡ:",
    },
    "btn_bingo":            {"en": "🎱 Bingo",             "am": "🎱 ቢንጎ"},
    "btn_ludo":             {"en": "🎲 Ludo (soon)",        "am": "🎲 ሉዶ (近ቶ)"},
    "btn_cards":            {"en": "🃏 Cards (soon)",       "am": "🃏 ካርድ (ቅርቡ)"},
    "btn_conquer":          {"en": "⚔️ Conquer (soon)",    "am": "⚔️ ድል (ቅርቡ)"},
    "coming_soon":          {"en": "🚧 Coming Soon!",       "am": "🚧 ቅርቡ ይመጣል!"},
    "players_active":       {"en": "👥 {count} playing",   "am": "👥 {count} ተጫዋቾች"},

    # ──────────────────────────────────────────
    # BINGO ROOM SELECTION
    # ──────────────────────────────────────────
    "bingo_rooms_text": {
        "en": (
            "🎱 <b>Bingo — Choose a Room</b>\n\n"
            "Each room has 200 cards. Buy up to 5 cards.\n"
            "House takes 20% — 80% goes to the winner(s)!\n\n"
            "Select your entry fee:"
        ),
        "am": (
            "🎱 <b>ቢንጎ — ክፍል ይምረጡ</b>\n\n"
            "እያንዳንዱ ክፍል 200 ካርታዎች አሉት። እስከ 5 ካርታ ይምረጡ።\n"
            "ቤቱ 20% ይወስዳል — 80% ለአሸናፊ(ዎች)!\n\n"
            "የመቀላቀያ ክፍያ ይምረጡ:"
        ),
    },
    "room_btn": {
        "en": "🟢 {fee} ETB  |  Pool: {pool} ETB  |  👥 {players}",
        "am": "🟢 {fee} ብር  |  ሽልማት: {pool} ብር  |  👥 {players}",
    },

    # ──────────────────────────────────────────
    # CARD SELECTION SCREEN
    # ──────────────────────────────────────────
    "card_select_header": {
        "en": (
            "🎱 <b>Bingo {fee} ETB — Select Your Cards</b>\n\n"
            "💰 Balance: <b>{balance} ETB</b>\n"
            "🏆 Prize Pool: <b>{pool} ETB</b>\n"
            "👥 Cards sold: <b>{sold}/200</b>\n"
            "👤 Last buyer: {last_buyer}\n"
            "⏳ Game starts in: <b>{countdown}s</b>\n\n"
            "Choose cards below (max {max_cards} per player):"
        ),
        "am": (
            "🎱 <b>ቢንጎ {fee} ብር — ካርታዎን ይምረጡ</b>\n\n"
            "💰 ቀሪ ሂሳብ: <b>{balance} ብር</b>\n"
            "🏆 የሽልማት ገንዘብ: <b>{pool} ብር</b>\n"
            "👥 የተሸጡ ካርታዎች: <b>{sold}/200</b>\n"
            "👤 የመጨረሻ ገዢ: {last_buyer}\n"
            "⏳ ጨዋታ በ: <b>{countdown} ሰከንድ</b> ይጀምራል\n\n"
            "ካርታ ይምረጡ (ከፍተኛ {max_cards} ካርታ):"
        ),
    },
    "card_preview_label": {
        "en": "👁 Preview — Card #{num}",
        "am": "👁 ቅድሚያ ዕይታ — ካርታ #{num}",
    },
    "btn_random_x1":    {"en": "🎲 Random x1",     "am": "🎲 ዘፈቀደ x1"},
    "btn_random_x2":    {"en": "🎲 Random x2",     "am": "🎲 ዘፈቀደ x2"},
    "btn_start_game":   {"en": "▶️ START!",         "am": "▶️ ጀምር!"},
    "btn_start_cost":   {"en": "▶️ START! ({cost} ETB)", "am": "▶️ ጀምር! ({cost} ብር)"},
    "card_taken":       {"en": "⛔ Card #{num} is already taken.", "am": "⛔ ካርታ #{num} ተወስዷል።"},
    "card_selected":    {"en": "✅ Card #{num} selected.", "am": "✅ ካርታ #{num} ተመርጧል።"},
    "no_cards_selected":{"en": "⚠️ Please select at least 1 card first.", "am": "⚠️ ቢያንስ 1 ካርታ ይምረጡ።"},
    "max_cards_exceeded":{"en": "⚠️ Max {max} cards per player per game.", "am": "⚠️ በአንድ ጨዋታ ከ{max} ካርታ አይበልጥም።"},
    "purchase_success": {
        "en": "✅ Cards purchased! Game starts in {countdown}s.\n💰 Remaining balance: <b>{balance} ETB</b>",
        "am": "✅ ካርታዎች ተገዝተዋል! ጨዋታ በ{countdown}ሰ. ይጀምራል።\n💰 ቀሪ ሂሳብ: <b>{balance} ብር</b>",
    },
    "insufficient_balance_buy": {
        "en": "❌ Insufficient balance.\nNeeded: <b>{needed} ETB</b> | Yours: <b>{have} ETB</b>\n\nDeposit first?",
        "am": "❌ በቂ ቀሪ ሂሳብ የለም።\nያስፈልጋል: <b>{needed} ብር</b> | አለዎት: <b>{have} ብር</b>\n\nገንዘብ ያስገቡ?",
    },

    # ──────────────────────────────────────────
    # LOBBY / WAITING
    # ──────────────────────────────────────────
    "lobby_waiting": {
        "en": (
            "⏳ <b>Waiting for players...</b>\n\n"
            "🏆 Prize Pool: <b>{pool} ETB</b>\n"
            "👥 Cards sold: <b>{sold}/200</b>\n"
            "⏱ Starts in: <b>{countdown}s</b>\n\n"
            "Minimum {min_cards} cards needed to start."
        ),
        "am": (
            "⏳ <b>ተጫዋቾችን እየጠበቅን...</b>\n\n"
            "🏆 ሽልማት: <b>{pool} ብር</b>\n"
            "👥 የተሸጡ ካርታዎች: <b>{sold}/200</b>\n"
            "⏱ ይጀምራል: <b>{countdown} ሰከንድ</b>\n\n"
            "ለመጀመር ቢያንስ {min_cards} ካርታ ያስፈልጋል።"
        ),
    },
    "lobby_refund": {
        "en": "⚠️ Not enough players. Game cancelled — <b>{amount} ETB</b> refunded to your account.",
        "am": "⚠️ በቂ ተጫዋቾች አልነበሩም። ጨዋታ ተሰርዟል — <b>{amount} ብር</b> ወደ አካውንትዎ ተመልሷል።",
    },

    # ──────────────────────────────────────────
    # ACTIVE GAME SCREEN
    # ──────────────────────────────────────────
    "game_header": {
        "en": (
            "🎱 <b>Bingo {fee} ETB  |  Call {called}/{total}</b>\n"
            "🏆 Prize Pool: <b>{pool} ETB</b>\n"
            "👥 Players: <b>{players}</b>\n\n"
        ),
        "am": (
            "🎱 <b>ቢንጎ {fee} ብር  |  ጥሪ {called}/{total}</b>\n"
            "🏆 ሽልማት: <b>{pool} ብር</b>\n"
            "👥 ተጫዋቾች: <b>{players}</b>\n\n"
        ),
    },
    "number_called": {
        "en": "🔵 <b>{letter}-{number}</b>  ({amharic})",
        "am": "🔵 <b>{letter}-{number}</b>  ({amharic})",
    },
    "game_starting": {
        "en": "🎲 Game starting! Good luck! 🍀",
        "am": "🎲 ጨዋታው ይጀምራል! መልካም እድል! 🍀",
    },
    "auto_win_on":  {"en": "🤖 Auto Win: ON",  "am": "🤖 ራስ-አሸናፊ: ሲሰራ"},
    "auto_win_off": {"en": "🤖 Auto Win: OFF", "am": "🤖 ራስ-አሸናፊ: ጠፍቷል"},
    "btn_check_all":{"en": "✅ Check All ({n}/{total})", "am": "✅ ሁሉ ፈትሽ ({n}/{total})"},
    "btn_bingo_claim":{"en": "🎉 BINGO!",              "am": "🎉 ቢንጎ!"},
    "btn_auto_toggle":{"en": "🤖 Auto: {state}",       "am": "🤖 ራስ: {state}"},

    # ──────────────────────────────────────────
    # BINGO CLAIM RESULTS
    # ──────────────────────────────────────────
    "bingo_claim_invalid": {
        "en": "❌ No valid win found on your cards yet. Keep watching!",
        "am": "❌ እስካሁን ድል አላገኙም። ቀጥሉ!",
    },
    "bingo_claim_accepted": {
        "en": "✅ Claim received! Confirming your win...",
        "am": "✅ ጥያቄዎ ተቀብሏል! ድልዎን በማረጋገጥ ላይ...",
    },
    "game_not_running": {
        "en": "⏳ This game hasn't started yet.",
        "am": "⏳ ይህ ጨዋታ እስካሁን አልጀመረም።",
    },
    "room_busy_alert": {
        "en": "🎲 A round is already in progress in this room. Please wait for it to finish.",
        "am": "🎲 በዚህ ክፍል ውስጥ ጨዋታ በመካሄድ ላይ ነው። እስኪጨርስ ይጠብቁ።",
    },
    "win_line": {
        "en": (
            "🎉🎉🎉 <b>BINGO! LINE WIN!</b> 🎉🎉🎉\n\n"
            "🏆 Winner: {username}\n"
            "💰 Prize: <b>{amount} ETB</b>\n"
            "🎴 Card #{card_num}\n\n"
            "💰 Your new balance: <b>{balance} ETB</b>"
        ),
        "am": (
            "🎉🎉🎉 <b>ቢንጎ! የረድፍ ድል!</b> 🎉🎉🎉\n\n"
            "🏆 አሸናፊ: {username}\n"
            "💰 ሽልማት: <b>{amount} ብር</b>\n"
            "🎴 ካርታ #{card_num}\n\n"
            "💰 አዲስ ቀሪ ሂሳብ: <b>{balance} ብር</b>"
        ),
    },
    "win_corners": {
        "en": (
            "🎊🎊🎊 <b>BINGO! CORNERS WIN!</b> 🎊🎊🎊\n\n"
            "🏆 Winner: {username}\n"
            "💰 Prize: <b>{amount} ETB</b>\n"
            "🎴 Card #{card_num}\n\n"
            "💰 Your new balance: <b>{balance} ETB</b>"
        ),
        "am": (
            "🎊🎊🎊 <b>ቢንጎ! የጠርዝ ድል!</b> 🎊🎊🎊\n\n"
            "🏆 አሸናፊ: {username}\n"
            "💰 ሽልማት: <b>{amount} ብር</b>\n"
            "🎴 ካርታ #{card_num}\n\n"
            "💰 አዲስ ቀሪ ሂሳብ: <b>{balance} ብር</b>"
        ),
    },
    "win_split": {
        "en": (
            "🎉🎉🎉 <b>BINGO! {winner_count} WINNERS!</b> 🎉🎉🎉\n\n"
            "The prize pool is split equally:\n"
            "🏆 Your share: <b>{amount} ETB</b>\n"
            "🎴 Card #{card_num}\n\n"
            "💰 Your new balance: <b>{balance} ETB</b>"
        ),
        "am": (
            "🎉🎉🎉 <b>ቢንጎ! {winner_count} አሸናፊዎች!</b> 🎉🎉🎉\n\n"
            "ሽልማቱ በእኩል ይከፋፈላል:\n"
            "🏆 የእርስዎ ድርሻ: <b>{amount} ብር</b>\n"
            "🎴 ካርታ #{card_num}\n\n"
            "💰 አዲስ ቀሪ ሂሳብ: <b>{balance} ብር</b>"
        ),
    },
    "win_split_announce_others": {
        "en": (
            "🏆 <b>{winner_count} players won together!</b>\n"
            "💰 Pool split: <b>{amount} ETB</b> each\n"
            "Winners: {winner_list}\n\n"
            "Better luck next time! 🍀"
        ),
        "am": (
            "🏆 <b>{winner_count} ተጫዋቾች በአንድነት አሸንፈዋል!</b>\n"
            "💰 የተከፋፈለ ሽልማት: እያንዳንዱ <b>{amount} ብር</b>\n"
            "አሸናፊዎች: {winner_list}\n\n"
            "ቀጣዩ ዙር ይሞክሩ! 🍀"
        ),
    },
    "win_announce_others": {
        "en": (
            "🏆 <b>{username}</b> won!\n"
            "💰 Prize: <b>{amount} ETB</b>\n"
            "🎴 Card #{card_num} ({win_type})\n\n"
            "Better luck next time! 🍀"
        ),
        "am": (
            "🏆 <b>{username}</b> አሸንፏል!\n"
            "💰 ሽልማት: <b>{amount} ብር</b>\n"
            "🎴 ካርታ #{card_num} ({win_type})\n\n"
            "ቀጣዩ ዙር ይሞክሩ! 🍀"
        ),
    },
    "no_winner_refund": {
        "en": "😮 No winner after 75 calls! <b>{amount} ETB</b> refunded to all players.",
        "am": "😮 75 ጥሪ ቢሆንም አሸናፊ አልተገኘም! <b>{amount} ብር</b> ለሁሉም ተጫዋቾች ተመልሷል።",
    },
    "btn_play_again": {"en": "🔁 Play Again", "am": "🔁 ዳግም ተጫወት"},
    "win_type_line":    {"en": "Line",    "am": "ረድፍ"},
    "win_type_corners": {"en": "Corners", "am": "ጠርዝ"},

    # ──────────────────────────────────────────
    # DEPOSIT FLOW
    # ──────────────────────────────────────────
    "deposit_choose_amount": {
        "en": (
            "💳 <b>Deposit</b>\n\n"
            "Minimum deposit: <b>{min} ETB</b>\n\n"
            "How much would you like to deposit?"
        ),
        "am": (
            "💳 <b>ገንዘብ ያስገቡ</b>\n\n"
            "አነስተኛ ገቢ: <b>{min} ብር</b>\n\n"
            "ምን ያህል ማስገባት ይፈልጋሉ?"
        ),
    },
    "btn_custom_amount": {"en": "✏️ Custom Amount", "am": "✏️ ሌላ መጠን"},
    "deposit_enter_custom": {
        "en": "✏️ Enter deposit amount (min {min} ETB):",
        "am": "✏️ የገቢ መጠን ያስገቡ (አነስተኛ {min} ብር):",
    },
    "deposit_invalid_amount": {
        "en": "❌ Invalid amount. Please enter a number ≥ {min}.",
        "am": "❌ ትክክለኛ ያልሆነ መጠን። {min} ወይም ከዚያ በላይ ያስገቡ።",
    },
    "deposit_instructions": {
        "en": (
            "💳 <b>Deposit {amount} ETB via Telebirr</b>\n\n"
            "1️⃣ Send <b>{amount} ETB</b> to Telebirr:\n"
            "   📱 <b>{telebirr_number}</b>\n"
            "   👤 Account name: <b>{recipient_name}</b>\n\n"
            "2️⃣ Copy the full confirmation SMS Telebirr sends you\n\n"
            "3️⃣ Paste it here in this chat\n\n"
            "⚠️ Send the exact amount. Paste the full SMS."
        ),
        "am": (
            "💳 <b>{amount} ብር በቴሌብር ያስገቡ</b>\n\n"
            "1️⃣ <b>{amount} ብር</b> ወደ ቴሌብር ይላኩ:\n"
            "   📱 <b>{telebirr_number}</b>\n"
            "   👤 አካውንት ስም: <b>{recipient_name}</b>\n\n"
            "2️⃣ ቴሌብር የሚልክልዎትን የማረጋገጫ SMS ሙሉውን ኮፒ ያድርጉ\n\n"
            "3️⃣ እዚህ ቻት ላይ ይለጥፉት\n\n"
            "⚠️ ትክክለኛውን መጠን ይላኩ። ሙሉ SMS ይለጥፉ።"
        ),
    },
    "deposit_processing":    {"en": "⏳ Verifying SMS...",                "am": "⏳ SMS እያረጋገጥን ነው..."},
    "deposit_success": {
        "en": (
            "✅ <b>Deposit Successful!</b>\n\n"
            "💰 Amount credited: <b>{amount} ETB</b>\n"
            "💰 New balance: <b>{balance} ETB</b>"
        ),
        "am": (
            "✅ <b>ገንዘቡ ገብቷል!</b>\n\n"
            "💰 የተጨመረ: <b>{amount} ብር</b>\n"
            "💰 አዲስ ቀሪ ሂሳብ: <b>{balance} ብር</b>"
        ),
    },
    "deposit_already_used": {
        "en": "❌ This transaction has already been used. Each SMS can only be credited once.",
        "am": "❌ ይህ ግብይት ቀደም ሲል ጥቅም ላይ ውሏል። እያንዳንዱ SMS አንድ ጊዜ ብቻ ይሰራል።",
    },
    "deposit_invalid_sms": {
        "en": "❌ Could not read that as a Telebirr SMS. Please paste the full original message.",
        "am": "❌ ይህ ትክክለኛ የቴሌብር SMS አይደለም። ሙሉ መልዕክቱን ይለጥፉ።",
    },
    "deposit_wrong_account": {
        "en": "❌ This payment was not sent to our account ({recipient_name} / {telebirr_number}).",
        "am": "❌ ይህ ክፍያ ወደ ትክክለኛው አካውንት ({recipient_name} / {telebirr_number}) አልተላከም።",
    },
    "deposit_amount_mismatch": {
        "en": "❌ SMS shows {sms_amount} ETB but you chose {expected_amount} ETB. Please retry.",
        "am": "❌ SMS {sms_amount} ብር ያሳያል ግን {expected_amount} ብር ምርጠዋል። እንደገና ይሞክሩ።",
    },
    "deposit_pick_amount": {
        "en": "💳 <b>Deposit</b>\n\nChoose an amount or enter a custom one:",
        "am": "💳 <b>ገንዘብ ያስገቡ</b>\n\nመጠን ይምረጡ ወይም የራስዎን መጠን ያስገቡ:",
    },
    "deposit_custom_prompt": {
        "en": "✏️ Enter the amount you want to deposit (min {min} ETB):",
        "am": "✏️ ማስገባት የሚፈልጉትን መጠን ያስገቡ (ዝቅተኛ {min} ብር):",
    },
    "deposit_amount_too_low": {
        "en": "❌ Minimum deposit is {min} ETB. Please enter a higher amount.",
        "am": "❌ ዝቅተኛ ተቀማጭ {min} ብር ነው። ከፍ ያለ መጠን ያስገቡ።",
    },
    "deposit_invalid": {
        "en": "❌ Could not read this SMS. Please paste the full, unedited Telebirr confirmation message.",
        "am": "❌ ይህን SMS ማንበብ አልተቻለም። ሙሉውን ያልተቀየረ የቴሌብር መልዕክት ይለጥፉ።",
    },
    "deposit_no_account": {
        "en": "⚠️ Deposits are temporarily unavailable. Please contact support.",
        "am": "⚠️ ክፍያ አሁን አይቻልም። ለድጋፍ ያግኙን።",
    },

    # ──────────────────────────────────────────
    # WITHDRAWAL FLOW
    # ──────────────────────────────────────────
    "withdraw_start": {
        "en": (
            "💸 <b>Withdraw</b>\n\n"
            "💰 Balance: <b>{balance} ETB</b>\n"
            "📱 Withdrawal to: <b>{phone}</b>\n\n"
            "Minimum: {min} ETB\n\n"
            "How much would you like to withdraw?"
        ),
        "am": (
            "💸 <b>ገንዘብ ያውጡ</b>\n\n"
            "💰 ቀሪ ሂሳብ: <b>{balance} ብር</b>\n"
            "📱 ወደ: <b>{phone}</b>\n\n"
            "አነስተኛ: {min} ብር\n\n"
            "ምን ያህል ማውጣት ይፈልጋሉ?"
        ),
    },
    "withdraw_no_phone": {
        "en": "⚠️ No phone number registered. Please restart with /start to register your number.",
        "am": "⚠️ ስልክ ቁጥር አልተመዘገበም። /start ይጫኑ።",
    },
    "cancel": {
        "en": "❌ Cancelled.",
        "am": "❌ ተሰርዟል።",
    },
    "withdraw_insufficient": {
        "en": "❌ Insufficient balance. Max you can withdraw: <b>{balance} ETB</b>",
        "am": "❌ በቂ ቀሪ ሂሳብ የለም። ከፍተኛ: <b>{balance} ብር</b>",
    },
    "withdraw_below_min": {
        "en": "❌ Minimum withdrawal is {min} ETB.",
        "am": "❌ አነስተኛ የማውጣት መጠን {min} ብር ነው።",
    },
    "withdraw_invalid_amount": {
        "en": "❌ Invalid amount. Enter a number.",
        "am": "❌ ትክክለኛ ያልሆነ መጠን። ቁጥር ያስገቡ።",
    },
    "withdraw_submitted": {
        "en": (
            "✅ <b>Withdrawal Request Submitted!</b>\n\n"
            "💰 Amount: <b>{amount} ETB</b>\n"
            "📱 To: <b>{phone}</b>\n\n"
            "⏳ Will be processed within 24 hours."
        ),
        "am": (
            "✅ <b>የማውጣት ጥያቄ ተልኳል!</b>\n\n"
            "💰 መጠን: <b>{amount} ብር</b>\n"
            "📱 ወደ: <b>{phone}</b>\n\n"
            "⏳ በ24 ሰዓት ውስጥ ይከናወናል።"
        ),
    },
    "withdraw_approved": {
        "en": "✅ Your withdrawal of <b>{amount} ETB</b> has been sent to <b>{phone}</b>!",
        "am": "✅ የ<b>{amount} ብር</b> ጥያቄዎ ወደ <b>{phone}</b> ተልኳል!",
    },
    "withdraw_rejected": {
        "en": "❌ Your withdrawal of {amount} ETB was rejected. Amount refunded to your balance.",
        "am": "❌ የ{amount} ብር ጥያቄዎ ተቀባይነት አላገኘም። ወደ ቀሪ ሂሳብዎ ተመልሷል።",
    },
    "withdraw_admin_notify": {
        "en": (
            "🔔 <b>Withdrawal Request #{id}</b>\n\n"
            "👤 User: {user_id} (@{username})\n"
            "📱 Phone: {phone}\n"
            "💰 Amount: <b>{amount} ETB</b>\n"
            "🕐 Time: {time}"
        ),
        "am": (
            "🔔 <b>የማውጣት ጥያቄ #{id}</b>\n\n"
            "👤 ተጠቃሚ: {user_id} (@{username})\n"
            "📱 ስልክ: {phone}\n"
            "💰 መጠን: <b>{amount} ብር</b>\n"
            "🕐 ጊዜ: {time}"
        ),
    },
    "btn_approve": {"en": "✅ Approve", "am": "✅ ፍቀድ"},
    "btn_reject":  {"en": "❌ Reject",  "am": "❌ ሰርዝ"},

    # ──────────────────────────────────────────
    # TRANSFER FLOW
    # ──────────────────────────────────────────
    "transfer_start": {
        "en": (
            "↔️ <b>Transfer to another player</b>\n\n"
            "💰 Your balance: <b>{balance} ETB</b>\n"
            "Minimum: {min} ETB\n\n"
            "Enter the recipient's Telegram username (without @):"
        ),
        "am": (
            "↔️ <b>ለሌላ ተጫዋቺ ዝውውር</b>\n\n"
            "💰 ቀሪ ሂሳብ: <b>{balance} ብር</b>\n"
            "አነስተኛ: {min} ብር\n\n"
            "የተቀባዩን Telegram ስም ያስገቡ (@ ሳይጨምሩ):"
        ),
    },
    "transfer_enter_amount": {
        "en": "💰 How much to transfer to @{to_username}? (Your balance: {balance} ETB)",
        "am": "💰 ለ@{to_username} ምን ያህል ይዛወር? (ቀሪ ሂሳብ: {balance} ብር)",
    },
    "transfer_user_not_found": {
        "en": "❌ User @{username} not found. They must have used this bot before.",
        "am": "❌ @{username} አልተገኘም። ቀደም ሲል ቦቱን ተጠቅሞ መሆን አለበት።",
    },
    "transfer_cannot_self": {
        "en": "❌ You cannot transfer to yourself.",
        "am": "❌ ለራስዎ ማዛወር አይቻልም።",
    },
    "transfer_cooldown": {
        "en": "⏳ You can only transfer once per hour. Try again in {minutes} min.",
        "am": "⏳ በሰዓቱ አንዴ ብቻ ማዛወር ይቻላል። {minutes} ደቂቃ ቆይተው ይሞክሩ።",
    },
    "transfer_insufficient": {
        "en": "❌ Insufficient balance.",
        "am": "❌ በቂ ቀሪ ሂሳብ የለም።",
    },
    "transfer_success": {
        "en": (
            "✅ <b>Transfer Successful!</b>\n\n"
            "💸 Sent: <b>{amount} ETB</b> to @{to_username}\n"
            "💰 New balance: <b>{balance} ETB</b>"
        ),
        "am": (
            "✅ <b>ዝውውር ተሳክቷል!</b>\n\n"
            "💸 ተልኳል: <b>{amount} ብር</b> ለ@{to_username}\n"
            "💰 አዲስ ቀሪ ሂሳብ: <b>{balance} ብር</b>"
        ),
    },
    "transfer_received": {
        "en": "💰 You received <b>{amount} ETB</b> from @{from_username}!",
        "am": "💰 ከ@{from_username} <b>{amount} ብር</b> ደረሰዎ!",
    },
    "transfer_below_min": {
        "en": "❌ Minimum transfer is {min} ETB.",
        "am": "❌ አነስተኛ ዝውውር {min} ብር ነው።",
    },
    "transfer_invalid_amount": {
        "en": "❌ Invalid amount. Enter a number.",
        "am": "❌ ትክክለኛ ያልሆነ መጠን። ቁጥር ያስገቡ።",
    },

    # ──────────────────────────────────────────
    # PROFILE
    # ──────────────────────────────────────────
    "profile_text": {
        "en": (
            "👤 <b>My Profile</b>\n\n"
            "🆔 ID: <code>{user_id}</code>\n"
            "👤 Username: @{username}\n"
            "📱 Phone: {phone}\n"
            "💰 Balance: <b>{balance} ETB</b>\n"
            "👥 Referrals: <b>{referrals}</b>\n"
            "📅 Member since: {joined}"
        ),
        "am": (
            "👤 <b>መገለጫዬ</b>\n\n"
            "🆔 መለያ: <code>{user_id}</code>\n"
            "👤 ስም: @{username}\n"
            "📱 ስልክ: {phone}\n"
            "💰 ቀሪ ሂሳብ: <b>{balance} ብር</b>\n"
            "👥 ጋብዞ ያስገቡ: <b>{referrals}</b>\n"
            "📅 አባልነት: {joined}"
        ),
    },

    # ──────────────────────────────────────────
    # TRANSACTIONS HISTORY
    # ──────────────────────────────────────────
    "transactions_header": {
        "en": "📋 <b>Last 10 Transactions</b>",
        "am": "📋 <b>የመጨረሻ 10 ግብይቶች</b>",
    },
    "no_transactions": {
        "en": "No transactions yet.",
        "am": "እስካሁን ምንም ግብይት የለም።",
    },
    "tx_row": {
        "en": "{icon} {type_label}  {sign}{amount} ETB  ({date})",
        "am": "{icon} {type_label}  {sign}{amount} ብር  ({date})",
    },
    "tx_type_deposit":         {"en": "Deposit",          "am": "ገቢ"},
    "tx_type_withdraw":        {"en": "Withdrawal",       "am": "ወጪ"},
    "tx_type_withdraw_refund": {"en": "Withdrawal Refund", "am": "የወጪ ተመላሽ"},
    "tx_type_transfer_in":     {"en": "Transfer In",      "am": "ዝውውር ወደ ሂሳብ"},
    "tx_type_transfer_out":    {"en": "Transfer Out",     "am": "ዝውውር ከሂሳብ"},
    "tx_type_bingo_bet":       {"en": "Bingo Bet",        "am": "ቢንጎ ውርርድ"},
    "tx_type_bingo_win":       {"en": "Bingo Win",        "am": "ቢንጎ ሽልማት"},
    "tx_type_bingo_refund":    {"en": "Bingo Refund",     "am": "ቢንጎ ተመላሽ"},
    "tx_type_referral_bonus":  {"en": "Referral Bonus",   "am": "የግብዣ ቦነስ"},
    "tx_type_signup_bonus":    {"en": "Signup Bonus",     "am": "ጀማሪ ቦነስ"},
    "tx_type_daily_bonus":     {"en": "Daily Bonus",      "am": "የቀን ቦነስ"},
    "tx_type_house_commission":{"en": "House Commission", "am": "የቤት ክፍያ"},

    # ──────────────────────────────────────────
    # DAILY BONUS
    # ──────────────────────────────────────────
    "daily_bonus_claimed": {
        "en": (
            "🎁 Daily bonus claimed!\n\n"
            "🔥 Streak: <b>{streak} day{streak_plural}</b>\n"
            "💰 <b>+{amount} ETB</b> added\n"
            "💰 New balance: <b>{balance} ETB</b>\n\n"
            "Come back tomorrow for more! ⏰"
        ),
        "am": (
            "🎁 የቀን ቦነስ ተወሰደ!\n\n"
            "🔥 ስትሪክ: <b>{streak} ቀን{streak_plural}</b>\n"
            "💰 <b>+{amount} ብር</b> ተጨምሯል\n"
            "💰 አዲስ ቀሪ ሂሳብ: <b>{balance} ብር</b>\n\n"
            "ነገ ይምጡ! ⏰"
        ),
    },
    "daily_bonus_wait": {
        "en": "⏳ Daily bonus already claimed.\nCome back in <b>{hours}h</b>.",
        "am": "⏳ ዛሬ ቀን ቦነስ ወስደዋል።\nበ<b>{hours} ሰዓት</b> ውስጥ ይምጡ።",
    },

    # ──────────────────────────────────────────
    # REFERRAL
    # ──────────────────────────────────────────
    "referral_info": {
        "en": (
            "👥 <b>Refer & Earn</b>\n\n"
            "Share your link and earn <b>{referral_bonus} ETB</b> "
            "when a friend makes their first deposit!\n\n"
            "Your friend also gets <b>{signup_bonus} ETB</b> free.\n\n"
            "🔗 Your link:\n<code>{link}</code>\n\n"
            "📊 Friends referred: <b>{count}</b>"
        ),
        "am": (
            "👥 <b>ጓደኛ ጋብዝ፣ ብር አግኝ</b>\n\n"
            "ሊንክዎን ያጋሩ እና ጓደኛዎ ገንዘብ ሲያስገባ <b>{referral_bonus} ብር</b> ያገኛሉ!\n\n"
            "ጓደኛዎ ደግሞ <b>{signup_bonus} ብር</b> ነፃ ያገኛል።\n\n"
            "🔗 ሊንክዎ:\n<code>{link}</code>\n\n"
            "📊 ጋብዘዋቸዋል: <b>{count}</b> ሰዎች"
        ),
    },
    "referral_bonus_earned": {
        "en": "🎉 Your friend {username} made their first deposit!\n💰 You earned <b>{amount} ETB</b> referral bonus!\n💰 Balance: <b>{balance} ETB</b>",
        "am": "🎉 ጓደኛዎ {username} ለመጀመሪያ ጊዜ ገንዘብ አስገብቷል!\n💰 <b>{amount} ብር</b> ቦነስ አግኝተዋል!\n💰 ቀሪ ሂሳብ: <b>{balance} ብር</b>",
    },

    # ──────────────────────────────────────────
    # ADMIN PANEL
    # ──────────────────────────────────────────
    "admin_menu": {
        "en": "⚙️ <b>Admin Panel</b>",
        "am": "⚙️ <b>አስተዳዳሪ ፓናል</b>",
    },
    "btn_admin_dashboard":  {"en": "📊 Dashboard",           "am": "📊 ዳሽቦርድ"},
    "btn_admin_withdrawals":{"en": "💸 Withdrawals",         "am": "💸 ወጪዎች"},
    "btn_admin_accounts":   {"en": "🏦 Deposit Accounts",    "am": "🏦 ቴሌብር አካውንቶች"},
    "btn_admin_broadcast":  {"en": "📢 Broadcast",           "am": "📢 ለሁሉም ላክ"},
    "btn_admin_house":      {"en": "🏠 House Wallet",        "am": "🏠 የቤት ዋሌት"},
    "btn_admin_settings":   {"en": "⚙️ Settings",            "am": "⚙️ ቅንብሮች"},
    "admin_dashboard": {
        "en": (
            "📊 <b>Dashboard</b>\n\n"
            "👥 Total Users: <b>{users}</b>\n"
            "🎮 Games Played: <b>{games}</b>\n"
            "💰 Total Deposited: <b>{deposited} ETB</b>\n"
            "🏠 House Wallet: <b>{house_balance} ETB</b>\n"
            "💎 Total Earned (all-time): <b>{house_total} ETB</b>\n\n"
            "📈 Peak hours (UTC):\n{peak_hours}"
        ),
        "am": (
            "📊 <b>ዳሽቦርድ</b>\n\n"
            "👥 ተጠቃሚዎች: <b>{users}</b>\n"
            "🎮 ጨዋታዎች: <b>{games}</b>\n"
            "💰 ጠቅላላ ቀጥተኛ ክፍያ: <b>{deposited} ብር</b>\n"
            "🏠 የቤት ዋሌት: <b>{house_balance} ብር</b>\n"
            "💎 ጠቅላላ ትርፍ: <b>{house_total} ብር</b>\n\n"
            "📈 ዋና ሰዓቶች (UTC):\n{peak_hours}"
        ),
    },
    "admin_no_pending_withdrawals": {
        "en": "✅ No pending withdrawals.",
        "am": "✅ ጥያቄ ያለ ወጪ የለም።",
    },
    "admin_withdrawal_list_header": {
        "en": "💸 <b>Pending Withdrawals ({count})</b>",
        "am": "💸 <b>ጠባቂ ወጪዎች ({count})</b>",
    },
    "admin_accounts_list": {
        "en": "🏦 <b>Deposit Accounts</b>\n\n{accounts}\n\nTo add: /addaccount <phone> <name>\nTo remove: /removeaccount <id>",
        "am": "🏦 <b>ቴሌብር አካውንቶች</b>\n\n{accounts}\n\nለመጨመር: /addaccount <phone> <name>\nለማስወገድ: /removeaccount <id>",
    },
    "admin_account_row": {
        "en": "#{id} | {phone} | {name} | {count} deposits | {status}",
        "am": "#{id} | {phone} | {name} | {count} ክፍያ | {status}",
    },
    "admin_account_active":   {"en": "✅ ACTIVE", "am": "✅ ገቢር"},
    "admin_account_inactive": {"en": "⭕ inactive","am": "⭕ ዝም"},
    "admin_account_added":    {"en": "✅ Account added: {phone} ({name})", "am": "✅ አካውንት ተጨምሯል: {phone} ({name})"},
    "admin_account_removed":  {"en": "✅ Account #{id} removed.", "am": "✅ አካውንት #{id} ተወግዷል።"},
    "admin_broadcast_prompt": {
        "en": "📢 Forward or type the message to broadcast to all {count} users:",
        "am": "📢 ለ{count} ተጠቃሚዎች ሁሉ ለመላክ መልዕክቱን ይፃፉ ወይም ያስተላልፉ:",
    },
    "admin_broadcast_done": {
        "en": "✅ Broadcast sent to {success}/{total} users.",
        "am": "✅ ለ{success}/{total} ተጠቃሚዎች ተልኳል።",
    },
    "admin_house_wallet": {
        "en": (
            "🏠 <b>House Wallet</b>\n\n"
            "💰 Current balance: <b>{balance} ETB</b>\n"
            "💎 Total earned (all-time): <b>{total} ETB</b>\n\n"
            "To withdraw: /housewithdraw <amount>"
        ),
        "am": (
            "🏠 <b>የቤት ዋሌት</b>\n\n"
            "💰 ወቅታዊ ቀሪ ሂሳብ: <b>{balance} ብር</b>\n"
            "💎 ጠቅላላ ትርፍ: <b>{total} ብር</b>\n\n"
            "ለማውጣት: /housewithdraw <amount>"
        ),
    },
    "admin_house_withdrawn": {
        "en": "✅ Withdrew <b>{amount} ETB</b> from house wallet. Remaining: <b>{balance} ETB</b>",
        "am": "✅ <b>{amount} ብር</b> ከቤት ዋሌት ወጥቷል። ቀሪ: <b>{balance} ብር</b>",
    },
    "admin_house_insufficient": {
        "en": "❌ House wallet has only {balance} ETB.",
        "am": "❌ የቤት ዋሌት ያለው {balance} ብር ብቻ ነው።",
    },
    "admin_settings": {
        "en": (
            "⚙️ <b>Settings</b>\n\n"
            "🏠 Commission: {commission}%\n"
            "⏱ Call delay: {call_delay}s\n"
            "⏳ Countdown: {countdown}s\n"
            "📋 Min cards to start: {min_cards}\n\n"
            "(Edit config.py to change these settings, then restart the bot.)"
        ),
        "am": (
            "⚙️ <b>ቅንብሮች</b>\n\n"
            "🏠 ኮሚሽን: {commission}%\n"
            "⏱ የጥሪ ፍጥነት: {call_delay} ሰ.\n"
            "⏳ የቆጠራ ጊዜ: {countdown} ሰ.\n"
            "📋 ለመጀመር ቢያንስ ካርታ: {min_cards}\n\n"
            "(ቅንብሮቹን ለመቀየር config.py ያርሙ፣ ቦቱን ደግሞ ያስጀምሩ።)"
        ),
    },
    "not_admin": {
        "en": "⛔ You are not authorized to use this command.",
        "am": "⛔ ይህን ትዕዛዝ የሚጠቀሙ አይደሉም።",
    },

    # ──────────────────────────────────────────
    # GENERIC / ERRORS
    # ──────────────────────────────────────────
    "error_generic": {
        "en": "⚠️ Something went wrong. Please try again.",
        "am": "⚠️ ችግር ተፈጥሯል። እንደገና ይሞክሩ።",
    },
    "main_menu_hint": {
        "en": "Tap /start to return to the main menu.",
        "am": "ወደ ዋና ምናሌ ለመመለስ /start ይጫኑ።",
    },
}


# =====================================================================
# HELPER FUNCTION
# =====================================================================

def get_text(key: str, lang: str = "am", **kwargs) -> str:
    """
    Retrieve a localized string and format it with keyword arguments.

    Usage:
        get_text("deposit_success", lang="am", amount=100, balance=950)

    Falls back to "am" if the requested language is missing,
    then falls back to the raw key if the key is missing entirely.
    """
    entry = STRINGS.get(key)
    if entry is None:
        return key   # return the raw key as last resort

    text = entry.get(lang) or entry.get("am") or entry.get("en") or key

    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError:
            pass  # leave unformatted if a placeholder is missing

    return text


def get_user_text(key: str, user, **kwargs) -> str:
    """Convenience wrapper: gets lang from a db Row (user object)."""
    lang = user["language"] if user and "language" in user.keys() else "am"
    return get_text(key, lang, **kwargs)


# =====================================================================
# SELF-TEST  (python3 locales.py)
# =====================================================================
if __name__ == "__main__":
    print("=== English ===")
    print(get_text("welcome_new", "en"))
    print()
    print(get_text("deposit_success", "en", amount=100.0, balance=950.0))
    print()
    print(get_text("win_corners", "en", username="@Ab8***", amount=850.0, card_num=42, balance=1850.0))

    print("\n=== Amharic ===")
    print(get_text("welcome_new", "am"))
    print()
    print(get_text("deposit_success", "am", amount=100.0, balance=950.0))
    print()
    print(get_text("win_corners", "am", username="@Ab8***", amount=850.0, card_num=42, balance=1850.0))

    print("\n=== Fallback test (missing key) ===")
    print(get_text("nonexistent_key", "am"))

    print("\n=== All keys present in both languages ===")
    missing = []
    for k, v in STRINGS.items():
        for lang in ("en", "am"):
            if lang not in v:
                missing.append(f"{k}[{lang}]")
    if missing:
        print("MISSING:", missing)
    else:
        print(f"All {len(STRINGS)} keys have both en and am translations ✅")
