# generate_audio.py
# ============================================
# HABESHA BET - AMHARIC NUMBER VOICE GENERATOR
#
# Generates one audio clip per bingo ball (1..75). Each clip speaks the
# column letter followed by the Amharic name of the number, e.g.:
#       1  -> "B አንድ"
#      75  -> "O ሰባ አምስት"
#
# Output: <AUDIO_DIR>/<number>.mp3   (e.g. audio/12.mp3)
#
# Uses gTTS (Google Translate TTS, lang='am'). Requires network access
# at generation time. Re-run any time; existing files are skipped so it
# safely resumes after an interruption.
#
# The Mini App fetches /audio/<number>.mp3 when a ball is called; the bot
# can also send these as voice notes (see ENABLE_VOICE_ANNOUNCEMENTS).
# ============================================
import os

import config
import bingo
from gtts import gTTS


def main():
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), config.AUDIO_DIR)
    os.makedirs(out_dir, exist_ok=True)

    # "Game starting! Good luck!" — same wording already used elsewhere in
    # the bot (locales.py: game_starting), reused here rather than a new
    # translation, so the voice matches the app's existing established tone.
    start_text = "ጨዋታው ይጀምራል! መልካም እድል!"
    start_path = os.path.join(out_dir, "game_started.mp3")
    if not os.path.exists(start_path):
        gTTS(start_text, lang="am").save(start_path)

    # Write a human-readable manifest (safe UTF-8) of what each clip says.
    manifest_path = os.path.join(out_dir, "manifest.txt")
    with open(manifest_path, "w", encoding="utf-8") as manifest:
        manifest.write(f"game_started: {start_text}\n")
        for n in range(1, 76):
            text = f"{bingo.number_to_letter(n)} {bingo.number_to_amharic(n)}"
            path = os.path.join(out_dir, f"{n}.mp3")
            if not os.path.exists(path):
                gTTS(text, lang="am").save(path)
            manifest.write(f"{n}: {text}\n")

    print(f"Done. {len(os.listdir(out_dir)) - 1} clip(s) in {out_dir}")


if __name__ == "__main__":
    main()
