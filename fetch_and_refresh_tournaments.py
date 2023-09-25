from bs4 import BeautifulSoup
import requests
import time
from datetime import datetime
from os.path import exists
import json
import traceback

def fetch_and_refresh_tournaments(s3Client):
	try:		
		openTournaments = []
		s3TablesResponse = s3Client.get_object(Bucket='pokescraper',
                         Key='tournaments.json')
		data = s3TablesResponse['Body'].read()
		openTournaments = json.loads(data)

		page = requests.get('https://rk9.gg/events/pokemon')
		soup = BeautifulSoup(page.content, "html.parser")
		tournaments = soup.find_all('table', attrs={'id':'dtUpcomingEvents'})
		tbody = tournaments[0].find('tbody')
		if(tbody):
			trs = tbody.find_all('tr')
			for tr in trs:
				tds = tr.find_all('td')
				if(len(tds) == 5):
					tName = tds[2].text.replace('\n', '').lstrip(' ').rstrip(' ')
					linkRef = ''
					links = tds[4].find_all('a', href=True)
					for link in links:
						if('tcg' in link.text.lower()):
							linkRef = link['href'].replace('/tournament/', '')
					if(len(linkRef)>0):
						tournamentAlreadyDiscovered = False
						for tournament in openTournaments:
							print(tournament)
							if(tournament['rk9link'] == linkRef):
								tournamentAlreadyDiscovered = True
							
						if(not(tournamentAlreadyDiscovered)):
							print('new Tournament! ' + tName + ' with url ' + linkRef)

							rk9_url = 'https://rk9.gg/tournament/' + linkRef
							tournament_page = requests.get(rk9_url)
							tournament_soup = BeautifulSoup(tournament_page.content, "html.parser")
							page_title = tournament_soup.find('h3', {'class': 'mb-0'}).text
							date =  page_title.split('\n')[1]

							months = {'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04', 'may': '05', 'jun': '06', 'jul': '07', 'aug': '08', 'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'}
							dateFields = date.replace('–', ' ').replace('-', ' ').replace(', ', ' ').split(" ")
							if len(dateFields) > 4:
								startDate = dateFields[4] + '-' + months[dateFields[0].strip()[:3].lower()] + '-' + f'{int(dateFields[1]):02d}'
								endDate = dateFields[4] + '-' + months[dateFields[2].strip()[:3].lower()] + '-' + f'{int(dateFields[3]):02d}'
							else:
								startDate = dateFields[3] + '-' + months[dateFields[0].strip()[:3].lower()] + '-' + f'{int(dateFields[1]):02d}'
								endDate = dateFields[3] + '-' + months[dateFields[0].strip()[:3].lower()] + '-' + f'{int(dateFields[2]):02d}'
							
							new_id = str(int(openTournaments[-1]['id']) + 1).zfill(7)
							newData = {"id": new_id, "name": tName, "date": {"start": startDate, "end": endDate}, "decklists": 0, "players": {"juniors": 0, "seniors": 0, "masters": 0}, "winners": {"juniors": None, "seniors": None, "masters": None}, "tournamentStatus": "not-started", "roundNumbers": {"juniors": None, "seniors": None, "masters": None}, "lastUpdated": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"), "rk9link": linkRef}

							openTournaments.append(newData)
							s3TournamentsExportString = json.dumps(openTournaments, indent = 4, sort_keys=True, ensure_ascii=False)
							# Update tournaments.json
							s3Client.put_object(Bucket='pokescraper',
								Key='tournaments.json',
								Body=s3TournamentsExportString.encode('UTF-8'),
								ServerSideEncryption='aws:kms')
			
							return openTournaments
			else:
				print('no news @ ' + datetime.now().strftime("%Y/%m/%d - %H:%M:%S"))
		else:
			print('no news @ ' + datetime.now().strftime("%Y/%m/%d - %H:%M:%S"))

		return openTournaments
	
	except Exception as e:
		print(e)
		print(traceback.format_exc())