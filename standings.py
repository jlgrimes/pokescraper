import time
import requests
from datetime import datetime
from bs4 import BeautifulSoup
import unicodedata
import sys
import json
import re
import argparse
import traceback
from supabase_client import supabase_client
import logging

#my imports
from standing import Standing
from player import Player, RemoveCountry
from decklists import Decklists, PlayersData
from tournaments import add_dates_to_tournament, get_tournament_format, get_event_type, tournament_should_be_finished

import math
from collections import Counter
from twitter_bot import send_tweet

#removing accents (for js calls)
def strip_accents(input_str):
	nfkd_form = unicodedata.normalize('NFKD', input_str)
	only_ascii = nfkd_form.encode('ASCII', 'ignore')
	return only_ascii

#points access for sorting function
def Points(elem):
	return elem.points

def elIsNotEmpty(el):
	return len(el) > 0

def mainWorker(tournament, getDecklists, getRoster, tournaments, formats, is_live, is_vgc):
	lastPageLoaded = ""
	page = None
	soup = None

	#sys.stdout.flush()
	starttime = time.time()

	try:
		if tournament['tournamentStatus'] == 'finished' and 'finalized_in_standings' in tournament and tournament['finalized_in_standings'] == True:
			print('Tournament finished. Skipping...')
			return

		directory = tournament['id']
		link = tournament['rk9link']

		url = 'https://rk9.gg/tournament/' + link
		page = requests.get(url)
		soup = BeautifulSoup(page.content, "html.parser")

		pageTitle = soup.find('h3', {'class': 'mb-0'}).text
		title = pageTitle.split('\n')[0]
		date =  pageTitle.split('\n')[1]

		tournament_details = {}
		tournament_details_list = soup.find("dl", {"class": "row card-text"})

		temp_key = ''
		for child in tournament_details_list:
			if child.name == 'dt':
				temp_key = child.text.strip()
			elif child.name == 'dd':
				tournament_details[temp_key] = list(filter(elIsNotEmpty, list(map(str.strip, child.text.strip().split('\n')))))
				temp_key = ''

		now = datetime.now() #current date and time
		strTime = now.strftime("%Y/%m/%d %H:%M:%S")

		tournament_details['updated-at'] = strTime
		tournament['metadata'] = tournament_details

		winners = []
		rounds = []
		nbplayers = []

		print('starting at : ' + strTime)

		standings = []

		standings.append(Standing(title, directory, 'juniors', 'Juniors', [link], []))
		standings.append(Standing(title, directory, 'seniors', 'Seniors', [link], []))
		standings.append(Standing(title, directory, 'masters', 'Masters', [link], []))

		players_export = []
		
		decklists_players = None
		roster = None
		if getDecklists:
			print('Reading decklists')
			decklists_players = Decklists(link)
		else:
			print('Not reading decklists')
		if getRoster:
			print('Reading roster')
			roster = PlayersData(link)
		else:
			print('Not reading roster')

		for standing in standings:
			print("Standing : " + standing.tournamentName + " - in " + standing.tournamentDirectory + "/" + standing.directory + " for " + standing.divisionName + " [" + standing.level + "/" + str(standing.roundsDay1) + "/" + str(standing.roundsDay2) + "]")
			winner = None

			for url in standing.urls:
				#requesting RK9 pairings webpage
				url = 'https://rk9.gg/pairings/' + url
				print("\t" + url)
				if(lastPageLoaded != url):
					lastPageLoaded = url
					page = requests.get(url)
					#page content to BeautifulSoup
					soup = BeautifulSoup(page.content, "html.parser")

				#finding out how many rounds on the page							
				iRoundsFromUrl = 0
				for ultag in soup.find_all('ul', {'class': 'nav nav-pills'}):
					for litag in ultag.find_all('li'):
						for aria in litag.find_all('a'):
							sp = aria.text.split(" ")
							if(sp[0][0:-1].lower() == standing.divisionName[0:len(sp[0][0:-1])].lower()):
								iRoundsFromUrl = int(sp[len(sp)-1])
								standing.level = str(aria['aria-controls'])

				#iRoundsFromUrl = 13
				roundsSet = False
				standing.currentRound = iRoundsFromUrl

				rounds.append(iRoundsFromUrl)

				#scrapping standings if available, to compare results later
				strToFind = standing.level + "-standings"
				standingPublishedData = soup.find('div', attrs={'id':strToFind})
				publishedStandings = []
				if(standingPublishedData):
					standingPublished = [y for y in [x.strip() for x in standingPublishedData.text.split('\n')] if y]
					for line in standingPublished:
						data = line.split(' ')
						pos = data[0].replace('.', '')
						player = ''
						for i in range(1, len(data)):
							if(i > 1):
								player += ' '
							player += data[i]
						publishedStandings.append(player.replace('  ', ' '))

				publishedStandings = []
				stillPlaying = 0

				level_slug = 0
				if standing.level == 'P1':
					level_slug = 1
				if standing.level == 'P2':
					level_slug = 2

				all_round_data = []
				print('Loading ' + str(iRoundsFromUrl) + 'rounds...')
				for round_number in range(iRoundsFromUrl):
					round_url = url + '?pod=' + str(level_slug) + '&rnd=' + str(round_number + 1)
					round_page = requests.get(round_url)
					#page content to BeautifulSoup
					round_soup = BeautifulSoup(round_page.content, "html.parser")
					all_round_data.append(round_soup)

				for iRounds in range(iRoundsFromUrl):
					firstTableData = True
					strToFind = standing.level + "R" + str(iRounds+1)
					stillPlaying = 0
					for match_data in all_round_data[iRounds]:
						player1 = ""
						player2 = ""
						p1status = -1
						p2status = -1
						p1dropped = False
						p2dropped = False
						p1late = 0
						p2late = 0
						scores1 = []
						scores2 = []
						table = "0"
						table1 = match_data.find('div', attrs={'class':'col-2'})
						if table1 != None:
							table2 = table1.find('span', attrs={'class':'tablenumber'})
							if table2 != None:
								table = table2.text								
						for player_data in match_data.find_all('div', attrs={'class':'player1'}):
							name = player_data.find_all('span', attrs={'class':'name'})
							if(len(name) > 0):
								score = re.findall(r'\(.*?\)', player_data.text)[0]
								score = score.replace('(', '')
								score = score.replace(')', '')
								scores1 = re.split('-', score)
								player1 = re.sub('\s+',' ', name[0].text)
								if(str(player_data).find(" dropped") != -1):
									p1dropped = True
								if(str(player_data).find(" winner") != -1):
									p1status = 2
								if(str(player_data).find(" loser") != -1):
									p1status = 0
								if(str(player_data).find(" tie") != -1):
									p1status = 1
								if(p1status == -1 and not p1dropped):
									if(iRounds+1 < iRoundsFromUrl):
										p1status = 0
										if(iRounds == 0):
											p1late = -1
								
								
						for player_data in match_data.find_all('div', attrs={'class':'player2'}):
							name = player_data.find_all('span', attrs={'class':'name'})
							if(len(name) > 0):
								score = re.findall(r'\(.*?\)', player_data.text)[0]
								score = score.replace('(', '')
								score = score.replace(')', '')
								scores2 = re.split('-', score)
								player2 = re.sub('\s+',' ', name[0].text)
								if(str(player_data).find(" dropped") != -1):
									p2dropped = True
								if(str(player_data).find(" winner") != -1):
									p2status = 2
								if(str(player_data).find(" loser") != -1):
									p2status = 0
								if(str(player_data).find(" tie") != -1):
									p2status = 1
								if(p2status == -1 and not p2dropped):
									if(iRounds+1 < iRoundsFromUrl):
										p2status = 0
										if(iRounds == 0):
											p2late = -1
						
						p1 = None
						p2 = None
						addP1 = True
						addP2 = True						

						if(len(player1) > 0):								
							for player in filter(lambda y: y.name == player1, standing.players):
								if(p1status == -1 and (player.wins == int(scores1[0]) and player.losses == int(scores1[1]) and player.ties == int(scores1[2]))):
									p1 = player
									addP1 = False
								if(p1status == 0 and (player.wins == int(scores1[0]) and player.losses + 1 == int(scores1[1]) and player.ties == int(scores1[2]))):
									p1 = player
									addP1 = False
								if(p1status == 1 and (player.wins == int(scores1[0]) and player.losses == int(scores1[1]) and player.ties + 1 == int(scores1[2]))):
									p1 = player
									addP1 = False
								if(p1status == 2 and (player.wins + 1 == int(scores1[0]) and player.losses == int(scores1[1]) and player.ties == int(scores1[2]))):
									p1 = player
									addP1 = False
								if(p1dropped):
									if(p1 == None):
										if(player.wins == int(scores1[0]) and player.losses == int(scores1[1]) and player.ties == int(scores1[2])):
											p1 = player
											player.dropRound = iRounds+1
											addP1 = False

							for player in filter(lambda y: y.name == player2, standing.players):
								if(p2status == -1 and (player.wins == int(scores2[0]) and player.losses == int(scores2[1]) and player.ties == int(scores2[2]))):
									p2 = player
									addP2 = False
								if(p2status == 0 and (player.wins == int(scores2[0]) and player.losses + 1 == int(scores2[1]) and player.ties == int(scores2[2]))):
									p2 = player
									addP2 = False
								if(p2status == 1 and (player.wins == int(scores2[0]) and player.losses == int(scores2[1]) and player.ties + 1 == int(scores2[2]))):
									p2 = player
									addP2 = False
								if(p2status == 2 and (player.wins + 1 == int(scores2[0]) and player.losses == int(scores2[1]) and player.ties == int(scores2[2]))):
									p2 = player
									addP2 = False
								if(p2dropped):
									if(p2 == None):
										if(player.wins == int(scores2[0]) and player.losses == int(scores2[1]) and player.ties == int(scores2[2])):
											p2 = player
											player.dropRound = iRounds+1
											addP2 = False							

						if(p1 == None):
							if(len(player1) > 0):
								standing.playerID = standing.playerID + 1										
								p1 = Player(player1, standing.divisionName, standing.playerID, p1late)
								if(p1.country == "" and roster != None):
									p1.country = roster.GetCountry(p1)
								if(p1.name in standing.dqed or (len(publishedStandings) > 0 and p1.name not in publishedStandings)):
									p1.dqed = True
						if(p2 == None):
							if(len(player2) > 0):
								standing.playerID = standing.playerID + 1
								p2 = Player(player2, standing.divisionName, standing.playerID, p2late)
								if(p2.country == "" and roster != None):
									p2.country = roster.GetCountry(p2)
								if(p2.name in standing.dqed or (len(publishedStandings) > 0 and p2.name not in publishedStandings)):
									p2.dqed = True
						if(p1 != None):
							if(p2 == None):
								p1.addMatch(None, p1status, p1dropped, iRounds+1 > standing.roundsDay1, iRounds+1 > standing.roundsDay2, table)
							else:
								p1.addMatch(p2, p1status, p1dropped, iRounds+1 > standing.roundsDay1, iRounds+1 > standing.roundsDay2, table)
							if(addP1 == True):
								standing.players.append(p1)
							if p1status == -1 and not p1.dropRound>-1:
								stillPlaying += 1

						if(p2 != None):
							if(p1 == None):
								p2.addMatch(None, p2status, p2dropped, iRounds+1 > standing.roundsDay1, iRounds+1 > standing.roundsDay2, table)
							else:
								p2.addMatch(p1, p2status, p2dropped, iRounds+1 > standing.roundsDay1, iRounds+1 > standing.roundsDay2, table)
							if(addP2 == True):
								standing.players.append(p2)

					if(len(standing.hidden)>0):
						for player in standing.players:
							if(player.name in standing.hidden):
								standing.players.remove(player)

					nbPlayers = len(standing.players)

					for player in standing.players:
						if((len(player.matches) >= standing.roundsDay1) or standing.roundsDay1 > iRounds+1):
							player.UpdateWinP(standing.roundsDay1, standing.roundsDay2, iRounds+1)
					for player in standing.players:
						if((len(player.matches) >= standing.roundsDay1) or standing.roundsDay1 > iRounds+1):
							player.UpdateOppWinP(standing.roundsDay1, standing.roundsDay2, iRounds+1)
					for player in standing.players:
						if((len(player.matches) >= standing.roundsDay1) or standing.roundsDay1 > iRounds+1):
							player.UpdateOppOppWinP(standing.roundsDay1, standing.roundsDay2, iRounds+1)

					if(iRounds+1 <= standing.roundsDay2):
						standing.players.sort(key=lambda p:(not p.dqed, p.points, p.late, round(p.OppWinPercentage*100, 2), round(p.OppOppWinPercentage*100, 2)), reverse=True)
						placement = 1
						for player in standing.players:
							if(not player.dqed):
								player.topPlacement = placement
								placement = placement + 1
							else:
								player.topPlacement = 9999
					else:
						if(iRounds+1 > standing.roundsDay2):
							for place in range(nbPlayers):
								if(len(standing.players[place].matches) == iRounds+1):
									if(standing.players[place].matches[len(standing.players[place].matches)-1].status == 2):#if top win
										stop = False
										for above in range(place-1, -1, -1):
											if(stop == False):
												if(len(standing.players[place].matches) == len(standing.players[above].matches)):
													if(standing.players[above].matches[len(standing.players[place].matches)-1].status == 2):#if player above won, stop searching
														stop = True
													if(standing.players[above].matches[len(standing.players[place].matches)-1].status == 0):#if player above lost, swap placement
														tempPlacement = standing.players[above].topPlacement
														standing.players[above].topPlacement = standing.players[place].topPlacement
														standing.players[place].topPlacement = tempPlacement
														standing.players.sort(key=lambda p:(not p.dqed, nbPlayers-p.topPlacement-1, p.points, p.late, round(p.OppWinPercentage*100, 2), round(p.OppOppWinPercentage*100, 2)), reverse=True)
														place = place - 1
														above = -1
					
					#rounds depending on attendance
					if(standing.type == "TCG" or standing.type == "VGC2"):
						if(standing.roundsDay1 == 999):
							roundsSet = True
							if(4 <= nbPlayers <= 8):
								standing.roundsDay1 = 3
								standing.roundsDay2 = 3
							if(9 <= nbPlayers <= 12):
								standing.roundsDay1 = 4
								standing.roundsDay2 = 4
							if(13 <= nbPlayers <= 20):
								standing.roundsDay1 = 5
								standing.roundsDay2 = 5
							if(21 <= nbPlayers <= 32):
								standing.roundsDay1 = 5
								standing.roundsDay2 = 5
							if(33 <= nbPlayers <= 64):
								standing.roundsDay1 = 6
								standing.roundsDay2 = 6
							if(65 <= nbPlayers <= 128):
								standing.roundsDay1 = 7
								standing.roundsDay2 = 7
							if(129 <= nbPlayers <= 226):
								standing.roundsDay1 = 8
								standing.roundsDay2 = 8
							if(227 <= nbPlayers <= 799):
								standing.roundsDay1 = 9
								standing.roundsDay2 = 14
							if(nbPlayers >= 800):
								standing.roundsDay1 = 9
								standing.roundsDay2 = 15
					if(standing.type == "VGC1"):
						if(standing.roundsDay1 == 999):
							roundsSet = True
							if(4 and nbPlayers < 8):
								standing.roundsDay1 = 3
							if(nbPlayers == 8):
								standing.roundsDay1 = 3
							if(9 <= nbPlayers <= 16):
								standing.roundsDay1 = 4
							if(17 <= nbPlayers <= 32):
								standing.roundsDay1 = 5
							if(33 <= nbPlayers <= 64):
								standing.roundsDay1 = 6
							if(65 <= nbPlayers <= 128):
								standing.roundsDay1 = 7
							if(129 <= nbPlayers <= 226):
								standing.roundsDay1 = 8
							if(227 <= nbPlayers <= 256):
								standing.roundsDay1 = 8
							if(257 <= nbPlayers <= 409):
								standing.roundsDay1 = 9
							if(410 <= nbPlayers <= 512):
								standing.roundsDay1 = 9
							if(nbPlayers >= 513):
								standing.roundsDay1 = 10
							standing.roundsDay2 = standing.roundsDay1						
					if(roundsSet == True and iRounds == 0):
						print("Standing : " + standing.type + " - " + standing.tournamentName + " - in " + standing.tournamentDirectory + "/" + standing.directory + " for " + standing.divisionName + " NbPlayers: "+ str(len(standing.players)) + " -> [" + standing.level + "/" + str(standing.roundsDay1) + "/" + str(standing.roundsDay2) + "]")

					if(decklists_players):
						for player in standing.players:
							deck_index = -1
							pos = -1
							for p in decklists_players.players:
								pos = pos + 1
								if((p.name.upper() == player.name.upper() or RemoveCountry(p.name).upper() == RemoveCountry(player.name).upper()) and p.level == player.level):
									deck_index = pos
									break
							if(deck_index != -1):
								player.decklist_ptcgo = decklists_players.players[deck_index].ptcgo_decklist
								player.decklist_json = decklists_players.players[deck_index].json_decklist
					
					if(iRounds+1 == standing.roundsDay2+3 and stillPlaying == 0):
						winner = standing.players[0]

			countries = []
			for player in standing.players:
				countries.append(player.country)
			countryCounter=Counter(countries)
			namesCountries=list(countryCounter.keys())
			countCountries=list(countryCounter.values())

			if len(countries)>0:
				countCountries, namesCountries = zip(*sorted(zip(countCountries, namesCountries), reverse=True))
			
			did_update_tournament = False

			# this should always be true just roll w it
			if(tournament != None):		
				if(len(standing.players) > 0):
					# if standing.directory.lower() == 'masters' and tournament['roundNumbers'][standing.directory.lower()] != iRoundsFromUrl:
						# send_tweet('Masters pairings for round ' + str(iRoundsFromUrl) + 'are now up for ' + tournament['name'])

					tournament['lastUpdated'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
					tournament['roundNumbers'][standing.directory.lower()] = iRoundsFromUrl

					if not is_vgc:
						# Adds in the object for the tournament if there isn't one (there should be)
						if 'should_reveal_decks' not in tournament or tournament['should_reveal_decks'] == None:
							tournament['should_reveal_decks'] = {
								'juniors': False,
								'seniors': False,
								'masters': False 
							}
						# Reveals decks on the last day of day 1
						tournament['should_reveal_decks'][standing.directory.lower()] = iRoundsFromUrl >= standing.roundsDay1

					if "players" not in tournament:
						tournament['players'] = {}
					tournament['players'][standing.directory.lower()] = len(standing.players)
					if(winner != None):
						tournament['winners'][standing.directory.lower()] = winner.name
					if(winner != None and standing.directory.lower() == 'masters'):
						tournament['tournamentStatus'] = "finished"
					else:
						tournament['tournamentStatus'] = "running"
				did_update_tournament = True
				if(not did_update_tournament):
					raise Exception('Tournament not updated in fetch_and_refresh_tournaments: ' + standing.tournamentDirectory)

			nbRounds = 0

			if(decklists_players):
				for player in standing.players:
					deck_index = -1
					pos = -1
					for p in decklists_players.players:
						pos = pos + 1
						if((p.name == player.name or RemoveCountry(p.name) == RemoveCountry(player.name)) and p.level == player.level):
							deck_index = pos
							break
					if(deck_index != -1):
						player.decklist_ptcgo = decklists_players.players[deck_index].ptcgo_decklist
						player.decklist_json = decklists_players.players[deck_index].json_decklist

			for player in standing.players:
				players_export.append(player.get_export_object(tournament['id']))

		# START - updating tournament
		tournament_index = -1
		ctr = 0
		for temp_tourn in tournaments:
			if temp_tourn['id'] == tournament['id']:
				tournament_index = ctr
				break
			ctr += 1

		if tournament_index == -1:
			raise Exception('Tournament not found: ' + tournament['name'])

		# Add dates
		if tournament['date'] == None:
			add_dates_to_tournament(date, tournament)

		if tournament_should_be_finished(tournament):
			print('Overriding tournament status to finished...')
			tournament['tournamentStatus'] = 'finished'

		if 'event_type' not in tournament:
			tournament['event_type'] = get_event_type(tournament['name'])

		# Add format if TCG
		if not is_vgc:
			tournament['format'] = get_tournament_format(formats, tournament)

		# Set true for being finalized in standings
		if tournament['tournamentStatus'] == 'finished':
			tournament['finalized_in_standings'] = True
		
		tournaments[tournament_index] = tournament
		# Update tournaments table
		tournaments_table = 'tournaments_vgc' if is_vgc else 'tournaments_new'
		supabase_client.table(tournaments_table).upsert([tournament]).execute()

		# Update standings table
		standings_table = 'standings_vgc' if is_vgc else 'standings_new'
		supabase_client.table(standings_table).upsert(players_export).execute()


		now = datetime.now() #current date and time
		print('Ending at ' + now.strftime("%Y/%m/%d - %H:%M:%S") + " with no issues")
		return {
        'statusCode': 200,
        'body': 'Tournament successfully updated'
    }
	except Exception as e:
		logging.error(e,exc_info=True)

		now = datetime.now() #current date and time
		print('Ending at ' + now.strftime("%Y/%m/%d - %H:%M:%S") + " WITH ISSUES")
		return {
        'statusCode': 200,
        'body': str(e)
    }
