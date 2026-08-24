from warden.bot import Warden
from warden.config import load_config
from warden.log import setup_logging

if __name__ == "__main__":
    config = load_config()
    setup_logging(config.log_level)
    # log_handler=None: discord.py tidak boleh memasang handler/formatter sendiri,
    # semuanya sudah lewat setup_logging di atas.
    Warden(config).run(config.discord_token, log_handler=None)
