# Telegram-ASR-Bot
A telegram ASR (Speech Recognition, or Speech-to-Text) bot based on python-telegram-bot and Google Cloud Speech.

## Usage
- `/start` to get a smoke test.
- `/clear` to clear local voice cache.
- Feel free to send voices, the bot will watch these messages and process them automatically.

## Prerequisite
### External
- `mediainfo`[^1]

### Python Packages
```toml
[tool.poetry.dependencies]
python = "^3.9"
python-telegram-bot = "^13.11"
google-cloud-speech = "^2.13.1"
environs = "^9.5.0"
pymediainfo = "^5.1.0"
google-cloud-storage = "^2.1.0"
```

### Google Cloud Configurations
#### Speech-to-Text
- A Service Account with `Cloud Speech Client` and `Storage Object Viewer` roles granted.
#### Cloud Storage
This is optional if you do _not_ need long speech recognition (voice duration > 60s).[^2]
- A Service Account with `Storage Object Admin` role granted.
  - Can be narrowed to `Storage Object Creator` if set `DELETE_BUCKET_VOICE=False`.
- A valid storage bucket under control.

### Telegram BotFather
- `/setprivacy` Turn disabled.
- `/setcommands`
```
start - Check bot
clear - Clear local cache
```

### Whitelist Group ID Lookup
Please refer to https://github.com/GabrielRF/telegram-id .

## .env Example
```env
# API Key
TG_API_KEY=""
GCLOUD_SPEECH_CREDENTIALS="/Users/asr-speech.json"
GCLOUD_BUCKET_CREDENTIALS="/Users/asr-storage.json"

# Bot Options
ALLOW_PRIVATE=False
ALLOW_GROUP=True
ENABLE_GROUP_WHITELIST=True
GROUP_WHITELIST="-1001145141919,-1001234567890"
ACCEPT_BOT_VOICE=False
ACCEPT_FORWARD_VOICE=False
DELETE_LOCAL_VOICE=True

# Voice Options
PREFER_LANGUAGE="en-US"
MULTIPLE_LANGUAGE_DETECT=True
OPTIONAL_LANGUAGE="zh,ja-JP,yue-Hant-HK"
ENABLE_WORD_CONFIDENCE=False
ENABLE_PUNCTUATION=True

# Storage Bucket Options
ENABLE_BUCKET=True
BUCKET_NAME="my-asr-bucket"
DELETE_BUCKET_VOICE=True

# Message
START_MSG="Start the bot."
NOT_ALLOWED_MSG="This chat type is not allowed."
NOT_IN_WHITELIST_MSG="This group is not in the whitelist."
DENY_BOT_MSG="Voice from another bot is rejected to process."
DENY_FORWARD_MSG="Voice from forward message is rejected to process."
PLACEHOLDER_MSG="Processing..."
CLEAR_MSG="The local voice cache has been successfully deleted."
EMPTY_RESULT_MSG="I can't hear you clearly."
DENY_LONG_VOICE_MSG="Voices that greater than 60 secs needs a Google Cloud Storage service."
```

[^1]: `pymediainfo` requires `libmediainfo-dev` to detect the sample rate of voice messages.
[^2]: https://cloud.google.com/speech-to-text/docs/async-recognize
