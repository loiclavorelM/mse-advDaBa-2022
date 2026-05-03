import os
import time
from datetime import datetime, timezone
from NeoJ4 import NeoJ4
from Dataloader import DataLoader

class App:    
    def __init__(self):
        self.neo4j_uri = os.environ.get('NEO4J_URI', 'bolt://localhost:7687')
        self.neo4j_user = os.environ.get('NEO4J_USER', 'neo4j')
        self.neo4j_password = os.environ.get('NEO4J_PASS', 'test')
        self.data_url = os.environ.get('DATA_URL', 'http://vmrum.isc.heia-fr.ch/files/DBLP-Citation-network-V18.jsonl')
        self.max_nodes = int(os.environ.get('MAX_NODES', '-1'))
        self.batch_size = int(os.environ.get('BATCH_SIZE', '500'))
        self.max_retries = int(os.environ.get('MAX_RETRIES', '10'))
        self.retry_backoff = int(os.environ.get('RETRY_BACKOFF', '10'))

        self.db = NeoJ4(self.neo4j_uri, self.neo4j_user, self.neo4j_password)
        self.loader = DataLoader(
            self.data_url,
            max_retries=self.max_retries,
            backoff_base=self.retry_backoff,
        )

    def run(self):
        print("-"*40)
        start = datetime.now(timezone.utc).isoformat()
        print(f"[START] {start} – Source: {self.data_url}")
        print(f"[CONFIG] MAX_NODES={self.max_nodes}, BATCH_SIZE={self.batch_size}")
        print("-"*40)
        
        start_time = time.time()
        articles_loaded = 0
        try:
            self.db.create_constraints()
            self.db.statistics()

            batch = []
            batches_inserted = 0
            for article in self.loader.stream_data():
                batch.append(article)
                articles_loaded += 1

                if articles_loaded >= self.max_nodes and self.max_nodes != -1:
                    break

                if len(batch) >= self.batch_size:
                    self.db.insert_batch(batch)
                    batches_inserted += 1
                    batch = []
                    elapsed = max(int(time.time() - start_time), 1)
                    rate = articles_loaded // elapsed
                    print(f"[BATCH #{batches_inserted}] {articles_loaded} articles | {elapsed}s écoulés | {rate} articles/s", flush=True)

                if articles_loaded % 100000 == 0 :
                    print(f"[PROGRESS] {articles_loaded} articles insérés... Temps écoulé: {int(time.time() - start_time)}s", flush=True)
        
                    
            if batch:
                self.db.insert_batch(batch)

 
        except Exception as e:
            print(f"\n[ERROR] Le chargement a été interrompu : {e}", flush=True)

        finally:
            duration = int(time.time() - start_time)
            print("-"*60)
            print(f"[Start] {start}")
            print(f"[END] {datetime.now(timezone.utc).isoformat()}")
            print(f"[DURATION] {duration} seconds")
            print("[SESSION RESULTS] Nodes processed during this run:")
            self.db.print_statistics_push()
            print("[DATABASE STATE] Overall nodes in Neo4j:", flush=True)
            self.db.statistics()
            print("-" * 60)
        
        self.db.close()

if __name__ == "__main__":
    app = App()
    app.run()