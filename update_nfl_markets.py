"""Read-only Kalshi NFL contracts matched to verified snap-verified appearances."""
import datetime as dt
import json
import pathlib
import time
import urllib.parse
from update_markets import API, get, history, match_market
from update_data import save_json

ROOT=pathlib.Path(__file__).resolve().parent
SERIES={'KXNFLPASSYDS':('PASS_YDS','Passing yards'),'KXNFLRSHYDS':('RUSH_YDS','Rushing yards'),
 'KXNFLRECYDS':('REC_YDS','Receiving yards'),'KXNFLREC':('REC','Receptions'),
 'KXNFLPASSTDS':('PASS_TD','Passing touchdowns'),'KXNFLRRYDS':('SCRIM_YDS','Rush + receiving yards')}
ALIASES={'WAS':['WAS','WSH'],'LAR':['LAR','LA'],'LV':['LV','OAK'],'LAC':['LAC','SD']}

def match_nfl(m,key,label,histories,schedule,now,blocked):
    event=m.get('event_ticker','').split('-',1)[-1]
    normalized=None
    for g in schedule:
        code=dt.date.fromisoformat(g['date']).strftime('%y%b%d').upper()
        for a in ALIASES.get(g['away'],[g['away']]):
            for h in ALIASES.get(g['home'],[g['home']]):
                if event==code+a+h:
                    normalized={**m,'event_ticker':m['event_ticker'].split('-',1)[0]+'-'+code+g['away']+g['home']}
    if not normalized: return None
    row=match_market(normalized,key,label,histories,schedule,now)
    if not row or row['team'] in blocked: return None
    row['eventTicker']=m['event_ticker']
    row['shortlist']=row['games']>=8 and row['rate']>=80 and row['last5']['rate']>=80 and row['last10']['rate']>=80 and row['priceCents']<=75 and row['spreadCents']<=15
    row['sourceType']='Kalshi listing + nflverse/ESPN history'
    return row

def main():
    props=json.loads((ROOT/'data/nfl_props.json').read_text());cache=json.loads((ROOT/'data/nfl_game_cache.json').read_text())
    if props.get('verified') is not True: raise RuntimeError('Verified NFL statistics required')
    histories=history(cache);now=dt.datetime.now(dt.timezone.utc);rows=[];errors=[];scanned=0
    for series,(key,label) in SERIES.items():
        cursor='';seen=set();matched=[]
        try:
            while True:
                q=urllib.parse.urlencode({'series_ticker':series,'status':'open','limit':1000,'cursor':cursor})
                data=get(API+'/markets?'+q)
                for m in data['markets']:
                    scanned+=1
                    row=match_nfl(m,key,label,histories,props['schedule'],now,props['blockedTeams'])
                    if row:matched.append(row)
                cursor=data.get('cursor','')
                if not cursor:break
                if cursor in seen:raise ValueError('Repeated pagination cursor')
                seen.add(cursor);time.sleep(.25)
            rows.extend(matched)
        except Exception as e:errors.append(series+': '+str(e))
    if errors and not rows: raise RuntimeError('No verified NFL market series: '+'; '.join(errors))
    rows.sort(key=lambda r:(not r['shortlist'],-r['last10']['rate'],-r['rate'],-r['games'],r['player'],r['stat'],r['threshold']))
    result={'status':'partial' if errors else 'ok','sport':'NFL','updatedAt':now.isoformat(),
      'statsUpdatedAt':props['updatedAt'],'rows':rows,'errors':errors,'marketsScanned':scanned,
      'platforms':{'Kalshi':{'status':'partial' if errors else 'connected','matched':len(rows)},'FanDuel':{'status':'unavailable','matched':0}},
      'method':'NFL shortlist: 8+ snap-verified appearances; season, last 5 and up-to-last 10 hit rates >=80%; Yes ask <=75 cents; spread <=15 cents. Recent windows use available season appearances. Injuries and future snap counts not verified. Fees excluded. Unsupported touchdown settlement rules are not approximated.'}
    save_json(ROOT/'data/nfl_markets.json',result)
    print(f'NFL markets: {scanned} scanned; {len(rows)} matched; {sum(r["shortlist"] for r in rows)} shortlist; {len(errors)} errors',flush=True)
if __name__=='__main__':main()
