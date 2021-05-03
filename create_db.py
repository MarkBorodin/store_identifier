import psycopg2


class DB(object):
    def open(self):
        hostname = '127.0.0.1'
        username = 'parsing_admin'
        password = 'parsing_adminparsing_admin'
        database = 'parsing'
        port = "5444"
        self.connection = psycopg2.connect(host=hostname, user=username, password=password, dbname=database, port=port)
        self.cur = self.connection.cursor()

    def close(self):
        self.cur.close()
        self.connection.close()

    def drop_table(self):
        self.cur.execute(
            """DROP TABLE Domains_and_subdomains"""
        )
        self.connection.commit()

    def create_tables(self):
        """create tables in the database if they are not contained"""

        self.cur.execute('''CREATE TABLE IF NOT EXISTS Domains_and_subdomains
                     (
                     id SERIAL,
                     DUNS integer,
                     Handelsregister_Nummer TEXT,
                     UID TEXT,
                     Internet_Adresse TEXT,
                     subdomains TEXT,
                     Rechtsform TEXT,
                     Filiale_Indikator TEXT,
                     Mitarbeiter integer,
                     Mitarbeiter_Gruppe TEXT,
                     is_shop boolean,
                     number_of_goods integer,
                     phone TEXT,
                     phone_main_page TEXT,
                     leader_phone_without_sitemap TEXT,
                     phones_all_pages TEXT,
                     leader_phone_sitemap TEXT,
                     leader_phone_from_team_sitemap TEXT,
                     email TEXT,
                     email_main_page TEXT,
                     leader_email_without_sitemap TEXT,
                     emails_all_pages TEXT,
                     leader_email_sitemap TEXT,
                     leader_email_from_team_sitemap TEXT
                     );''')

        self.connection.commit()


db = DB()
db.open()
db.create_tables()
db.close()
