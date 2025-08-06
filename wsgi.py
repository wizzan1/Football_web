# wsgi.py

from textfootball import create_app
from config import DevelopmentConfig

# This line creates a fully configured 'app' instance
# that Flask command-line tools can find and use.
app = create_app(DevelopmentConfig)
