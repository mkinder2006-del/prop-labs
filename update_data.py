#!/usr/bin/env python3
"""Prop Labs: incremental, league-wide NBA regular-season box-score ingestion.
ESPN endpoints are unofficial. Errors never overwrite previously verified output.
"""
import datetime as dt
import json
import os
import pathlib
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).resolve().parent
DATA = ROOT / 'data'
DATA.mkdir(exist_ok=True)
CACHE = DATA / 'game_cache.json'
OUTPUT = DATA / 'props.json'
BASE = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba'
SEASON = int(os.environ.get('NBA_SEASON', dt.datetime.now(ZoneInfo('America/New_York')).year if dt.datetime.now(ZoneInfo('America/New_York')).month >= 10 else dt.datetime.now(ZoneInfo('America/New_York')).year - 1))
# Season starts in October; use Oct 1 to avoid guessing opening night.
START = dt.date(SEASON, 10, 1)
TODAY = dt.datetime.now(ZoneInfo('America/New_York')).date()
TEAM_CODES = {'GS':'GSW','NY':'NYK','NO':'NOP','SA':'SAS','UTAH':'UTA'}

def get_json(url, attempts=3):
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0 (compatible; PropLabs/1.0; personal-research)', 'Accept':'application/json'})
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.load(r)
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            if attempt == attempts - 1:
                raise RuntimeError(f'{url}: {exc}') from exc
            time.sleep(2 ** attempt + random.random())

def save_json(path, value):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, separators=(',', ':'), ensure_ascii=False), encoding='utf-8')
    temp.replace(path)

def abbr(team):
    return TEAM_CODES.get(str(team or '').upper(), str(team or '').upper())

def numeric(value):
    try:
        return float(str(value).replace(',', ''))
    except (TypeError, ValueError):
        return None

def extract_game(summary, event_id):
    # ESPN summary -> boxscore.players[].statistics[].labels and athletes[].stats
    sides = summary.get('boxscore', {}).get('players', [])
    if len(sides) != 2:
        raise ValueError(f'Incomplete ESPN box score for {event_id}')
    result = []
    for side in sides:
        team = abbr(side.get('team', {}).get('abbreviation'))
        if not team:
            raise ValueError('Missing team abbreviation')
        for group in side.get('statistics', []):
            labels = [str(x).lower().strip() for x in group.get('labels', [])]
            for entry in group.get('athletes', []):
                athlete = entry.get('athlete', {})
                stats = entry.get('stats') or []
                if entry.get('didNotPlay'):
                    continue
                if not stats or len(stats) != len(labels):
                    raise ValueError('Missing stats for participating player')
                # DNP rows typically have no numeric stat vector.
                values = dict(zip(labels, stats))
                def stat(*names):
                    for name in names:
                        if name in values:
                            return numeric(values[name])
                    return None
                pts = stat('pts','points')
                reb = stat('reb','rebs','rebounds')
                ast = stat('ast','assists')
                three = stat('3pm','3fgm')
                if three is None and '3pt' in values:
                    three = numeric(str(values['3pt']).split('-')[0])
                stl = stat('stl','steals')
                blk = stat('blk','blocks')
                if any(x is None or x < 0 or x != int(x) for x in (pts,reb,ast,three,stl,blk)):
                    raise ValueError('Invalid player statistics')
                aid = str(athlete.get('id') or '')
                if not aid:
                    continue
                pos = athlete.get('position') or {}
                result.append({'id':aid,'player':athlete.get('displayName') or athlete.get('fullName') or aid,
                               'team':team,'position':pos.get('abbreviation') or '—',
                               'starter':bool(entry.get('starter') is True),
                               'PTS':int(pts),'REB':int(reb),'AST':int(ast),'3PM':int(three),
                               'STL':int(stl),'BLK':int(blk)})
    if len(result) < 8:
        raise ValueError(f'Suspiciously few player lines ({len(result)}) for {event_id}')
    header = summary.get('header', {})
    if str(header.get('id')) != str(event_id) or header.get('season', {}).get('type') != 2 or header.get('season', {}).get('year') != SEASON + 1:
        raise ValueError('Box score event/season mismatch')
    comp = header['competitions'][0]
    if not comp.get('status', {}).get('type', {}).get('completed'):
        raise ValueError('Game is not final')
    if len({p['id'] for p in result}) != len(result):
        raise ValueError('Duplicate player lines')
    for c in comp['competitors']:
        team = abbr(c['team']['abbreviation'])
        lines = [p for p in result if p['team'] == team]
        if len(lines) < 5 or sum(p['PTS'] for p in lines) != int(c['score']):
            raise ValueError('Player points do not reconcile to final score: ' + team)
    return result

def get_games_for_date(day):
    url = BASE + '/scoreboard?' + urllib.parse.urlencode({'dates':day.strftime('%Y%m%d'),'limit':100,'seasontype':2})
    return get_json(url).get('events', [])

def derive(cache, upcoming, fetched, errors):
    histories = defaultdict(list)
    for event in sorted(cache.values(), key=lambda e: e['date']):
        if not event.get('players'):
            continue
        for p in event['players']:
            histories[p['id']].append(p)
    matchups = {}
    for game in upcoming:
        for team in (game['away'],game['home']):
            matchups[team] = game['match']
    metrics = [('PTS','Points'),('REB','Rebounds'),('AST','Assists'),('3PM','3-pointers'),
               ('STL','Steals'),('BLK','Blocks'),('P+R','Points + Rebounds'),
               ('P+A','Points + Assists'),('R+A','Rebounds + Assists'),('PRA','PRA')]
    # Conservative research floors: avoid trivial 1+ point/rebound/assist lines.
    # These are plausibility filters, NOT proof a sportsbook lists a market.
    minimum_thresholds = {
        'Points': 10, 'Rebounds': 5, 'Assists': 4, '3-pointers': 2,
        'Steals': 1, 'Blocks': 1, 'Points + Rebounds': 15,
        'Points + Assists': 15, 'Rebounds + Assists': 8, 'PRA': 20,
    }
    output = []
    for aid, games in histories.items():
        latest = games[-1]
        counts = len(games)
        # Require a confirmed start in the latest appearance; unknown and bench roles fail closed.
        recent_known = [g for g in games[-3:] if 'starter' in g]
        recent_starts = sum(g.get('starter') is True for g in recent_known)
        starter_verified = games[-1].get('starter') is True and recent_starts >= max(1, len(recent_known)-1)
        if not counts:
            continue
        for key,label in metrics:
            vals = []
            for g in games:
                v = {'PTS':g['PTS'],'REB':g['REB'],'AST':g['AST'],'3PM':g['3PM'],
                     'STL':g['STL'],'BLK':g['BLK'],
                     'P+R':g['PTS']+g['REB'],'P+A':g['PTS']+g['AST'],
                     'R+A':g['REB']+g['AST'],'PRA':g['PTS']+g['REB']+g['AST']}[key]
                vals.append(v)
            avg = round(sum(vals)/counts,1)
            # Include all integer thresholds with >= 80% hits, so red and green rates both appear.
            for threshold in range(minimum_thresholds[label],max(vals)+1):
                hits = sum(v >= threshold for v in vals)
                rate = round(hits/counts*100,1)
                if rate < 80:
                    continue
                def recent_record(n):
                    sample = vals[-n:]
                    count = sum(value >= threshold for value in sample)
                    return {'hits':count,'games':len(sample),'rate':round(100*count/len(sample),1)}
                output.append({'player':latest['player'],'team':latest['team'],'position':latest['position'],
                               'matchup':matchups.get(latest['team'],'—'),'games':counts,'stat':label,
                               'starterVerified':starter_verified,'starterEvidence':'ESPN box score starter flag; latest appearance with available recent-start confirmation' if starter_verified else 'Unconfirmed or reserve',
                               'threshold':threshold,'avg':avg,'hits':hits,'rate':rate,
                               'last5':recent_record(5),'last10':recent_record(10),'last20':recent_record(20),
                               'sourceUrl':'https://www.espn.com/nba/player/_/id/'+str(aid),
                               'sourceType':'ESPN box scores · custom threshold'})
    output.sort(key=lambda r:(-r['rate'],-r['games'],r['player'],r['stat'],r['threshold']))
    return {'status':'ok','verified':True,'validation':'All discovered final regular-season games parsed; player points reconcile to final scores','source':'ESPN unofficial public JSON endpoints',
            'updatedAt':dt.datetime.now(dt.timezone.utc).isoformat(),
            'season':f'{SEASON}-{str(SEASON+1)[-2:]}','regularSeasonOnly':True,
            'gamesCached':len(cache),'playersTracked':len(histories),
            'schedule':upcoming,'rows':output,'fetchErrors':errors[:25],
            'notes':'Plausible research floors applied; custom integer thresholds are not verified sportsbook odds. Only completed games with parseable ESPN player box scores are counted; data may be incomplete if upstream is unavailable.'}

def main():
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    cache = {k:v for k,v in cache.items() if v.get('season') == SEASON}
    previous = json.loads(OUTPUT.read_text()) if OUTPUT.exists() else None
    errors = []
    # Cache completed games forever; recheck recent 2 days for corrections.
    date = START
    events = {}
    upcoming = []
    successful_dates = 0
    while date <= TODAY + dt.timedelta(days=7):
        try:
            daily = get_games_for_date(date)
            successful_dates += 1
            for ev in daily:
                if ev.get('season', {}).get('type') != 2 or ev.get('season', {}).get('year') != SEASON + 1:
                    continue
                eid = str(ev.get('id') or '')
                if not eid:
                    continue
                comp = (ev.get('competitions') or [{}])[0]
                competitors = comp.get('competitors') or []
                home = next((abbr(c.get('team',{}).get('abbreviation')) for c in competitors if c.get('homeAway')=='home'), '')
                away = next((abbr(c.get('team',{}).get('abbreviation')) for c in competitors if c.get('homeAway')=='away'), '')
                complete = ev.get('status',{}).get('type',{}).get('completed',False)
                if complete:
                    events[eid] = {'id':eid,'date':date.isoformat()}
                elif date >= TODAY and home and away:
                    upcoming.append({'id':eid,'date':date.isoformat(),'match':f'{away} @ {home}',
                                     'away':away,'home':home,'time':ev.get('date','')})
        except Exception as exc:
            errors.append(f'Schedule {date}: {exc}')
        date += dt.timedelta(days=1)
        # Avoid hammering ESPN; undocumented endpoints may rate-limit.
        time.sleep(0.35)
    if errors:
        raise RuntimeError('Incomplete schedule scan; refusing publication: ' + '; '.join(errors[:5]))
    if successful_dates == 0:
        raise RuntimeError('No schedules retrieved. Preserving previous verified output.')
    fetched = 0
    for eid, ev in events.items():
        if eid in cache and (TODAY-dt.date.fromisoformat(ev['date'])).days > 2:
            continue
        try:
            summary = get_json(BASE + '/summary?event=' + urllib.parse.quote(eid))
            players = extract_game(summary,eid)
            cache[eid] = {'date':ev['date'],'season':SEASON,'players':players}
            fetched += 1
        except Exception as exc:
            errors.append(f'Boxscore {eid}: {exc}')
        time.sleep(0.75)
    # Never publish a "verified" empty dashboard.
    if not cache:
        raise RuntimeError('No complete player box scores retrieved. Not publishing empty output.')
    # Guard against incomplete historical scan being published as complete.
    if errors and previous and len(cache) < max(1, int(previous.get('gamesCached', 0) * 0.9)):
        raise RuntimeError('Suspiciously incomplete refresh; preserving previous output.')
    if errors or set(events) - set(cache):
        raise RuntimeError('Incomplete box scores; refusing publication: ' + '; '.join(errors[:5]))
    cache = {k:cache[k] for k in events}
    save_json(CACHE,cache)
    result = derive(cache, sorted(upcoming,key=lambda g:g['time']), fetched, errors)
    if not result['rows']:
        raise RuntimeError('No valid prop rows computed. Preserving previous output.')
    save_json(OUTPUT,result)
    print(f"Updated {len(cache)} games, {result['playersTracked']} players, {len(result['rows'])} prop rows; {fetched} game summaries fetched; {len(errors)} errors")

if __name__ == '__main__':
    main()
