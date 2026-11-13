import datetime as dt
import unittest
from copy import deepcopy
from update_markets import match_market, history

class MarketTests(unittest.TestCase):
    def setUp(self):
        self.now=dt.datetime(2026,11,13,12,tzinfo=dt.timezone.utc)
        self.games=[{'player':'Test Player','team':'NYK','position':'G','PTS':20,'REB':5,'AST':4,'3PM':2} for _ in range(12)]
        self.hist={'testplayer':self.games}
        self.schedule=[{'date':'2026-11-13','away':'NYK','home':'IND','time':'2026-11-14T00:00:00Z','match':'NYK @ IND'}]
        self.market={'status':'active','strike_type':'greater','yes_sub_title':'Test Player: 15+','floor_strike':14.5,'event_ticker':'KXNBAPTS-26NOV13NYKIND','ticker':'test','close_time':'2026-11-14T03:00:00Z','open_time':'2026-11-13T00:00:00Z','yes_ask_dollars':'.75','yes_bid_dollars':'.70','yes_ask_size_fp':'20'}
    def match(self,m=None):
        return match_market(m or self.market,'PTS','Points',self.hist,self.schedule,self.now)
    def test_actual_line_and_recent_windows(self):
        self.games[-1]['PTS']=10
        r=self.match()
        self.assertEqual(r['hits'],11)
        self.assertEqual(r['last5']['hits'],4)
        self.assertEqual(r['last10']['hits'],9)
        self.assertEqual(r['last20']['games'],12)
        self.assertTrue(r['shortlist'])
    def test_wrong_game_or_date_never_matched(self):
        for event in ['KXNBAPTS-26NOV14NYKIND','KXNBAPTS-26NOV13INDNYK']:
            m=deepcopy(self.market);m['event_ticker']=event
            self.assertIsNone(self.match(m))
    def test_invalid_unavailable_and_nonstandard_markets(self):
        for key,value in [('status','settled'),('floor_strike',15),('yes_ask_dollars','NaN'),('yes_ask_size_fp','0'),('strike_type','between')]:
            m=deepcopy(self.market);m[key]=value
            self.assertIsNone(self.match(m),(key,value))
    def test_expensive_and_small_sample_not_shortlisted(self):
        self.market['yes_ask_dollars']='.95'
        self.assertFalse(self.match()['shortlist'])
        self.market['yes_ask_dollars']='.75';self.hist['testplayer']=self.games[:5]
        self.assertFalse(self.match()['shortlist'])
    def test_started_game_hidden(self):
        self.now=dt.datetime(2026,11,14,1,tzinfo=dt.timezone.utc)
        self.assertIsNone(self.match())

if __name__=='__main__': unittest.main()
