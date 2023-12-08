from bs4 import BeautifulSoup
import requests
import time
from datetime import datetime, timedelta
import os
from os.path import exists
import json
import traceback
from supabase_client import supabase_client
import googlemaps

gmaps_key = os.environ.get("GOOGLE_MAPS_API_KEY")
gmaps = googlemaps.Client(key=gmaps_key)

def get_event_type(name):
	if ' regional' in name.lower():
		return 'regional-championships'
	if ' international' in name.lower():
		return 'international-championships'
	if 'world' in name.lower():
		return 'world-championships'
	if ' special' in name.lower():
		return 'special-event'
	if ' special' in name.lower():
		return 'special-event'
	if ' open' in name.lower():
		return 'world-championships-open'

def get_location(rk9_location_str):
	geocode_result = gmaps.geocode(rk9_location_str)
	return json.dumps(geocode_result)

def get_date(date_str):
	[year, day, month] = date_str.split('-')
	return datetime(int(year), int(day), int(month))

def get_tournament_format(formats, tournament):
	most_recent_format = None

	for format in formats:
		if most_recent_format == None:
			most_recent_format = format
		else:
			start_date = get_date(tournament['date']['start'])
			format_start_date = get_date(format['start_date'])
			most_recent_format_start_date = get_date(most_recent_format['start_date'])

			tournament_could_be_in_format = format_start_date.date() <= start_date.date()
			tournament_is_closer_to_date = abs(format_start_date - start_date) < abs(most_recent_format_start_date - start_date)

			if tournament_could_be_in_format and tournament_is_closer_to_date:
				most_recent_format = format


	return most_recent_format['id']

def tournament_should_be_finished(tournament):
	end_date = get_date(tournament['date']['end'])
	end_date += timedelta(days=1)
	return datetime.now() > end_date

def add_dates_to_tournament(date, tournament):
	months = {'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04', 'may': '05', 'jun': '06', 'jul': '07', 'aug': '08', 'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'}
	dateFields = date.replace('–', ' ').replace('-', ' ').replace(', ', ' ').split(" ")
	if len(dateFields) > 4:
		startDate = dateFields[4] + '-' + months[dateFields[0].strip()[:3].lower()] + '-' + f'{int(dateFields[1]):02d}'
		endDate = dateFields[4] + '-' + months[dateFields[2].strip()[:3].lower()] + '-' + f'{int(dateFields[3]):02d}'
	else:
		startDate = dateFields[3] + '-' + months[dateFields[0].strip()[:3].lower()] + '-' + f'{int(dateFields[1]):02d}'
		endDate = dateFields[3] + '-' + months[dateFields[0].strip()[:3].lower()] + '-' + f'{int(dateFields[2]):02d}'

	tournament['date'] = {
		"start": startDate,
		"end": endDate
	}
	

def fetch_tournaments(should_fetch_past_events, is_vgc):
	try:
		tournaments_table = 'tournaments_vgc' if is_vgc else 'tournaments_new'

		should_update_tournaments = False
		openTournaments = supabase_client.table(tournaments_table).select('*').order('id').execute().data

		page = requests.get('https://rk9.gg/events/pokemon')
		soup = BeautifulSoup(page.content, "html.parser")

		target_id = 'dtPastEvents' if should_fetch_past_events else 'dtUpcomingEvents'
		tournaments = soup.find_all('table', attrs={'id':target_id})
		tbody = tournaments[0].find('tbody')
		if(tbody):
			trs = tbody.find_all('tr')
			trs.reverse()
			for tr in trs:
				tds = tr.find_all('td')
				if(len(tds) == 5):
					tName = tds[2].text.replace('\n', '').lstrip(' ').rstrip(' ')
					linkRef = ''
					links = tds[4].find_all('a', href=True)
					for link in links:
						target_phrase = 'vg' if is_vgc else 'tcg'
						if(target_phrase in link.text.lower()):
							linkRef = link['href'].replace('/tournament/', '')
					if(len(linkRef)>0):
						tournamentAlreadyDiscovered = False
						for tournament in openTournaments:
							if(tournament['rk9link'] == linkRef):
								tournamentAlreadyDiscovered = True
							
						if(not(tournamentAlreadyDiscovered)):
							print('new Tournament! ' + tName + ' with url ' + linkRef)

							new_id = 1
							if len(openTournaments) > 0:
								new_id = int(openTournaments[-1]['id']) + 1

							if is_vgc:
								newData = {"id": new_id, "name": tName, "date": None, "players": {"juniors": 0, "seniors": 0, "masters": 0}, "winners": {"juniors": None, "seniors": None, "masters": None}, "tournamentStatus": "not-started", "roundNumbers": {"juniors": None, "seniors": None, "masters": None}, "lastUpdated": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"), "rk9link": linkRef, "event_type": get_event_type(tName), "finalized_in_standings": False }
							else:
								newData = {"id": new_id, "name": tName, "date": None, "decklists": 0, "players": {"juniors": 0, "seniors": 0, "masters": 0}, "winners": {"juniors": None, "seniors": None, "masters": None}, "tournamentStatus": "not-started", "roundNumbers": {"juniors": None, "seniors": None, "masters": None}, "lastUpdated": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"), "rk9link": linkRef, "should_reveal_decks": {"juniors": False, "seniors": False, "masters": False }, "event_type": get_event_type(tName), "finalized_in_standings": False }

							openTournaments.append(newData)
							should_update_tournaments = True

		# if should_update_tournaments:
		# 	supabase_client.table('tournaments_new').upsert(openTournaments).execute()

		return openTournaments
	
	except Exception as e:
		print(e)
		print(traceback.format_exc())