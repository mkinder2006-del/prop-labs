"""Verified NFL regular-season snapshots: nflverse stats + participation, ESPN checks."""
import concurrent.futures as cf
import csv
import datetime as dt
import hashlib
import io
import json
import pathlib
import time
import urllib.request
from collections import defaultdict
from update_data import get_json, save_json
from update_markets import norm

ROOT=pathlib.Path(__file__).resolve().parent
DATA=ROOT/'data';DATA.mkdir(exist_ok=True)
NOW=dt.datetime.now(dt.timezone.utc)
SEASON=NOW.year if NOW.month>=7 else NOW.year-1
BASE='https://github.com/nflverse/nflverse-data/releases/download/'
SOURCES={'stats':BASE+f'stats_player/stats_player_week_{SEASON}.csv',
 'snaps':BASE+f'snap_counts/snap_counts_{SEASON}.csv',
 'roster':BASE+f'rosters/roster_{SEASON}.csv','schedule':BASE+'schedules/games.csv'}
FIELDS={'PASS_YDS':'passing_yards','PASS_TD':'passing_tds','RUSH_YDS':'rushing_yards',
 'RUSH_TD':'rushing_tds','REC_YDS':'receiving_yards','REC':'receptions','REC_TD':'receiving_tds'}
LABELS={'PASS_YDS':'Passing yards','PASS_TD':'Passing touchdowns','RUSH_YDS':'Rushing yards',
 'REC_YDS':'Receiving yards','REC':'Receptions','SCRIM_YDS':'Rush + receiving yards'}
LADDERS={'PASS_YDS':range(150,401,25),'PASS_TD':range(1,5),'RUSH_YDS':[25,40,50,60,75,100,125],
 'REC_YDS':[25,40,50,60,75,100,125],'REC':range(2,11),'SCRIM_YDS':range(25,201,25)}

def team(s): return {'LA':'LAR','STL':'LAR','SD':'LAC','OAK':'LV','WSH':'WAS'}.get(s,s)
def integer(v):
    n=float(v)
    if not n.is_integer(): raise ValueError('Invalid integer statistic')
    return int(n)
def download(url):
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url,timeout=40) as r: return list(csv.DictReader(io.StringIO(r.read().decode('utf-8-sig'))))
        except Exception:
            if attempt==2: raise
            time.sleep(2**attempt)

def validate_espn(summary,g,stats):
    header=summary['header']
    if str(header['id'])!=g['espn'] or header['season']['year']!=SEASON or header['season']['type']!=2:
        raise ValueError('ESPN game/season mismatch')
    comp=header['competitions'][0]
    if not comp['status']['type']['completed']: raise ValueError('Game not final')
    sides=summary['boxscore']['players']
    if len(sides)!=2: raise ValueError('Missing box-score side')
    checks={'passing':{'YDS':'PASS_YDS','TD':'PASS_TD'},'rushing':{'YDS':'RUSH_YDS','TD':'RUSH_TD'},'receiving':{'YDS':'REC_YDS','REC':'REC','TD':'REC_TD'}}
    for side in sides:
        t=team(side['team']['abbreviation'])
        if t not in [team(g['away_team']),team(g['home_team'])]: raise ValueError('Team mismatch')
        groups={x['name']:x for x in side['statistics']}
        for category,fields in checks.items():
            group=groups[category]
            values=[dict(zip(group['labels'],a['stats'])) for a in group['athletes'] if not a.get('didNotPlay')]
            for label,key in fields.items():
                # Passing team totals are net of sacks; compare gross individual yards instead.
                espn=sum(integer(v[label]) for v in values)
                other=sum(integer(p[FIELDS[key]]) for p in stats if team(p['team'])==t)
                if espn!=other: raise ValueError(f'{t} {key} source mismatch: {espn} vs {other}')
    for c in comp['competitors']:
        score=g['home_score'] if c['homeAway']=='home' else g['away_score']
        if integer(c['score'])!=integer(score): raise ValueError('Final score mismatch')

def build_players(g,stats,snaps,roster):
    byid={p['player_id']:p for p in stats}
    if len(byid)!=len(stats): raise ValueError('Duplicate player stat records')
    players={};unmapped=[]
    for snap in snaps:
        if sum(integer(snap.get(k) or '0') for k in ('offense_snaps','defense_snaps','st_snaps'))<=0 or snap['position'] not in ('QB','RB','FB','HB','WR','TE'): continue
        identity=roster.get(snap['pfr_player_id']) or roster.get('name:'+team(snap['team'])+':'+norm(snap['player']))
        if not identity or not identity['gsis_id']:
            unmapped.append(snap['player']);continue
        aid=identity['gsis_id'];row=byid.get(aid)
        if row and team(row['team'])!=team(snap['team']): raise ValueError('Participation team mismatch')
        # A verified snap appearance without a stat row contributes zero, not a missing game.
        p={'id':aid,'player':(row or {}).get('player_display_name') or identity['full_name'],
           'team':team(snap['team']),'position':snap['position'],'offenseSnaps':integer(snap['offense_snaps']),'totalSnaps':sum(integer(snap.get(k) or '0') for k in ('offense_snaps','defense_snaps','st_snaps'))}
        for key,col in FIELDS.items(): p[key]=integer(row[col]) if row else 0
        p['SCRIM_YDS']=p['RUSH_YDS']+p['REC_YDS']
        if p['id'] in players: raise ValueError('Duplicate snap appearance')
        players[aid]=p
    if unmapped: raise ValueError('Unmapped offensive participants: '+', '.join(unmapped))
    if len(players)<12: raise ValueError('Incomplete offensive participants')
    return list(players.values())

def main():
    with cf.ThreadPoolExecutor(max_workers=4) as pool:
        futures={k:pool.submit(download,url) for k,url in SOURCES.items()}
        data={k:f.result() for k,f in futures.items()}
    schedule=[g for g in data['schedule'] if integer(g['season'])==SEASON and g['game_type']=='REG']
    if not schedule: raise RuntimeError('No current NFL regular-season schedule')
    stats=defaultdict(list);snaps=defaultdict(list)
    for r in data['stats']:
        if r['season']==str(SEASON) and r['season_type']=='REG': stats[r['game_id']].append(r)
    for r in data['snaps']:
        if r['season']==str(SEASON) and r['game_type']=='REG': snaps[r['game_id']].append(r)
    roster={}; name_matches=defaultdict(list)
    for r in data['roster']:
        if r.get('pfr_id') and r.get('gsis_id'): roster[r['pfr_id']]=r
        if r.get('gsis_id'): name_matches['name:'+team(r['team'])+':'+norm(r['full_name'])].append(r)
    for name,candidates in name_matches.items():
        if len({r['gsis_id'] for r in candidates})==1: roster[name]=candidates[0]
    cachepath=DATA/'nfl_game_cache.json'
    old=json.loads(cachepath.read_text()) if cachepath.exists() else {}
    cache={};pending=[];errors=[];upcoming=[];blocked=set();tasks=[]
    for g in schedule:
        gid=g['game_id']
        day=dt.date.fromisoformat(g['gameday'])
        if g['home_score'] and g['away_score'] and day<=NOW.date():
            if gid not in stats or gid not in snaps:
                pending.append(gid);blocked.update([team(g['away_team']),team(g['home_team'])]);continue
            fingerprint=hashlib.sha256(json.dumps([stats[gid],snaps[gid]],sort_keys=True).encode()).hexdigest()
            if gid in old and old[gid].get('fingerprint')==fingerprint:
                cache[gid]={**old[gid],'players':build_players(g,stats[gid],snaps[gid],roster)};continue
            tasks.append((g,fingerprint))
        elif NOW.date()<=day<=NOW.date()+dt.timedelta(days=10):
            # nflverse kickoff times are Eastern local clock times.
            from zoneinfo import ZoneInfo
            stamp=dt.datetime.fromisoformat(g['gameday']+'T'+g['gametime']).replace(tzinfo=ZoneInfo('America/New_York')).astimezone(dt.timezone.utc)
            if stamp>NOW:
                a,h=team(g['away_team']),team(g['home_team'])
                upcoming.append({'id':g['espn'],'date':g['gameday'],'time':stamp.isoformat(),'away':a,'home':h,'match':a+' @ '+h})
    def check(item):
        g,fingerprint=item
        summary=get_json('https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event='+g['espn'])
        validate_espn(summary,g,stats[g['game_id']])
        players=build_players(g,stats[g['game_id']],snaps[g['game_id']],roster)
        return g['game_id'],{'date':g['gameday'],'season':SEASON,'fingerprint':fingerprint,'players':players}
    with cf.ThreadPoolExecutor(max_workers=4) as pool:
        futures={pool.submit(check,item):item[0] for item in tasks}
        for future in cf.as_completed(futures):
            g=futures[future]
            try:
                gid,event=future.result();cache[gid]=event
            except Exception as e:
                errors.append(g['game_id']+': '+str(e));blocked.update([team(g['away_team']),team(g['home_team'])])
    if errors: raise RuntimeError('NFL verification failed; previous output preserved: '+'; '.join(errors[:12]))
    if not cache: raise RuntimeError('No verified NFL games')
    histories=defaultdict(list)
    for g in sorted(cache.values(),key=lambda e:e['date']):
        for p in g['players']: histories[p['id']].append(p)
    matchups={}
    for g in sorted(upcoming,key=lambda e:e['time']):
        for t in (g['away'],g['home']): matchups.setdefault(t,g['match'])
    # Snap-count evidence: only the leading active player in each team/position group.
    # This is not an official injury or depth-chart confirmation.
    latest_by_team_role=defaultdict(list)
    for games in histories.values():
        latest=games[-1]
        role='RB' if latest['position'] in ('RB','FB','HB') else latest['position']
        if role in ('QB','RB','WR','TE'):
            recent=games[-3:]
            latest_by_team_role[(latest['team'],role)].append((sum(p.get('offenseSnaps',0) for p in recent)/len(recent),latest['id']))
    leaders={}
    for key,candidates in latest_by_team_role.items():
        candidates.sort(reverse=True)
        if len(candidates)==1 or candidates[0][0]>candidates[1][0]:
            leaders[key]=candidates[0][1]
    rows=[]
    for games in histories.values():
        latest=games[-1]
        if latest['team'] in blocked: continue
        role='RB' if latest['position'] in ('RB','FB','HB') else latest['position']
        starter_verified=role in ('QB','RB','WR','TE') and leaders.get((latest['team'],role))==latest['id'] and latest.get('offenseSnaps',0)>0
        for key,label in LABELS.items():
            if key.startswith('PASS') and latest['position']!='QB': continue
            vals=[p[key] for p in games]
            for threshold in LADDERS[key]:
                hits=sum(v>=threshold for v in vals);rate=round(hits/len(vals)*100,1)
                if rate<80: continue
                def recent_record(n):
                    sample=vals[-n:]
                    count=sum(v>=threshold for v in sample)
                    return {'hits':count,'games':len(sample),'rate':round(100*count/len(sample),1)}
                rows.append({'player':latest['player'],'team':latest['team'],'position':latest['position'],
                  'matchup':matchups.get(latest['team'],'—'),'stat':label,'threshold':threshold,
                  'starterVerified':starter_verified,'starterEvidence':'Leading recent offensive snap count at position; not an official depth chart' if starter_verified else 'Secondary or unconfirmed role',
                  'games':len(vals),'hits':hits,'rate':rate,'avg':round(sum(vals)/len(vals),1),
                  'last5':recent_record(5),'last10':recent_record(10),'last20':recent_record(20),
                  'sourceUrl':'https://www.nfl.com/players/',
                  'sourceType':'nflverse + ESPN verified · custom threshold'})
    result={'status':'ok','verified':True,'sport':'NFL','season':str(SEASON),'regularSeasonOnly':True,
      'updatedAt':dt.datetime.now(dt.timezone.utc).isoformat(),'gamesCached':len(cache),'playersTracked':len(histories),
      'schedule':sorted(upcoming,key=lambda e:e['time']),'rows':rows,'fetchErrors':[],
      'pendingGames':pending,'blockedTeams':sorted(blocked),'sources':SOURCES,
      'notes':'Snap-verified skill-player appearances including special-teams-only and zero-output games. Inactive/DNP games excluded. Teams with pending snap data are withheld. Pass/rush/receiving totals and final scores reconciled to ESPN. Touchdown market rules vary; unsupported contracts are omitted.'}
    save_json(cachepath,cache);save_json(DATA/'nfl_props.json',result)
    print(f'NFL: {len(cache)} verified games; {len(histories)} players; {len(rows)} research thresholds; {len(pending)} pending games',flush=True)
if __name__=='__main__': main()
