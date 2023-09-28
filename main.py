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
  print('Fetching past tournaments...')
  tournaments = fetch_tournaments(should_fetch_past_events=True)

  formats = supabase_client.table('Formats').select('id,format,rotation,start_date').execute().data
  for tournament in tournaments:
    print('Updating tournament - ' + tournament['name'])
    mainWorker(tournament, True, False, tournaments, formats, False)

  print('Done!')

def load_past_tournament(tournament_id):
  print('Loading tournament with id', tournament_id)

  tournament = supabase_client.table('tournaments_new').select('*').eq('id', tournament_id).execute().data[0]
  formats = supabase_client.table('Formats').select('id,format,rotation,start_date').execute().data

  print('Updating tournament - ' + tournament['name'])
  mainWorker(tournament, True, False, [tournament], formats, False)

  print('Done!')


def update_live_and_upcoming_tournaments():
  print('Fetching upcoming tournaments...')
  tournaments = fetch_tournaments(should_fetch_past_events=False)

  formats = supabase_client.table('Formats').select('id,format,rotation,start_date').execute().data
  for tournament in tournaments:
    print('Updating tournament - ' + tournament['name'])
    mainWorker(tournament, True, False, tournaments, formats, True)

  print('Done!')


load_past_tournament(58)