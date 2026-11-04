import unittest
from collect import collect, parse_event
SOURCE={'id':'acireale','name':'Comune di Acireale','calendar':'https://www.comune.acireale.ct.it/it/events','permissionUrl':'https://www.comune.acireale.ct.it/it/legal_notices'}
HTML='''<h1 data-element="event-title">Mostra</h1><div><p>Data inizio:</p><b>5 novembre 2026</b></div><div><p>Data fine:</p><b>8 novembre 2026</b></div><h1>19:30 - Inizio evento</h1><div class="paragraph"><div class="row"><a id="costo"></a></div><div>Gratuito</div></div><div class="card-place"><h1 class="card-title">Museo</h1><div class="card-text">Via Roma 1, Acireale</div></div>'''
class CollectorTests(unittest.TestCase):
    def test_event_dates(self):
        event=parse_event(HTML,SOURCE['calendar'],SOURCE)
        self.assertEqual(event['date'],'2026-11-05')
        self.assertEqual(event['endDate'],'2026-11-08')
        self.assertEqual(event['time'],'19:30')
    def test_free_and_attributed(self):
        event=parse_event(HTML,SOURCE['calendar'],SOURCE)
        self.assertEqual(event['price'],0)
        self.assertEqual(event['source'],'Comune di Acireale')
        self.assertEqual(event['license'],'CC BY 4.0')
    def test_unknown_price(self):
        self.assertIsNone(parse_event(HTML.replace('Gratuito','Biglietti in sede'),SOURCE['calendar'],SOURCE)['price'])
    def test_missing_date(self):
        self.assertIsNone(parse_event(HTML.replace('Data inizio:','Ultimo aggiornamento:'),SOURCE['calendar'],SOURCE))
    def test_missing_address(self):
        self.assertIsNone(parse_event(HTML.replace('class="card-text"','class="description"'),SOURCE['calendar'],SOURCE))
    def test_unconfirmed_license(self):
        calls=[]
        def getter(url):
            calls.append(url)
            return 'All rights reserved'
        events,statuses=collect([SOURCE],'2026-11-04',getter=getter,pause=lambda _:None)
        self.assertEqual(events,[])
        self.assertEqual(statuses[0]['status'],'error')
        self.assertEqual(calls,[SOURCE['permissionUrl']])
    def test_outage_preserves_current(self):
        previous=parse_event(HTML,SOURCE['calendar'],SOURCE)
        def fail(_): raise TimeoutError()
        events,statuses=collect([SOURCE],'2026-11-06',[previous],getter=fail)
        self.assertEqual(len(events),1)
        self.assertEqual(statuses[0]['status'],'error')
    def test_expired_removed(self):
        previous=parse_event(HTML,SOURCE['calendar'],SOURCE)
        def fail(_): raise TimeoutError()
        events,_=collect([SOURCE],'2026-11-09',[previous],getter=fail)
        self.assertEqual(events,[])
if __name__=='__main__': unittest.main()
