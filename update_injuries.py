#!/usr/bin/env python3
"""Conservative ESPN injury snapshot ingestion. Missing/ambiguous reports are NOT verified."""
import datetime as dt
import json
import pathlib
import urllib.request
from update_data import save_json

ROOT=pathlib.Path(__file__).resolve().parent
OUT=ROOT/'data'/'injuries.json'
SOURCES={
 'NBA':'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries',
 'NFL':'https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries',
}
TEAMS={'GS':'GSW','NY':'NYK','NO':'NOP','SA':'SAS','UTAH':'UTA','WSH':'WAS','LA':'LAR'}
STATUSES={'out':'Out','inactive':'Inactive','doubtful':'Doubtful','questionable':'Questionable','probable':'Probable','day-to-day':'Day-To-Day','injured reserve':'Injured Reserve','ir':'Injured Reserve'}
def normalized_status(raw):
    raw=str(raw or '').strip().lower()
    return STATUSES.get(raw)
def parse(payload,sport,url):
    if not isinstance(payload,dict) or not isinstance(payload.get('injuries'),list):
        raise ValueError('Unexpected ESPN injury schema; refusing verified designation')
    result=[]
    for team in payload['injuries']:
        info=team.get('team') or {}
        abbr=str(info.get('abbreviation') or team.get('abbreviation') or '').upper()
        abbr=TEAMS.get(abbr,abbr)
        if not abbr: continue
        for entry in team.get('injuries') or []:
            athlete=entry.get('athlete') or {}
            name=athlete.get('displayName') or athlete.get('fullName')
            status=normalized_status(entry.get('status') or entry.get('type',{}).get('description'))
            if not name or not status: continue
            detail=entry.get('details') or {}
            if isinstance(detail,dict): detail=detail.get('detail') or detail.get('type') or detail.get('side') or ''
            result.append({'player':name,'team':abbr,'status':status,'detail':str(detail),
                           'source':'ESPN injury listing','sourceUrl':url})
    if len(result)>1500: raise ValueError('Unexpected injury volume')
    return result
def main():
    prior={}
    if OUT.exists():
        try: prior=json.loads(OUT.read_text())
        except (ValueError,OSError): pass
    now=dt.datetime.now(dt.timezone.utc).isoformat()
    output={}
    for sport,url in SOURCES.items():
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; PropLabs/1.0)','Accept':'application/json'})
            with urllib.request.urlopen(req,timeout=25) as response:
                payload=json.load(response)
            rows=parse(payload,sport,url)
            if not rows:
                raise ValueError('No individual designations returned; injury coverage cannot be verified')
            output[sport]={'verified':True,'updatedAt':now,'rows':rows,'sourceUrl':url,
                           'note':'ESPN injury listings, not official game-day starter confirmation. Missing entry does not mean healthy.'}
            print(f'{sport}: {len(rows)} ESPN injury designations')
        except Exception as exc:
            # Never label stale or failed source data current.
            output[sport]={'verified':False,'updatedAt':now,'rows':[],'sourceUrl':url,'note':str(exc)[:250]}
            print(f'{sport}: unavailable ({exc})')
    save_json(OUT,output)
if __name__=='__main__':main()
