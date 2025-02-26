from os import environ

class BotConfiguration:
    
    @property
    def token(self) -> str:
        token = environ.get('TRAIN_DISCORD_TOKEN')
        if token is None:
            raise ValueError('Discord token not found in environment variables.')
        return token

    @property
    def command_hash(self) -> int:
        try:
            with open('config/command_hash', 'r') as f:
                return int(f.read())
        except Exception:
            return 0
        
    @command_hash.setter
    def command_hash(self, value: int) -> None:
        try:
            with open('config/command_hash', 'w') as f:
                f.write(str(value))
        except Exception:
            pass
