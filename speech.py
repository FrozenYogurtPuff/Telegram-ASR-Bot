import logging

from google.cloud import speech_v1p1beta1 as speech

from voice_manager import VoiceManager

logger = logging.getLogger(__name__)


class GcloudSpeech:
    def __init__(self, api_key, options):
        self._prefer_lang = options["prefer"]
        self._is_multilingual = options["is_multi"]
        self._opt_langs = options["opt"]
        self._is_word_conf = options["word_conf"]
        self._is_punct = options["punct"]
        self.client = speech.SpeechClient.from_service_account_file(api_key)

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

    def recognize(self, local_path: str = None, bucket_path: str = None) -> str:
        if not local_path and not bucket_path:
            raise ValueError("You must specify either local_path or bucket_path")
        if local_path and bucket_path:
            raise ValueError("You must specify either local_path or bucket_path")

        config = speech.RecognitionConfig(**self._config)
        if local_path:
            buf = VoiceManager.load_voice(local_path)
            audio = speech.RecognitionAudio(content=buf)
            response = self.client.recognize(config=config, audio=audio)
        else:
            audio = speech.RecognitionAudio(uri=bucket_path)
            operation = self.client.long_running_recognize(config=config, audio=audio)
            response = operation.result(timeout=60)

        sentence = ""
        for result in response.results:
            alternative = result.alternatives[0]
            logger.warning(f"{alternative.transcript}")
            logger.warning(f"Confidence - {alternative.confidence}")
            sentence += alternative.transcript
        return sentence
