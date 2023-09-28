import os
from tournaments import fetch_tournaments
from standings import mainWorker
from supabase_client import supabase_client

# mainWorker("0000090", "BA189xznzDvlCdfoQlBC", False, False)

# for tournament in data:
#   #if (tournament['tournamentStatus'] != 'finished'):
#   print('Updating tournament - ' + tournament['name'])
#   mainWorker(tournament, False, False, data)

def load_all_past_tournaments():
  print('Fetching all tournaments...')
  tournaments = fetch_tournaments(should_fetch_past_events=True)

  formats = supabase_client.table('Formats').select('id,format,rotation,start_date').execute().data
  for tournament in tournaments:
    print('Updating tournament - ' + tournament['name'])
    mainWorker(tournament, False, False, tournaments, formats)

  print('Done!')

load_all_past_tournaments()