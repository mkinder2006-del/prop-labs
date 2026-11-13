"""Read-only market matching. No orders, credentials, or fabricated sportsbook lines."""
import datetime as dt
import json
import math
import pathlib
import re
import time
import unicodedata
import urllib.parse
import urllib.request
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parent
API = 'https://api.elections.kalshi.com/trade-api/v2'
SERIES = {'KXNBAPTS': ('PTS','Points'), 'KXNBAREB': ('REB','Rebounds'),
          'KXNBAAST': ('AST','Assists'), 'KXNBA3PT': ('3PM','3-pointers'),
          'KXNBAPRA': ('PRA','PRA')}

def norm(s):
    return re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().lower())

def get(url):
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={'Accept':'application/json','User-Agent':'PropLabs/1.1'}),timeout=25) as r:
                return json.load(r)
        except Exception:
            if attempt == 2: raise
            time.sleep(2 ** attempt)

def history(cache):
    h=defaultdict(list)
    identities=defaultdict(set)
    for event in sorted(cache.values(),key=lambda e:e['date']):
        for p in event['players']:
            identities[norm(p['player'])].add(p.get('id',p['player']))
            h[norm(p['player'])].append({**p,'date':event['date']})
    return {k:v for k,v in h.items() if len(identities[k])==1}

def match_market(m, key, label, histories, schedule, now):
    if m.get('status') != 'active' or m.get('strike_type') != 'greater': return None
    title=m.get('yes_sub_title','')
    found=re.fullmatch(r'(.+):\s*(\d+)\+',title)
    if not found: return None
    name, threshold=found.group(1),int(found.group(2))
    if float(m.get('floor_strike',-1)) != threshold-0.5: return None
    games=histories.get(norm(name),[])
    if not games: return None
    latest=games[-1]
    # Exact event identity: local game date + away/home team codes; never join on player name alone.
    event=m.get('event_ticker','').split('-',1)[-1]
    candidates=[]
    for g in schedule:
        date=dt.date.fromisoformat(g['date'])
        event_code=date.strftime('%y%b%d').upper()+g['away']+g['home']
        if event==event_code and latest['team'] in (g['away'],g['home']): candidates.append(g)
    if len(candidates)!=1: return None
    game=candidates[0]
    start=dt.datetime.fromisoformat(game['time'].replace('Z','+00:00'))
    if start<=now: return None
    close=dt.datetime.fromisoformat(m['close_time'].replace('Z','+00:00'))
    opened=dt.datetime.fromisoformat(m['open_time'].replace('Z','+00:00'))
    if close<=now or opened>now: return None
    ask=float(m.get('yes_ask_dollars') or 0)
    bid=float(m.get('yes_bid_dollars') or 0)
    size=float(m.get('yes_ask_size_fp') or 0)
    if not all(math.isfinite(v) for v in (ask,bid,size)) or not 0<ask<1 or size<=0: return None
    if bid>ask: return None
    vals=[p['PTS']+p['REB']+p['AST'] if key=='PRA' else p[key] for p in games]
    def record(n):
        v=vals[-n:]; hits=sum(x>=threshold for x in v)
        return {'hits':hits,'games':len(v),'rate':round(hits/len(v)*100,1)}
    season=record(len(vals)); recent=record(5); last10=record(10); last20=record(20)
    # Historical screen, NOT a calibrated forecast or expected-value estimate.
    shortlist=len(vals)>=10 and season['rate']>=80 and recent['rate']>=80 and last10['rate']>=80 and ask<=.75 and ask-bid<=.15
    return {'player':latest['player'],'team':latest['team'],'position':latest['position'],
      'matchup':game['match'],'gameTime':game['time'],'stat':label,'threshold':threshold,
      'avg':round(sum(vals)/len(vals),1),'games':len(vals),'hits':season['hits'],'rate':season['rate'],
      'last5':recent,'last10':last10,'last20':last20,'platform':'Kalshi','side':'Yes',
      'priceCents':round(ask*100,2),'bidCents':round(bid*100,2),'spreadCents':round((ask-bid)*100,2),
      'askSize':size,'ticker':m['ticker'],'eventTicker':m['event_ticker'],
      'sourceUrl':API+'/markets/'+urllib.parse.quote(m['ticker']),
      'observedAt':now.isoformat(),'marketUpdatedAt':m.get('updated_time'),
      'shortlist':shortlist,'sourceType':'Kalshi listing + ESPN history'}

def main():
    props=json.loads((ROOT/'data/props.json').read_text()); cache=json.loads((ROOT/'data/game_cache.json').read_text())
    if props.get('verified') is not True: raise RuntimeError('Verified statistics required')
    histories=history(cache); now=dt.datetime.now(dt.timezone.utc); rows=[]; errors=[]; scanned=0
    for series,(key,label) in SERIES.items():
        cursor=''; seen=set(); matched=[]
        try:
            while True:
                q=urllib.parse.urlencode({'series_ticker':series,'status':'open','limit':1000,'cursor':cursor})
                payload=get(API+'/markets?'+q)
                for m in payload['markets']:
                    scanned+=1
                    row=match_market(m,key,label,histories,props['schedule'],now)
                    if row: matched.append(row)
                cursor=payload.get('cursor','')
                if not cursor: break
                if cursor in seen: raise ValueError('Repeated pagination cursor')
                seen.add(cursor); time.sleep(.25)
            rows.extend(matched)
        except Exception as e: errors.append(series+': '+str(e))
    rows.sort(key=lambda r:(not r['shortlist'],-r['last10']['rate'],-r['rate'],-r['games'],r['player'],r['stat'],r['threshold']))
    result={'status':'ok' if not errors else 'partial','updatedAt':now.isoformat(),
      'statsUpdatedAt':props['updatedAt'],'rows':rows,'marketsScanned':scanned,'errors':errors,
      'platforms':{'Kalshi':{'status':'partial' if errors else 'connected','matched':len(rows)},
                   'FanDuel':{'status':'unavailable','matched':0,'note':'Current FanDuel lines could not be verified. No FanDuel availability or odds are implied.'}},
      'method':'Shortlist: 10+ appearances; season, last 5 and last 10 hit rates >=80%; Yes ask <=85 cents; bid-ask spread <=15 cents. Historical screen only; injuries, lineups and minutes not verified. Fees excluded from prices. Prices can move.'}
    dest=ROOT/'data/markets.json';tmp=dest.with_suffix('.tmp');tmp.write_text(json.dumps(result,separators=(',',':')));tmp.replace(dest)
    print('Scanned',scanned,'markets;',len(rows),'matched listings;',sum(r['shortlist'] for r in rows),'shortlist;',len(errors),'series errors',flush=True)
    for error in errors: print(error)
    if errors and not rows: raise RuntimeError('No market series could be verified')
if __name__=='__main__': main()
