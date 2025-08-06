# C:\...\my_football_game\HTML\run.py (Corrected)

from textfootball import create_app # <-- THE ONLY CHANGE IS HERE
from config import DevelopmentConfig

app = create_app(config_class=DevelopmentConfig)

if __name__ == '__main__':
    app.run()
