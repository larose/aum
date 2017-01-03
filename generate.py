import arrow
from   bs4 import BeautifulSoup
from   cachecontrol import CacheControl
from   cachecontrol.caches.file_cache import FileCache
import concurrent.futures
import datetime
import html
import itertools
import jinja2
import locale
from   multiprocessing.pool import ThreadPool
import os
import urllib.parse
from   slugify import slugify
import re
import requests


locale.setlocale(locale.LC_ALL, "fr_CA.utf8")
french_months = [datetime.date(2000, i, 1).strftime('%b') for i in range(1, 13)]
locale.setlocale(locale.LC_ALL, "en_CA.utf8")


BUILD_DIR = os.environ.get('BUILD_DIR', 'build')
CACHE_DIR = os.environ.get('CACHE_DIR', 'cache')
HOME_PAGE = os.environ.get('HOME_PAGE', 'http://www.montrealultimate.ca/')
MAX_WORKERS = int(os.environ.get('MAX_WORKERS', 40))
USE_CACHE = os.environ.get('USE_CACHE', 'y').lower()[0:1] == 'y'


class Game:
    def __init__(self, scheduled_time, away_team_name, home_team_name, field_name, division_name, away_score, home_score):
        self.scheduled_time = scheduled_time
        self.away_team_name = away_team_name
        self.home_team_name = home_team_name
        self.field_name= field_name
        self.division_name = division_name
        self.away_score = away_score
        self.home_score = home_score


def fetch_page(session, url):
    resp = session.get(url)
    resp.raise_for_status()
    return resp.text


def format_date(date):
    return ' '.join([date.strftime('%-d'), french_months[date.month - 1], date.strftime('%Y')])

def format_date_without_year(date):
    return ' '.join([date.strftime('%-d'), french_months[date.month - 1]])

def parse_leagues(html_doc):
    soup = BeautifulSoup(html_doc, 'html.parser')

    for a in soup.find_all('a', href=re.compile("ulm/view/[0-9]+/[0-9]+/[0-9]+")):
        yield {
            'name': html.unescape(a.text).replace('_', ' '),
            'href': a['href']
        }


def parse_games(html_doc):
    soup = BeautifulSoup(html_doc, 'html.parser')

    for match_status in soup.find_all('tr', {'class': ['match-status-0', 'match-status-1', 'match-status-2', 'match-status-3', 'match-status-4']}):

        division_name = match_status.find('td', {'class': ['division']}).text.strip()

        away = match_status.find('td', {'class': ['awayteam']})
        a = away.find('a')
        away_team_name = a.text

        home = match_status.find('td', {'class': ['hometeam']})
        a = home.find('a')
        home_team_name = a.text


        away_score = match_status.find('td', {'class': ['awayscore-0', 'awayscore-1', 'awayscore-2', 'awayscore-3', 'awayscore-4']}).text.strip()
        try:
            away_score = int(away_score)
        except:
            if away_score == '-':
                away_score = None


        home_score = match_status.find('td', {'class': ['homescore-0', 'homescore-1', 'homescore-2', 'homescore-3', 'homescore-4']}).text.strip()
        try:
            home_score = int(home_score)
        except:
            if home_score == '-':
                home_score = None

        field = match_status.find('td', {'class': ['field']})
        time = field.find(text=re.compile('[0-9]+:[0-9]+'))

        field_name = field.find('a').text.strip()

        league_schedule = match_status.find_parent('table', {'id': ['ulm-league-schedule']})

        date = league_schedule.find('caption').text

        # TODO: Change locale
        scheduled_time = datetime.datetime.strptime(date + ' ' + time, "%d %b %Y %H:%M")

        yield Game(scheduled_time=scheduled_time, away_team_name=away_team_name,
                   home_team_name=home_team_name, field_name=field_name, division_name=division_name, away_score=away_score, home_score=home_score)


def process_league(session, league, template, last_update):
    print(league['href'])
    league_content = fetch_page(session, league['href'])
    games = list(parse_games(league_content))

    divisions_by_day = []

    field_names = [game.field_name for game in games]
    field_names_prefix = "".join([i[0] for i in itertools.takewhile(lambda x: len(set(x)) == 1, zip(*field_names))])
    for game in games:
        game.field_name_abbr = game.field_name[len(field_names_prefix):]

    dates = [game.scheduled_time for game in games]
    for date, games_for_day in itertools.groupby(sorted(games, key=date_key), date_key):
        divisions_by_day.append((date, []))
        for division_name, games_for_division in itertools.groupby(sorted(games_for_day, key=per_day_key), lambda game: game.division_name):
            divisions_by_day[-1][1].append((division_name, list(games_for_division)))

    context = {
        'divisions_by_day': divisions_by_day,
        'last_update': last_update,
        'league_name': league['name']
    }

    result = {
        'name': league['name'],
        'content': template.render(context),
        'slugified_name': slugify(league['name']),
        'start': min(dates),
        'end': max(dates)
    }

    return result



def date_key(game):
    return game.scheduled_time.date()


def per_day_key(game):
    return game.division_name, game.scheduled_time, game.field_name.lower()


def league_groupby_key(league):
    return '-'.join(league['name'].split('-')[0:2])


def raw_league_key(league):
    index = 0
    name = league['name'].lower()
    if 'junior' in name:
        index = 10
    elif 'playoffs' in name:
        index = 20

    return index, league['name']

def main():
    last_update = arrow.utcnow().to('America/Montreal').format('YYYY-MM-DD HH:mm')
    os.makedirs(BUILD_DIR, exist_ok=True)

    session = requests.session()
    if USE_CACHE:
        cache = FileCache(CACHE_DIR, forever=True)
        session = CacheControl(session, cache=cache)
        session.headers['cache-control'] = 'max-age = 999999999999999'
        os.makedirs(CACHE_DIR, exist_ok=True)

    env = jinja2.Environment(loader=jinja2.FileSystemLoader(os.path.join(os.path.dirname(__file__), 'templates')))
    env.filters['format_date'] = format_date
    env.filters['format_date_without_year'] = format_date_without_year

    home_page_content = fetch_page(session, HOME_PAGE)

    leagues = parse_leagues(home_page_content)

    schedule_league_template = env.get_template('schedule_league.html')

    futures = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        for league in leagues:
            league['href'] = urllib.parse.urljoin(HOME_PAGE, league['href'])
            future = executor.submit(process_league, session, league, schedule_league_template, last_update)
            futures.append(future)

    for future in futures:
        result = future.result()

        filename = os.path.join(BUILD_DIR, result['slugified_name'], 'index.html')
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, 'w') as league_file:
            league_file.write(result['content'])


    index_template = env.get_template('index.html')

    raw_leagues = []
    context = {
        'last_update': last_update,
        'leagues': []
    }

    for future in futures:
        result = future.result()

        raw_leagues.append({
            'name': result['name'],
            'url': result['slugified_name'] + '/',
            'start': result['start'],
            'end': result['end']
        })

    for league_prefix, _leagues in itertools.groupby(sorted(raw_leagues, key=lambda league: league['name']), league_groupby_key):
        _leagues = list(_leagues)
        league_session, league_name = league_prefix.split(' ', maxsplit=1)
        context['leagues'].append({
            'name': "{} ({})".format(league_name.strip(), league_session.strip().replace('-', '&#8209;')),
            'rounds': [
                {
                    'name': l['name'].split('-')[2].strip(),
                    'url': l['url'],
                    'start': l['start'],
                    'end': l['end']
                } for l in sorted(_leagues, key=raw_league_key)
            ]
        })


    with open(os.path.join(BUILD_DIR, 'index.html'), 'w') as index_file:
        index_file.write(index_template.render(context))


if __name__ == '__main__':
    main()
