import boto3
import os
from dotenv import load_dotenv

from standings import mainWorker
from fetch_and_refresh_tournaments import fetch_and_refresh_tournaments

# mainWorker("0000090", "BA189xznzDvlCdfoQlBC", False, False)

load_dotenv()

access_key = os.environ.get("AWS_ACCESS_KEY")
secret_key = os.environ.get("AWS_SECRET_KEY")
session = boto3.Session(
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
)

s3 = session.client('s3')
data = fetch_and_refresh_tournaments(s3Client=s3)

for tournament in data:
  print(tournament)