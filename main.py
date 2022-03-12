import logging
import uuid

from environs import Env, EnvError

from google.cloud import speech_v1p1beta1 as speech

from telegram import Update, Voice
from telegram.ext import (
    CallbackContext,
    CommandHandler,
    Filters,
    MessageHandler,
    Updater,
)
from pathlib import Path

from pymediainfo import MediaInfo


class ConfigNotFound(Exception):
    pass


class VoiceNotFound(Exception):
    pass


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)


def parse_env():
    env = Env()
    env.read_env()

    try:
        tg_api_key = env.str("TG_API_KEY")
    except EnvError:
        raise ConfigNotFound("API Key not detected.")

    is_allow_private = env.bool("ALLOW_PRIVATE", False)
    is_allow_group = env.bool("ALLOW_GROUP", True)
    is_whitelist = env.bool("ENABLE_GROUP_WHITELIST", False)
    whitelist_ids = env.list("GROUP_WHITELIST", subcast=int) if is_whitelist else None
    accept_bot = env.bool("ACCEPT_BOT_VOICE", False)
    accept_fwd = env.bool("ACCEPT_FORWARD_VOICE", False)

    bot_options = {
        "private": is_allow_private,
        "group": is_allow_group,
        "whitelist": is_whitelist,
        "whitelist_ids": whitelist_ids,
        "accept_bot": accept_bot,
        "accept_fwd": accept_fwd,
    }

    start_msg = env.str("START_MSG", None)
    not_allowed_msg = env.str("NOT_ALLOWED_MSG", None)
    not_white_msg = env.str("NOT_IN_WHITELIST_MSG", None)
    deny_bot_msg = env.str("DENY_BOT_MSG", None)
    deny_fwd_msg = env.str("DENY_FORWARD_MSG", None)
    placeholder_msg = env.str("PLACEHOLDER_MSG", None)
    clear_msg = env.str("CLEAR_MSG", None)

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
    }

    try:
        prefer_lang = env.str("PREFER_LANGUAGE")
    except EnvError:
        raise ConfigNotFound("Prefer language is unset.")

    enable_multilingual = env.bool("MULTIPLE_LANGUAGE_DETECT", False)
    optional_langs = env.list("OPTIONAL_LANGUAGE") if enable_multilingual else None
    enable_word_conf = env.bool("ENABLE_WORD_CONFIDENCE", False)
    enable_punct = env.bool("ENABLE_PUNCTUATION", False)

    asr_options = {
        "prefer": prefer_lang,
        "is_multi": enable_multilingual,
        "opt": optional_langs,
        "word_conf": enable_word_conf,
        "punct": enable_punct,
    }

    return tg_api_key, bot_options, asr_options, msg


class GcloudASR:
    def __init__(self, options):
        self._prefer_lang = options["prefer"]
        self._is_multilingual = options["is_multi"]
        self._opt_langs = options["opt"]
        self._is_word_conf = options["word_conf"]
        self._is_punct = options["punct"]

        self.client = speech.SpeechClient()

        self._config = {
            "encoding": speech.RecognitionConfig.AudioEncoding.OGG_OPUS,
            "sample_rate_hertz": 48000,
            "language_code": self._prefer_lang,
        }
        if self._is_multilingual:
            self._config.update({"alternative_language_codes": self._opt_langs})
        if self._is_word_conf:
            self._config.update({"enable_word_confidence": self._is_word_conf})
        if self._is_punct:
            self._config.update({"enable_automatic_punctuation": self._is_punct})

    def set_sample_rate(self, sample_rate: int) -> None:
        self._config.update({"sample_rate_hertz": sample_rate})

    @staticmethod
    def load_voice(path: str) -> bytes:
        file = Path(path)
        if not file.exists():
            raise VoiceNotFound(f"Path: {path}")
        with file.open("rb") as buf:
            return buf.read()

    def recognize(self, path: str) -> str:
        buf = self.load_voice(path)
        audio = speech.RecognitionAudio(content=buf)
        config = speech.RecognitionConfig(**self._config)
        response = self.client.recognize(config=config, audio=audio)
        sentence = ""
        for result in response.results:
            alternative = result.alternatives[0]
            logging.warning(f"{alternative.transcript}")
            logging.warning(f"Confidence - {alternative.confidence}")
            sentence += alternative.transcript
        return sentence


class ASRBot:
    def __init__(
        self,
        tg_api_key: str,
        options: dict,
        messages: dict,
        recognizer: GcloudASR,
    ):
        self._tg_api_key = tg_api_key

        self._allow_private = options["private"]
        self._allow_group = options["group"]
        self._whitelist = options["whitelist"]
        self._whitelist_id = options["whitelist_ids"]
        self._accept_bot = options["accept_bot"]
        self._accept_fwd = options["accept_fwd"]

        self._start_msg = messages["start"]
        self._not_allowed_msg = messages["not_allowed"]
        self._not_white_msg = messages["not_white"]
        self._deny_bot_msg = messages["deny_bot"]
        self._deny_fwd_msg = messages["deny_fwd"]
        self._placeholder_msg = messages["placeholder"]
        self._clear_msg = messages["clear"]
        self._empty_result_msg = messages["empty_result"]

        self.updater = Updater(token=self._tg_api_key, use_context=True)
        self.dispatcher = self.updater.dispatcher
        self.recognizer = recognizer

    @staticmethod
    def get_voice_path(voice: Voice) -> str:
        filename = str(uuid.uuid4().hex) + ".ogg"
        base_relative = Path("voice")
        base_path = base_relative.resolve(strict=True)

        full_path = str(base_path / filename)
        voice.get_file().download(custom_path=full_path)

        return full_path

    @staticmethod
    def get_sample_rate(path: str) -> int:
        if not Path(path).exists():
            raise VoiceNotFound(f"Path: {path}")
        media_info = MediaInfo.parse(path)

        try:
            sample_rate = media_info.audio_tracks[0].sampling_rate
        except KeyError:
            logging.error("Parse sample_rate error, fallback to 48000Hz.")
            sample_rate = 48000

        return sample_rate

    @staticmethod
    def send_if_set(update: Update, context: CallbackContext):
        def send_msg(var: str):
            if var and len(var):
                return context.bot.send_message(
                    chat_id=update.effective_chat.id, text=var
                )
            return None

        return send_msg

    @staticmethod
    def delete_voice(path: str) -> None:
        Path(path).unlink(missing_ok=True)

    @staticmethod
    def initial_voice_cache() -> None:
        base_path = Path("voice")
        if not base_path.exists():
            base_path.mkdir()

        for child_path in base_path.iterdir():
            child_path.unlink()

    def register(self):
        def start(update: Update, context: CallbackContext):
            self.send_if_set(update, context)(self._start_msg)

        def clear(update: Update, context: CallbackContext):
            self.initial_voice_cache()
            self.send_if_set(update, context)(self._clear_msg)

        def listen(update: Update, context: CallbackContext):

            send_msg = self.send_if_set(update, context)

            if not self._allow_group and update.effective_chat.type.endswith("group"):
                send_msg(self._not_allowed_msg)

            elif not self._allow_private and update.effective_chat.type == "private":
                send_msg(self._not_allowed_msg)

            elif self._whitelist and update.effective_chat.id not in self._whitelist_id:
                send_msg(self._not_white_msg)

            elif not self._accept_bot and update.effective_user.is_bot:
                send_msg(self._deny_bot_msg)

            elif not self._accept_fwd and update.message.forward_from:
                send_msg(self._deny_fwd_msg)

            else:
                msg = send_msg(self._placeholder_msg)

                filepath = self.get_voice_path(update.message.voice)
                sample_rate = self.get_sample_rate(filepath)
                self.recognizer.set_sample_rate(sample_rate)
                result = self.recognizer.recognize(filepath)

                if not len(result):
                    result = self._empty_result_msg

                if msg:
                    context.bot.editMessageText(
                        chat_id=update.effective_chat.id,
                        message_id=msg.message_id,
                        text=result,
                    )
                else:
                    send_msg(result)

                self.delete_voice(filepath)

        start_handler = CommandHandler("start", start)
        self.dispatcher.add_handler(start_handler)

        listen_handler = MessageHandler(Filters.voice, listen)
        self.dispatcher.add_handler(listen_handler)

        clear_handler = CommandHandler("clear", clear)
        self.dispatcher.add_handler(clear_handler)

    def start(self):
        self.initial_voice_cache()
        self.updater.start_polling()


if __name__ == "__main__":
    TG_API_KEY, BOT_OPT, ASR_OPT, MSG = parse_env()
    asr = GcloudASR(ASR_OPT)
    bot = ASRBot(TG_API_KEY, BOT_OPT, MSG, asr)
    bot.register()
    bot.start()
