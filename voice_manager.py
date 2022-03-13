import logging
import uuid
from pathlib import Path

from telegram import Voice

from pymediainfo import MediaInfo

from exception import VoiceNotFound

logger = logging.getLogger(__name__)


class VoiceManager:
    @staticmethod
    def initial_voice_cache(delete: bool = True) -> None:
        base_path = Path("voice")
        if not base_path.exists():
            base_path.mkdir()

        if delete:
            for child_path in base_path.iterdir():
                child_path.unlink()

    @staticmethod
    def delete_voice(path: str) -> None:
        Path(path).unlink(missing_ok=True)

    @staticmethod
    def download_voice(voice: Voice) -> str:
        filename = str(uuid.uuid4().hex) + ".ogg"
        base_relative = Path("voice")
        base_path = base_relative.resolve(strict=True)

        full_path = str(base_path / filename)
        voice.get_file().download(custom_path=full_path)

        return full_path

    @staticmethod
    def load_voice(path: str) -> bytes:
        file = Path(path)
        if not file.exists():
            raise VoiceNotFound(f"Path: {path}")
        with file.open("rb") as buf:
            return buf.read()

    @staticmethod
    def get_info(path: str) -> dict[str, int]:
        if not Path(path).exists():
            raise VoiceNotFound(f"Path: {path}")
        media_info = MediaInfo.parse(path)

        try:
            sample_rate = media_info.audio_tracks[0].sampling_rate
        except KeyError:
            logging.error("Parse sample_rate error, fallback to 48000Hz.")
            sample_rate = 48000

        try:
            duration = media_info.audio_tracks[0].duration
        except KeyError:
            logging.error("Parse duration error.")
            duration = 0

        return {"sample_rate": sample_rate, "duration": duration}
