import re
import sys
import time
from concurrent.futures import TimeoutError

import pandas as pd
import psycopg2
import requests
from bs4 import BeautifulSoup
from pebble import ProcessPool
from selenium import webdriver
from url_normalize import url_normalize
from usp.tree import sitemap_tree_for_homepage


class DomainsAndSubdomains(object):

    def __init__(self, file):
        self.file = file
        self.domains = list()

    def get_domains(self):
        """get url and other data from file"""
        df = pd.read_excel(self.file, engine='openpyxl')
        self.domains = df.to_dict(orient='record')

    @staticmethod
    def clear_url(target):
        """tidy up url"""
        return re.sub('.*www\.', '', target, 1).split('/')[0].strip()

    @staticmethod
    def task_done(future):
        """this is needed to handle the timeout in multithreaded mode"""
        try:
            result = future.result()  # blocks until results are ready
        except TimeoutError as error:
            print("Function took longer than %d seconds" % error.args[1])
        except Exception as error:
            print("Function raised %s" % error)

    @staticmethod
    def normalize_urls_list(common_list):
        """tidy up the url list"""
        lst = []
        for dom in common_list:
            dom = dom.replace('www.', '').replace('http://', '').replace('https://', '')
            lst.append(url_normalize(dom))
        lst = list(set(lst))
        return lst

    @staticmethod
    def check_the_quantity_of_goods(common_list):
        """find the number of products (counting the number of keywords in the links found in the sitemap)"""
        counter = 0
        for link in common_list:
            tree = sitemap_tree_for_homepage(link)
            lst = [page.url for page in tree.all_pages()]
            words_for_goods = ['goods', 'product', 'produkt', 'commodity', 'ware', 'item',
                               'article', 'artikel', 'objekte', 'object']
            urls_list = str(lst)
            for word in words_for_goods:
                counter += urls_list.count(word)
        return counter

    def start(self):
        """start of the program"""
        self.get_domains()

        with ProcessPool(max_workers=5, max_tasks=10) as pool:
            for i in self.domains:
                future = pool.schedule(self.check_domain, args=[i], timeout=300)
                future.add_done_callback(self.task_done)

    def check_domain(self, item):
        """check subdomains and check if url is a store (by keywords)"""
        try:
            domain = item['Internet-Adresse']
            subdomains = []
            subdomains_list = list()
            domain_is_shop = False
            domain = str(domain)
            if domain != 'nan':

                target = self.clear_url(domain)

                req = requests.get("https://crt.sh/?q=%.{d}&output=json".format(d=target))

                if req.status_code != 200:
                    print("[X] Information not available!")

                else:

                    for (key, value) in enumerate(req.json()):
                        subdomains.append(value['name_value'])

                    subdomains = sorted(set(subdomains))

                    for subdomain in subdomains:
                        if 'shop' in subdomain or 'store' in subdomain:
                            domain_is_shop = True
                            if '\n' in subdomain:
                                s = subdomain.split(sep='\n')
                                for v in s:
                                    if 'shop' in v or 'store' in v:
                                        subdomains_list.append(url_normalize(v))
                                        print(f'subdomain_m: {v}')
                            else:
                                subdomains_list.append(url_normalize(subdomain))
                                print(f'subdomain_o: {subdomain}')

                if domain_is_shop is False:
                    if len(self.is_shop([domain])) > 0:
                        domain_is_shop = True
                    else:
                        domain_is_shop = False

                common_list = [link for link in subdomains_list]
                common_list.append(domain)
                common_list = self.normalize_urls_list(common_list)
                counter = self.check_the_quantity_of_goods(common_list)

                if counter > 0:
                    domain_is_shop = True

                self.open_db()
                self.cur.execute(
                    """INSERT INTO Domains_and_subdomains (DUNS, Handelsregister_Nummer, UID, Internet_Adresse,
                     subdomains, Rechtsform, Filiale_Indikator, Mitarbeiter, Mitarbeiter_Gruppe, is_shop, number_of_goods)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""", (
                        item['DUNS'],
                        item['Handelsregister-Nummer'],
                        item['UID'],
                        item['Internet-Adresse'],
                        str(subdomains_list),
                        item['Rechtsform'],
                        item['Filiale Indikator'],
                        item['Mitarbeiter'],
                        item['Mitarbeiter Gruppe'],
                        domain_is_shop,
                        counter
                    )
                )
                self.connection.commit()
                self.close_db()

            else:
                self.open_db()
                self.cur.execute(
                    """INSERT INTO Domains_and_subdomains (DUNS, Handelsregister_Nummer, UID, Internet_Adresse,
                     subdomains, Rechtsform, Filiale_Indikator, Mitarbeiter, Mitarbeiter_Gruppe, is_shop, number_of_goods)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""", (
                        item['DUNS'],
                        item['Handelsregister-Nummer'],
                        item['UID'],
                        item['Internet-Adresse'],
                        '',
                        item['Rechtsform'],
                        item['Filiale Indikator'],
                        item['Mitarbeiter'],
                        item['Mitarbeiter Gruppe'],
                        False,
                        0
                    )
                )
                self.connection.commit()
                self.close_db()

        except Exception as e:
            print(f'1: {e}')
            self.open_db()
            self.cur.execute(
                """INSERT INTO Domains_and_subdomains (DUNS, Handelsregister_Nummer, UID, Internet_Adresse,
                 subdomains, Rechtsform, Filiale_Indikator, Mitarbeiter, Mitarbeiter_Gruppe, is_shop, number_of_goods)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""", (
                    item['DUNS'],
                    item['Handelsregister-Nummer'],
                    item['UID'],
                    item['Internet-Adresse'],
                    '',
                    item['Rechtsform'],
                    item['Filiale Indikator'],
                    item['Mitarbeiter'],
                    item['Mitarbeiter Gruppe'],
                    False,
                    0
                )
            )
            self.connection.commit()
            self.close_db()

    @staticmethod
    def is_shop(subdomains_list):
        """check if url is a store (by keywords)"""
        try:
            shops = []
            chrome_options = webdriver.ChromeOptions()
            chrome_options.headless = True
            browser = webdriver.Chrome('chromedriver', chrome_options=chrome_options)
            for url in subdomains_list:
                browser.get(url)
                time.sleep(5)
                soup = str(BeautifulSoup(browser.page_source, 'lxml'))
                words = ['shop', 'Shop', 'SHOP', 'store', 'Store', 'STORE', 'pay', 'Pay', 'PAY', 'cart', 'Cart', 'CART',
                         'buy', 'Buy', 'BUY', 'franken', 'Franken', 'FRANKEN', 'CHF']
                for word in words:
                    if word in soup:
                        shops.append(url)
                    else:
                        pass
            browser.close()
            print(f'SHOPS FOUND: {shops}')
            return shops
        except Exception as e:
            print(f'2: {e}')
            return []

    def open_db(self):
        """open the database"""
        hostname = '127.0.0.1'
        username = 'parsing_admin'
        password = 'parsing_adminparsing_admin'
        database = 'parsing'
        port = "5444"
        self.connection = psycopg2.connect(  # noqa
            host=hostname,
            user=username,
            password=password,
            dbname=database,
            port=port)
        self.cur = self.connection.cursor()  # noqa

    def close_db(self):
        """close the database"""
        self.cur.close()
        self.connection.close()


if __name__ == '__main__':
    # get company in command line
    file = sys.argv[1]

    # create object
    obj = DomainsAndSubdomains(file)

    # get data
    obj.start()
