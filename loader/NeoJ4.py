from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable
import time

#https://www.datacamp.com/tutorial/neo4j-tutorial
class NeoJ4:
    CYPHER_BATCH = """
    UNWIND $batch AS row
    MERGE (a:Article {_id: row._id})
      ON CREATE SET a.title = row.title
      ON MATCH  SET a.title = coalesce(a.title, row.title)
    WITH a, row, exists((:Author)-[:AUTHORED]->(a)) AS alreadyDone
    CALL {
      WITH a, row, alreadyDone
      WITH a, row WHERE NOT alreadyDone
      UNWIND row.authors AS author
      MERGE (p:Author {_id: author._id}) ON CREATE SET p.name = author.name
      CREATE (p)-[:AUTHORED]->(a)
    }
    WITH a, row, alreadyDone
    CALL {
      WITH a, row, alreadyDone
      WITH a, row WHERE NOT alreadyDone
      UNWIND row.references AS refId
      MERGE (b:Article {_id: refId})
      CREATE (a)-[:CITES]->(b)
    }
    """

    def __init__(self, uri, user, password, max_retries=10, delay=5):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        for i in range(max_retries):
            try:
                self.driver.verify_connectivity()
                print("Connection successful!")
                return
            except Exception as e:
                print(f"Failed to connect to Neo4j: {e}")
                time.sleep(delay)

        raise Exception("Impossible de se connecter à Neo4j après plusieurs tentatives.")


    def connect_with_retry(self, max_retries=10, delay=5):
        for i in range(max_retries):
            try:
                self.db.create_constraints() 
                print("[INFO] Connecté à Neo4j avec succès.")
                return
            except ServiceUnavailable:
                print(f"[WARN] Neo4j non prêt (tentative {i+1}/{max_retries})...")
                time.sleep(delay)
        raise Exception("Impossible de se connecter à Neo4j après plusieurs tentatives.")

    def close(self):
        self.driver.close()

    def create_constraints(self):
        with self.driver.session() as session:
            session.run("CREATE CONSTRAINT article_id IF NOT EXISTS FOR (a:Article) REQUIRE a._id IS UNIQUE")
            session.run("CREATE CONSTRAINT author_id  IF NOT EXISTS FOR (p:Author)  REQUIRE p._id IS UNIQUE")
            print("[INFO] Contraintes d'unicité créées.")

    def insert_batch(self, batch):
        with self.driver.session() as session:
            session.run(self.CYPHER_BATCH, batch=batch)

    def print_statistics_push(self):
        with self.driver.session() as session:
            articles = session.run("MATCH (a:Article) RETURN count(a) AS n").single()['n']
            authors = session.run("MATCH (p:Author)  RETURN count(p) AS n").single()['n']
            cites = session.run("MATCH ()-[r:CITES]->() RETURN count(r) AS n").single()['n']
            authored = session.run("MATCH ()-[r:AUTHORED]->() RETURN count(r) AS n").single()['n']

            if self.articles != None :
                print(f"[COUNT] Articles={abs(self.articles - articles)} Authors={abs(self.authors - authors)} NODES={abs((self.articles - articles) + (self.authors - authors))}")
            else:
                print(f"[COUNT] Articles={articles} Authors={authors} NODES={articles + authors}")

            self.articles = articles;
            self.authors = authors
            self.cites = cites;
            self.authored = authored;


    def statistics(self, usePrint=True):
        with self.driver.session() as session:
            self.articles = session.run("MATCH (a:Article) RETURN count(a) AS n").single()['n']
            self.authors = session.run("MATCH (p:Author)  RETURN count(p) AS n").single()['n']
            self.cites = session.run("MATCH ()-[r:CITES]->() RETURN count(r) AS n").single()['n']
            self.authored = session.run("MATCH ()-[r:AUTHORED]->() RETURN count(r) AS n").single()['n']
            if usePrint:
                print(f"[COUNT] Articles={self.articles} Authors={self.authors} CITES={self.cites} AUTHORED={self.authored}")
