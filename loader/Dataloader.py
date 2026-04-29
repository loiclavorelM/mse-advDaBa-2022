import json
import requests

class DataLoader:    
    def __init__(self, url):
        self.url = url

    def clean_article(self, raw_data):
        return {
            '_id': raw_data.get('id'),
            'title': raw_data.get('title'),
            'authors': [
                {'_id': a['id'], 'name': a.get('name')}
                for a in (raw_data.get('authors') or []) if a.get('id')
            ],
            'references': [
                r for r in (raw_data.get('references') or []) if isinstance(r, str)
            ]
        }

    def stream_data(self):
        with requests.get(self.url, stream=True) as response:
            response.raise_for_status()
            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                try:
                    raw_data = json.loads(line)
                    if raw_data.get('id'):
                        yield self.clean_article(raw_data)
                except json.JSONDecodeError:
                    continue
