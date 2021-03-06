import pymongo
import tweepy
import logging.handlers
from decouple import config

# SQL database
DB_ENDPOINT = config('DB_ENDPOINT')
PORT = config('PORT')
USR = config('USR')
REGION = config('REGION')
DB_NAME = config('DB_NAME')
MASTER_USERNAME = config('MASTER_USERNAME')
MASTER_PASSWORD = config('MASTER_PASSWORD')

# Mongodb 
MONGO_CLIENT = pymongo.MongoClient(config('MONGO_CLIENT'))
mongo_db = MONGO_CLIENT['stock_screener_realtime_db']

# polygon
POLYGON_BASE_URL = config('POLYGON_BASE_URL')
POLYGON_API_KEY = config('POLYGON_API_KEY')

# Twitter API Keys set
TWEEPY_CONSUMER_KEY = config('TWEEPY_CONSUMER_KEY')
TWEEPY_CONSUMER_SECRET = config('TWEEPY_CONSUMER_SECRET')
TWEEPY_ACCESS_TOKEN  = config('TWEEPY_ACCESS_TOKEN')
TWEEPY_ACCESS_SECRET = config('TWEEPY_ACCESS_SECRET')

# Tweepy config
TWEEPY_AUTH = tweepy.OAuthHandler(TWEEPY_CONSUMER_KEY, TWEEPY_CONSUMER_SECRET)
TWEEPY_AUTH.set_access_token(TWEEPY_ACCESS_TOKEN, TWEEPY_ACCESS_SECRET)
TWEEPY_API = tweepy.API(TWEEPY_AUTH)

#News API org API Key
NEWS_API_KEY = config('NEWS_API_KEY')

# Global Vars
UTC_MARKET_OPEN = '14:30:00'
UTC_MARKET_CLOSE = '21:00:00'
TWEET_BASE_URL = 'https://twitter.com/user/status/'
PERIOD = 5
ALPHA = 2 / (PERIOD+1)
MULTIPLIER = 1.4

# Email stuff
GMAIL_ROOT_USER = config('GMAIL_ROOT_USER')
GMAIL_USER_1 = config('GMAIL_USER_1')
GMAIL_USER_2 = config('GMAIL_USER_2')
GMAIL_USER_3 = config('GMAIL_USER_3')
GMAIL_ROOT_PASS = config('GMAIL_ROOT_PASS')

# Create logger (main logger)
LOGGER = logging.getLogger('REGULAR')
LOGGER.setLevel(logging.INFO)

# Handler 
LOG_FILE = '/tmp/sample-app.log'
handler = logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes=1048576, backupCount=5)
handler.setLevel(logging.INFO)

# Formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Add Formatter to Handler
handler.setFormatter(formatter)

# add Handler to Logger
LOGGER.addHandler(handler)

# Create logger (sockets)
LOGGER_SOCKET = logging.getLogger('SOCKET')
LOGGER_SOCKET.setLevel(logging.INFO)

# Handler 
LOG_FILE_SOCKET = '/tmp/sample-app-2.log'
handler_socket = logging.handlers.RotatingFileHandler(LOG_FILE_SOCKET, maxBytes=1048576, backupCount=5)
handler_socket.setLevel(logging.INFO)

# Add Formatter to Handler
handler_socket.setFormatter(formatter)

# add Handler to Logger
LOGGER_SOCKET.addHandler(handler_socket)