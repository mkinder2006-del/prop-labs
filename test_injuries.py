import unittest
import datetime as dt
NOW=dt.datetime.now(dt.timezone.utc).isoformat()
from update_injuries import parse,normalized_status

class InjuryParserTests(unittest.TestCase):
    def test_known_designations(self):
        self.assertEqual(normalized_status('OUT'),'Out')
        self.assertEqual(normalized_status('questionable'),'Questionable')
        self.assertIsNone(normalized_status('not-a-designation'))
    def test_parse_source_rows(self):
        data={'injuries':[{'team':{'abbreviation':'GS'},'injuries':[
            {'athlete':{'displayName':'Example Player'},'status':'Out','date':NOW,'details':{'type':'Ankle'}},
            {'athlete':{'displayName':'Unknown Player'},'status':'Unknown'}]}]}
        rows=parse(data,'NBA','https://example.com')
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['team'],'GSW')
        self.assertEqual(rows[0]['status'],'Out')
    def test_actual_espn_schema(self):
        data={'injuries':[{'id':'22','displayName':'Arizona Cardinals','injuries':[
            {'athlete':{'displayName':'Sample Receiver'},'status':'Questionable','date':NOW,'shortComment':'Hamstring'}]}]}
        rows=parse(data,'NFL','https://example.com',{'22':'ARI'})
        self.assertEqual(rows[0]['team'],'ARI')
        self.assertEqual(rows[0]['detail'],'Hamstring')
    def test_schema_fails_closed(self):
        with self.assertRaises(ValueError):
            parse({'injuries':{}},'NFL','https://example.com')

if __name__=='__main__':unittest.main()
