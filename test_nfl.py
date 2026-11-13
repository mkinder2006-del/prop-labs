import datetime as dt
import unittest
from copy import deepcopy
from update_nfl import FIELDS, SEASON, build_players, validate_espn
from update_nfl_markets import match_nfl

class NFLTests(unittest.TestCase):
    def setUp(self):
        self.g={'espn':'123','away_team':'BUF','home_team':'MIA','away_score':'21','home_score':'14'}
        self.stats=[];self.snaps=[];self.roster={}
        for team in ['BUF','MIA']:
            for i in range(6):
                aid=team+str(i)
                self.roster[aid]={'gsis_id':aid,'full_name':aid}
                self.snaps.append({'pfr_player_id':aid,'offense_snaps':'12','position':'WR','team':team,'player':aid})
    def test_zero_output_appearances_are_included(self):
        players=build_players(self.g,[],self.snaps,self.roster)
        self.assertEqual(len(players),12)
        self.assertTrue(all(p['REC']==0 and p['REC_YDS']==0 for p in players))
    def test_zero_snaps_are_excluded(self):
        self.snaps.append({'pfr_player_id':'inactive','offense_snaps':'0','position':'WR','team':'BUF','player':'inactive'})
        self.assertEqual(len(build_players(self.g,[],self.snaps,self.roster)),12)
    def test_special_teams_only_appearance_counts(self):
        self.snaps[0]['offense_snaps']='0';self.snaps[0]['st_snaps']='5'
        players=build_players(self.g,[],self.snaps,self.roster)
        self.assertEqual(len(players),12)
        self.assertEqual(players[0]['totalSnaps'],5)
    def test_unmapped_player_stops_publication(self):
        del self.roster['BUF0']
        with self.assertRaises(ValueError):build_players(self.g,[],self.snaps,self.roster)
    def test_negative_yards_are_kept(self):
        row={'player_id':'BUF0','team':'BUF',**{v:'0' for v in FIELDS.values()}}
        row['rushing_yards']='-3';row['player_display_name']='Player'
        result=build_players(self.g,[row],self.snaps,self.roster)
        self.assertEqual(next(p for p in result if p['id']=='BUF0')['RUSH_YDS'],-3)
    def test_wrong_season_rejected(self):
        with self.assertRaises(ValueError): validate_espn({'header':{'id':'123','season':{'year':SEASON-1,'type':2}}},self.g,[])
    def test_nonfinal_rejected(self):
        s={'header':{'id':'123','season':{'year':SEASON,'type':2},'competitions':[{'status':{'type':{'completed':False}}}]}}
        with self.assertRaises(ValueError):validate_espn(s,self.g,[])
    def test_nfl_listing_and_recent_records(self):
        now=dt.datetime(2026,11,13,12,tzinfo=dt.timezone.utc)
        h={'testplayer':[{'player':'Test Player','team':'LAR','position':'QB','PASS_YDS':250} for _ in range(8)]}
        schedule=[{'date':'2026-11-15','time':'2026-11-15T21:00:00Z','away':'LAR','home':'SEA','match':'LAR @ SEA'}]
        m={'status':'active','strike_type':'greater','yes_sub_title':'Test Player: 200+','floor_strike':199.5,'event_ticker':'KXNFLPASSYDS-26NOV15LASEA','ticker':'test','close_time':'2026-11-16T03:00:00Z','open_time':'2026-11-13T00:00:00Z','yes_ask_dollars':'.75','yes_bid_dollars':'.70','yes_ask_size_fp':'20'}
        r=match_nfl(m,'PASS_YDS','Passing yards',h,schedule,now,[])
        self.assertTrue(r['shortlist']);self.assertEqual(r['games'],8);self.assertEqual(r['last10']['games'],8)
        self.assertIsNone(match_nfl(m,'PASS_YDS','Passing yards',h,schedule,now,['LAR']))
        m['event_ticker']='KXNFLPASSYDS-26NOV16LASEA'
        self.assertIsNone(match_nfl(m,'PASS_YDS','Passing yards',h,schedule,now,[]))

if __name__=='__main__':unittest.main()
