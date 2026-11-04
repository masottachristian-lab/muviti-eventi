"""Collect factual event fields from explicitly licensed municipal calendars."""
import hashlib
import re
import time
import urllib.request
import urllib.robotparser
from datetime import datetime
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
USER_AGENT = 'Muviti-events/1.0 (+https://github.com/masottachristian-lab/muviti-eventi)'
MONTHS = dict(zip('gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre'.split(), range(1, 13)))
def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'text/html'})
    with urllib.request.urlopen(request, timeout=20) as response:
        if urlparse(response.url).hostname != urlparse(url).hostname:
            raise ValueError('Unexpected cross-domain redirect')
        return response.read(2_000_001).decode('utf-8')
def italian_date(text):
    match = re.search(r'\b(\d{1,2})\s+(' + '|'.join(MONTHS) + r')\s+(\d{4})\b', text.lower())
    if not match: return None
    day, month, year = match.groups()
    return datetime(int(year), MONTHS[month], int(day)).date().isoformat()
def section_text(soup, anchor):
    node = soup.find(id=anchor)
    if node is None: return ''
    section = node.find_parent(class_='paragraph') or node.find_parent(class_='row')
    return section.get_text(' ', strip=True) if section else ''
def parse_event(html, url, source):
    soup = BeautifulSoup(html, 'html.parser')
    title = soup.select_one('[data-element="event-title"]')
    if title is None: return None
    start = soup.find(string=re.compile(r'Data\s+inizio', re.I))
    date = italian_date(start.parent.parent.get_text(' ', strip=True)) if start else None
    if date is None: return None
    end_node = soup.find(string=re.compile(r'Data\s+fine', re.I))
    end_date = italian_date(end_node.parent.parent.get_text(' ', strip=True)) if end_node else None
    clock = soup.find(string=re.compile(r'\d{1,2}:\d{2}\s*-\s*Inizio evento'))
    clock_match = re.search(r'\b(\d{1,2}):([0-5]\d)\b', str(clock)) if clock else None
    event_time = f'{int(clock_match[1]):02d}:{clock_match[2]}' if clock_match else None
    place = soup.select_one('.card-place')
    venue_node = place.select_one('.card-title') if place else None
    address_node = place.select_one('.card-text') if place else None
    if venue_node is None or address_node is None: return None
    cost = section_text(soup, 'costo').lower()
    price = 0 if re.search(r'\bgratuit[oa]\b|ingresso libero', cost) else None
    name = title.get_text(' ', strip=True)
    lower = name.lower()
    category = ('Concerti' if re.search(r'concerto|musica|jazz', lower) else 'Fiere' if re.search(r'fiera|mercat|sagra', lower) else 'Serate' if re.search(r'dj set|discoteca|party', lower) else 'Cultura e mostre')
    event = {'id': source['id'] + '-' + hashlib.sha256(url.encode()).hexdigest()[:16], 'title': name[:200], 'category': category, 'date': date, 'time': event_time, 'venue': venue_node.get_text(' ', strip=True)[:200], 'address': address_node.get_text(' ', strip=True)[:300], 'price': price, 'source': source['name'], 'url': url, 'license': 'CC BY 4.0', 'licenseUrl': 'https://creativecommons.org/licenses/by/4.0/'}
    if end_date and end_date >= date: event['endDate'] = end_date
    return event
def collect_source(source, today, getter=fetch, pause=time.sleep):
    base = source['calendar']
    policy = BeautifulSoup(getter(source['permissionUrl']), 'html.parser').get_text(' ', strip=True)
    if not re.search(r'CC[-\s]BY\s*4\.0', policy, re.I): raise ValueError('Reuse license no longer confirmed')
    robot = urllib.robotparser.RobotFileParser()
    robot.parse(getter(urljoin(base, '/robots.txt')).splitlines())
    if not robot.can_fetch(USER_AGENT, base): raise ValueError('Calendar blocked by robots.txt')
    soup = BeautifulSoup(getter(base), 'html.parser')
    urls = []
    for link in soup.select('a[href]'):
        url = urljoin(base, link['href']).split('#')[0]
        if urlparse(url).hostname == urlparse(base).hostname and '/it/events/' in urlparse(url).path and url not in urls: urls.append(url)
    events, failures = [], 0
    for url in urls[:25]:
        if not robot.can_fetch(USER_AGENT, url):
            failures += 1
            continue
        pause(1)
        try:
            event = parse_event(getter(url), url, source)
            if event and event.get('endDate', event['date']) >= today: events.append(event)
            elif event is None: failures += 1
        except Exception: failures += 1
    if urls and failures == min(len(urls), 25): raise ValueError('No event detail could be parsed')
    return events, failures
def collect(sources, today, previous=(), getter=fetch, pause=time.sleep):
    events, statuses = [], []
    for source in sources:
        try:
            found, failures = collect_source(source, today, getter, pause)
            events.extend(found)
            statuses.append({**source, 'status': 'partial' if failures else 'ok', 'count': len(found)})
        except Exception as error:
            retained = [e for e in previous if e['id'].startswith(source['id'] + '-') and e.get('endDate', e['date']) >= today]
            events.extend(retained)
            statuses.append({**source, 'status': 'error', 'count': len(retained)})
            print(f"Source {source['id']} unavailable: {type(error).__name__}")
    return events, statuses
