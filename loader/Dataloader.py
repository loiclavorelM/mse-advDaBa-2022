import json
import time
import requests


class DataLoader:
    def __init__(self, url, max_retries=10, backoff_base=10, request_timeout=60, resume_bytes=0):
        self.url = url
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.request_timeout = request_timeout
        self.resume_bytes = resume_bytes

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
        byte_offset = self.resume_bytes
        attempt = 0
        if byte_offset > 0:
            print(
                f"[STREAM] RESUME_BYTES={byte_offset} → on saute le début du fichier "
                f"(supposé déjà ingéré, MERGE protège quand même).",
                flush=True,
            )

        while True:
            try:
                headers = {}
                if byte_offset > 0:
                    headers['Range'] = f'bytes={byte_offset}-'
                    print(f"[STREAM] Reprise depuis l'octet {byte_offset}", flush=True)

                with requests.get(
                    self.url,
                    stream=True,
                    headers=headers,
                    timeout=self.request_timeout,
                ) as response:
                    if byte_offset > 0 and response.status_code == 200:
                        print(
                            "[WARN] Le serveur ne supporte pas Range. "
                            "Re-stream depuis le début (MERGE évitera les doublons).",
                            flush=True,
                        )
                        byte_offset = 0
                    response.raise_for_status()
                    attempt = 0

                    for line_bytes in response.iter_lines(decode_unicode=False):
                        if line_bytes is None:
                            continue
                        byte_offset += len(line_bytes) + 1

                        if not line_bytes.strip():
                            continue
                        try:
                            raw_data = json.loads(line_bytes.decode('utf-8'))
                        except (json.JSONDecodeError, UnicodeDecodeError):
                            continue
                        if raw_data.get('id'):
                            yield self.clean_article(raw_data)

                    print(f"[STREAM] Fini. Total octets lus: {byte_offset}", flush=True)
                    return

            except (
                requests.exceptions.ChunkedEncodingError,
                requests.exceptions.ConnectionError,
                requests.exceptions.ReadTimeout,
                requests.exceptions.HTTPError,
                ConnectionError,
            ) as e:
                attempt += 1
                if attempt > self.max_retries:
                    print(
                        f"[ERROR] Max retries ({self.max_retries}) atteint après "
                        f"{byte_offset} octets lus. Abandon.",
                        flush=True,
                    )
                    raise
                wait = min(self.backoff_base * (2 ** (attempt - 1)), 300)
                print(
                    f"[RETRY] Connexion perdue après {byte_offset} octets. "
                    f"Tentative {attempt}/{self.max_retries} dans {wait}s. "
                    f"Erreur: {type(e).__name__}: {e}",
                    flush=True,
                )
                time.sleep(wait)
