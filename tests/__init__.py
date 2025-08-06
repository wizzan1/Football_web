# C:\...\my_football_game\HTML\tests\test_config.py

import unittest
from app import create_app
from config import DevelopmentConfig, TestingConfig

class ConfigTestCase(unittest.TestCase):
    def test_development_config(self):
        """Test that the development config loads correctly."""
        app = create_app(DevelopmentConfig)
        self.assertFalse(app.config['TESTING'])
        self.assertTrue(app.config['DEBUG'])
        self.assertIn('instance', app.config['SQLALCHEMY_DATABASE_URI'])

    def test_testing_config(self):
        """Test that the testing config loads correctly."""
        app = create_app(TestingConfig)
        self.assertTrue(app.config['TESTING'])
        self.assertIn('memory', app.config['SQLALCHEMY_DATABASE_URI'])

if __name__ == '__main__':
    unittest.main()
