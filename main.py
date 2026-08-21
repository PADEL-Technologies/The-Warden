from warden.bot import Warden
from warden.config import load_config

if __name__ == "__main__":
    config = load_config()
    Warden(config).run(config.discord_token, root_logger=True)
