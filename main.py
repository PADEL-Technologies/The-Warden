import os

from warden.bot import Warden

# ponytail: token read straight from the env. Add a config module at 3+ settings.
if __name__ == "__main__":
    Warden().run(os.environ["DISCORD_TOKEN"], root_logger=True)
