#!/usr/bin/env python3
"""ESPN depth-chart positional leaders; projections, NOT official game-day starting lineups."""
import datetime as dt
import json
import time
from update_data import save_json
from update_injuries import ROOT,SOURCES,fetch_json,fetch_teams,TEAMS

OUT=ROOT/'data'/'depthcharts.json'
NBA_POS={'pg','sg','sf','pf','c'}
NFL_POS={'qb','rb','hb','fb','wr','wr1','wr2','wr3','te','te1','te2','slot','swr'}
def parse_depthchart(payload,sport,team,source):
    if not isinstance(payload.get('depthchart'),list): raise ValueError('Missing depthchart array')
    rows=[]
    for chart in payload['depthchart']:
        if sport=='NFL' and not any(x in str(chart.get('name','')).lower() for x in ('offense','offensive','base 11','base 12','base 21')):
            continue
        for position,group in (chart.get('positions') or {}).items():
            position=position.lower()
            if position not in (NBA_POS if sport=='NBA' else NFL_POS):continue
            athletes=group.get('athletes') or []
            if not isinstance(athletes,list):continue
            seen=set()
            for idx,athlete in enumerate(athletes):
                name=athlete.get('displayName') or athlete.get('fullName')
                if not name or name in seen:continue
                seen.add(name)
                rows.append({'player':name,'team':team,'position':position.upper(),'rank':idx+1,
                             'sourceUrl':source})
    return rows
def main():
    now=dt.datetime.now(dt.timezone.utc).isoformat()
    output={}
    for sport,url in SOURCES.items():
        base=url.rsplit('/',1)[0]
        rows=[];errors=[]
        try:
            teams=fetch_teams(sport)
            for teamid,abbr in teams.items():
                source=base+'/teams/'+teamid+'/depthcharts'
                try:
                    payload=fetch_json(source)
                    parsed=parse_depthchart(payload,sport,TEAMS.get(abbr,abbr),source)
                    if not parsed: raise ValueError('No relevant positions')
                    rows.extend(parsed)
                except Exception as exc:
                    errors.append(f'{abbr}: {str(exc)[:80]}')
                time.sleep(0.45)
            # A partial team feed must not be described as league-wide verified.
            covered=len({x['team'] for x in rows})
            verified=covered>=min(10,len(teams))
            output[sport]={'verified':verified,'updatedAt':now,'rows':rows if verified else [],'coveredTeams':sorted({x['team'] for x in rows}),
                           'teamsCovered':covered,'teamsExpected':len(teams),'errors':errors[:8],
                           'note':'ESPN ordered depth-chart projection; first available listed player is not a confirmed game-day starter.'}
            print(f'{sport} depth charts: {covered}/{len(teams)} teams, {len(rows)} roles, verified={verified}',flush=True)
        except Exception as exc:
            output[sport]={'verified':False,'updatedAt':now,'rows':[],'errors':[str(exc)[:200]]}
            print(f'{sport} depth charts unavailable: {exc}',flush=True)
    save_json(OUT,output)
if __name__=='__main__':main()
