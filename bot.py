import logging

from telegram import Update
from telegram.ext import (
    CallbackContext,
    CommandHandler,
    Filters,
    MessageHandler,
    Updater,
)

from speech import GcloudSpeech
from storage import GcloudStorage
from voice_manager import VoiceManager

logger = logging.getLogger(__name__)


class ASRBot:
    def __init__(
        self,
        api_key: str,
        options: dict,
        messages: dict,
        recognizer: GcloudSpeech,
        uploader: GcloudStorage,
    ):
        self._api_key = api_key

        self._allow_private = options["private"]
        self._allow_group = options["group"]
        self._whitelist = options["whitelist"]
        self._whitelist_id = options["whitelist_ids"]
        self._accept_bot = options["accept_bot"]
        self._accept_fwd = options["accept_fwd"]
        self._delete = options["delete"]

        self._start_msg = messages["start"]
        self._not_allowed_msg = messages["not_allowed"]
        self._not_white_msg = messages["not_white"]
        self._deny_bot_msg = messages["deny_bot"]
        self._deny_fwd_msg = messages["deny_fwd"]
        self._placeholder_msg = messages["placeholder"]
        self._clear_msg = messages["clear"]
        self._empty_result_msg = messages["empty_result"]
        self._deny_long_msg = messages["deny_long"]

        self.updater = Updater(token=self._api_key, use_context=True)
        self.dispatcher = self.updater.dispatcher
        self.recognizer = recognizer
        self.uploader = uploader

    @staticmethod
    def send_if_set(update: Update, context: CallbackContext):
        def send_msg(var: str):
            if var and len(var):
                return context.bot.send_message(
                    chat_id=update.effective_chat.id, text=var
                )
            return None

        return send_msg

    def delete_voice(self, path: str) -> None:
        if self._delete:
            VoiceManager.delete_voice(path)

    def register(self):
        def start(update: Update, context: CallbackContext):
            self.send_if_set(update, context)(self._start_msg)

        def clear(update: Update, context: CallbackContext):
            VoiceManager.initial_voice_cache()
            self.send_if_set(update, context)(self._clear_msg)

        def listen(update: Update, context: CallbackContext):

            send_msg = self.send_if_set(update, context)

            if not self._allow_group and update.effective_chat.type.endswith("group"):
                send_msg(self._not_allowed_msg)
                return None

            if not self._allow_private and update.effective_chat.type == "private":
                send_msg(self._not_allowed_msg)
                return None

            if self._whitelist and update.effective_chat.id not in self._whitelist_id:
                send_msg(self._not_white_msg)
                return None

            if not self._accept_bot and update.effective_user.is_bot:
                send_msg(self._deny_bot_msg)
                return None

            if not self._accept_fwd and update.message.forward_from:
                send_msg(self._deny_fwd_msg)
                return None

            filepath = VoiceManager.download_voice(update.message.voice)
            info = VoiceManager.get_info(filepath)
            sample_rate = info["sample_rate"]
            duration = info["duration"]

            # c.f. https://cloud.google.com/speech-to-text/docs/async-recognize
            long_bucket = duration >= 60000

            # Need a bucket
            if long_bucket and not self.uploader:
                send_msg(self._deny_long_msg)
                self.delete_voice(filepath)
                return None

            msg = send_msg(self._placeholder_msg)
            self.recognizer.set_sample_rate(sample_rate)

            if long_bucket:
                blob_name = self.uploader.upload(filepath)
                bucket_path = self.uploader.get_uri(blob_name)
                result = self.recognizer.recognize(bucket_path=bucket_path)
            else:
                blob_name = None
                result = self.recognizer.recognize(local_path=filepath)

            # Result body is empty
            if not len(result):
                result = self._empty_result_msg

            # Replace the placeholder msg to result
            if msg:
                context.bot.editMessageText(
                    chat_id=update.effective_chat.id,
                    message_id=msg.message_id,
                    text=result,
                )
            else:
                send_msg(result)

            if long_bucket:
                self.uploader.delete(blob_name)

            self.delete_voice(filepath)

        start_handler = CommandHandler("start", start)
        self.dispatcher.add_handler(start_handler)

        listen_handler = MessageHandler(Filters.voice, listen)
        self.dispatcher.add_handler(listen_handler)

        clear_handler = CommandHandler("clear", clear)
        self.dispatcher.add_handler(clear_handler)

    def start(self):
        VoiceManager.initial_voice_cache(self._delete)
        self.updater.start_polling(drop_pending_updates=True)
        self.updater.idle()
