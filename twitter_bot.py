import tweepy
import os
from dotenv import load_dotenv

def send_tweet(text):
  load_dotenv()

  consumer_key = os.environ.get("TWITTER_CONSUMER_KEY")
  consumer_secret = os.environ.get("TWITTER_CONSUMER_SECRET")
  access_token = os.environ.get("TWITTER_ACCESS_TOKEN")
  access_token_secret = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET")

  client = tweepy.Client(
      consumer_key=consumer_key,
      consumer_secret=consumer_secret,
      access_token=access_token,
      access_token_secret=access_token_secret
  )

  client.create_tweet(text=text)