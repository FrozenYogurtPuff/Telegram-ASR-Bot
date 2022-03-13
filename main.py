import logging

from environs import Env, EnvError

from bot import ASRBot
from exception import ConfigNotFound
from speech import GcloudSpeech
from storage import GcloudStorage

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

logger = logging.getLogger(__name__)


def parse_env():
    env = Env()
    env.read_env()

    try:
        tg_api_key = env.str("TG_API_KEY")
    except EnvError:
        raise ConfigNotFound("Telegram API Key not detected.")

    try:
        gcloud_speech_cred = env.str("GCLOUD_SPEECH_CREDENTIALS")
    except EnvError:
        raise ConfigNotFound("Google Cloud Speech Credentials not detected.")

    try:
        gcloud_storage_cred = env.str("GCLOUD_STORAGE_CREDENTIALS")
    except EnvError:
        raise ConfigNotFound("Google Cloud Storage Object Credentials not detected.")

    api_keys = {
        "tg": tg_api_key,
        "speech": gcloud_speech_cred,
        "storage": gcloud_storage_cred,
    }

    is_allow_private = env.bool("ALLOW_PRIVATE", False)
    is_allow_group = env.bool("ALLOW_GROUP", True)
    is_whitelist = env.bool("ENABLE_GROUP_WHITELIST", False)

    try:
        whitelist_ids = (
            env.list("GROUP_WHITELIST", subcast=int) if is_whitelist else None
        )
    except EnvError:
        raise ConfigNotFound(
            "Illegal group whitelists when `ENABLE_GROUP_WHITELIST=True`."
        )

    accept_bot = env.bool("ACCEPT_BOT_VOICE", False)
    accept_fwd = env.bool("ACCEPT_FORWARD_VOICE", False)
    delete_local = env.bool("DELETE_LOCAL_VOICE", True)

    bot_options = {
        "private": is_allow_private,
        "group": is_allow_group,
        "whitelist": is_whitelist,
        "whitelist_ids": whitelist_ids,
        "accept_bot": accept_bot,
        "accept_fwd": accept_fwd,
        "delete": delete_local,
    }

    start_msg = env.str("START_MSG", None)
    not_allowed_msg = env.str("NOT_ALLOWED_MSG", None)
    not_white_msg = env.str("NOT_IN_WHITELIST_MSG", None)
    deny_bot_msg = env.str("DENY_BOT_MSG", None)
    deny_fwd_msg = env.str("DENY_FORWARD_MSG", None)
    placeholder_msg = env.str("PLACEHOLDER_MSG", None)
    clear_msg = env.str("CLEAR_MSG", None)
    deny_long_voice_msg = env.str("DENY_LONG_VOICE_MSG", None)

    try:
        empty_result_msg = env.str("EMPTY_RESULT_MSG")
    except EnvError:
        raise ConfigNotFound("Empty result message is unset.")

    msg = {
        "start": start_msg,
        "not_allowed": not_allowed_msg,
        "not_white": not_white_msg,
        "deny_bot": deny_bot_msg,
        "deny_fwd": deny_fwd_msg,
        "placeholder": placeholder_msg,
        "clear": clear_msg,
        "empty_result": empty_result_msg,
        "deny_long": deny_long_voice_msg,
    }

    try:
        prefer_lang = env.str("PREFER_LANGUAGE")
    except EnvError:
        raise ConfigNotFound("Prefer language is unset.")

    enable_multilingual = env.bool("MULTIPLE_LANGUAGE_DETECT", False)

    try:
        optional_langs = env.list("OPTIONAL_LANGUAGE") if enable_multilingual else None
    except EnvError:
        raise ConfigNotFound(
            "Illegal optional languages when `MULTIPLE_LANGUAGE_DETECT=True`."
        )

    enable_word_conf = env.bool("ENABLE_WORD_CONFIDENCE", False)
    enable_punct = env.bool("ENABLE_PUNCTUATION", False)

    asr_options = {
        "prefer": prefer_lang,
        "is_multi": enable_multilingual,
        "opt": optional_langs,
        "word_conf": enable_word_conf,
        "punct": enable_punct,
    }

    enable_bucket = env.bool("ENABLE_BUCKET", False)

    try:
        bucket_name = env.str("BUCKET_NAME") if enable_bucket else None
    except EnvError:
        raise ConfigNotFound("Illegal bucket name when `ENABLE_BUCKET=True`.")

    delete_bucket = env.bool("DELETE_BUCKET_VOICE", True)

    bucket_options = {
        "enable": enable_bucket,
        "name": bucket_name,
        "delete": delete_bucket,
    }

    return api_keys, bot_options, asr_options, bucket_options, msg


if __name__ == "__main__":
    API_KEY, BOT_OPT, ASR_OPT, STORAGE_OPT, MSG = parse_env()
    TG_API_KEY = API_KEY["tg"]
    SPEECH_API_KEY = API_KEY["speech"]
    STORAGE_API_KEY = API_KEY["storage"]

    asr = GcloudSpeech(SPEECH_API_KEY, ASR_OPT)
    bucket = GcloudStorage(STORAGE_API_KEY, STORAGE_OPT)
    bot = ASRBot(TG_API_KEY, BOT_OPT, MSG, asr, bucket)
    bot.register()
    bot.start()
