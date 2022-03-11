import logging

from environs import Env, EnvError

from telegram import Update, Voice
from telegram.ext import CallbackContext
from telegram.ext import CommandHandler
from telegram.ext import Updater
from telegram.ext import MessageHandler, Filters

from google.cloud import speech_v1p1beta1 as speech


class ConfigNotFound(Exception):
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
    handle_bot_voice = env.bool("HANDLE_BOT_VOICE", False)

    bot_options = {
        "private": is_allow_private,
        "group": is_allow_group,
        "whitelist": is_whitelist,
        "whitelist_ids": whitelist_ids,
        "handle_bot": handle_bot_voice,
    }

    start_msg = env.str("START_MSG", None)
    not_allowed_msg = env.str("NOT_ALLOWED_MSG", None)
    not_white_msg = env.str("NOT_IN_WHITELIST_MSG", None)
    deny_bot_msg = env.str("NOT_HANDLE_BOT_MSG", None)
    placeholder_msg = env.str("PLACEHOLDER_MSG", None)

    msg = {
        "start": start_msg,
        "not_allowed": not_allowed_msg,
        "not_white": not_white_msg,
        "deny_bot": deny_bot_msg,
        "placeholder": placeholder_msg,
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

        _config = {
            "encoding": speech.RecognitionConfig.AudioEncoding.OGG_OPUS,
            "sample_rate_hertz": 48000,
            "language_code": self._prefer_lang,
        }
        if self._is_multilingual:
            _config.update({"alternative_language_codes": self._opt_langs})
        if self._is_word_conf:
            _config.update({"enable_word_confidence": self._is_word_conf})
        if self._is_punct:
            _config.update({"enable_automatic_punctuation": self._is_punct})

        self.config = speech.RecognitionConfig(**_config)

    def recognize(self, buf) -> str:
        audio = speech.RecognitionAudio(content=buf)
        response = self.client.recognize(config=self.config, audio=audio)
        sentence = ""
        for result in response.results:
            alternative = result.alternatives[0]
            logging.warning(f"{alternative.transcript}")
            logging.warning(f"Confidence - {alternative.confidence}")
            sentence += alternative.transcript
        return sentence


class ASRBot:
    def __init__(
        self, tg_api_key: str, options: dict, messages: dict, recognizer: GcloudASR
    ):
        self._tg_api_key = tg_api_key

        self._allow_private = options["private"]
        self._allow_group = options["group"]
        self._whitelist = options["private"]
        self._whitelist_id = options["whitelist_ids"]
        self._handle_bot = options["handle_bot"]

        self._start_msg = messages["start"]
        self._not_allowed_msg = messages["not_allowed"]
        self._not_white_msg = messages["not_white"]
        self._deny_bot_msg = messages["deny_bot"]
        self._placeholder_msg = messages["placeholder"]

        self.updater = Updater(token=self._tg_api_key, use_context=True)
        self.dispatcher = self.updater.dispatcher
        self.recognizer = recognizer

    @staticmethod
    def get_voice_buffer(voice: Voice) -> bytes:
        return bytes(voice.get_file().download_as_bytearray())

    def register(self):
        def start(update: Update, context: CallbackContext):
            if self._start_msg:
                context.bot.send_message(
                    chat_id=update.effective_chat.id, text=self._start_msg
                )

        def listen(update: Update, context: CallbackContext):
            exclude = False

            if not self._allow_group and update.effective_chat.type.endswith("group"):
                if self._not_allowed_msg:
                    context.bot.send_message(
                        chat_id=update.effective_chat.id, text=self._not_allowed_msg
                    )
                exclude = True

            if not self._allow_private and update.effective_chat.type == "private":
                if self._not_allowed_msg:
                    context.bot.send_message(
                        chat_id=update.effective_chat.id, text=self._not_allowed_msg
                    )
                exclude = True

            if self._whitelist and update.effective_chat.id not in self._whitelist_id:
                if self._not_white_msg:
                    context.bot.send_message(
                        chat_id=update.effective_chat.id, text=self._not_white_msg
                    )
                exclude = True

            if not self._handle_bot and update.effective_user.is_bot:
                print(update.effective_user)
                if self._deny_bot_msg:
                    context.bot.send_message(
                        chat_id=update.effective_chat.id, text=self._deny_bot_msg
                    )
                exclude = True

            if not exclude:
                if self._placeholder_msg:
                    msg = context.bot.send_message(
                        chat_id=update.effective_chat.id, text=self._placeholder_msg
                    )

                    buf = self.get_voice_buffer(update.message.voice)
                    result = self.recognizer.recognize(buf)

                    context.bot.editMessageText(
                        chat_id=update.effective_chat.id,
                        message_id=msg.message_id,
                        text=result,
                    )
                else:
                    buf = self.get_voice_buffer(update.message.voice)
                    result = self.recognizer.recognize(buf)

                    context.bot.send_message(
                        chat_id=update.effective_chat.id, text=result
                    )

        start_handler = CommandHandler("start", start)
        self.dispatcher.add_handler(start_handler)

        listen_handler = MessageHandler(Filters.voice, listen)
        self.dispatcher.add_handler(listen_handler)

    def start(self):
        self.updater.start_polling()


if __name__ == "__main__":
    TG_API_KEY, BOT_OPT, ASR_OPT, MSG = parse_env()
    asr = GcloudASR(ASR_OPT)
    bot = ASRBot(TG_API_KEY, BOT_OPT, MSG, asr)
    bot.register()
    bot.start()
