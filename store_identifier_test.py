import csv
import re
import time
from concurrent.futures import TimeoutError
import phonenumbers
import pandas as pd
import psycopg2
import requests
from bs4 import BeautifulSoup
from ordered_set import OrderedSet
from pebble import ProcessPool
from selenium import webdriver
from url_normalize import url_normalize
from usp.tree import sitemap_tree_for_homepage
from usp.web_client.requests_client import RequestsWebClient
from pyisemail import is_email


class _RequestsWebClient(RequestsWebClient):
    __USER_AGENT = 'Mozilla/5.0'


class DomainsAndSubdomains(object):
    words_for_shop = [
        'checkout', 'shopping cart', 'warenkorb', 'korb', 'basket'
    ]

    words_for_goods = [
        'goods', 'produ', 'commodity', 'ware', 'item', 'article', 'artikel', 'objekte', 'object',
        'dienstleistungen', 'services', 'service', 'bedienung', 'CHF', 'buy', 'franken', 'pay'
    ]

    words_for_company_leader = [
        'leader', 'head', 'chief', 'Leiter', 'Chef', 'Geschäftsführer', 'Geschäftsleitung', 'Gruppenleitung',
        'führer', 'Director', 'CEO', 'COO'
    ]

    words_for_company_team = [
        'team', 'staff', 'personnel', 'mitarbeiter', 'Ueber_uns', 'ber uns', 'ber_uns', 'ueber-uns', 'about us',
        'about_us', 'kontakt', 'contact', 'contatti', 'firma', 'corporate', 'company', 'impressum', 'agentur', 'buero'
    ]

    def __init__(self, file, mode='1', timeout=3600): # noqa
        self.file = file
        self.result_file = f'result_{self.file}'
        self.mode = mode
        self.domains = list()
        self.buffer = list()
        self.timeout = timeout
        self.headers = {'User-Agent': 'Mozilla/5.0'}

    def get_domains(self):
        """get url and other data from file"""

        # open and read the file
        df = pd.read_excel(self.file, engine='openpyxl')
        self.domains = df.to_dict(orient='record')

        # create output file
        columns = list(df.columns.values)
        columns.append('shop (Yes/No)')
        columns.append('number of products')
        columns.append('shop-domain')
        columns.append('phone')
        columns.append('phone_main_page')
        columns.append('leader_phone_without_sitemap')
        columns.append('phones_all_pages')
        columns.append('leader_phone_sitemap')
        columns.append('leader_phone_from_team_sitemap')
        columns.append('email')
        columns.append('email_main_page')
        columns.append('leader_email_without_sitemap')
        columns.append('emails_all_pages')
        columns.append('leader_email_sitemap')
        columns.append('leader_email_from_team_sitemap')

        # with csv lib
        with open(self.result_file, "w", newline="", encoding='UTF-8') as f:
            writer = csv.writer(f)
            writer.writerows([columns])

    @staticmethod
    def clear_url(target):
        """tidy up url"""
        return re.sub('.*www\.', '', target, 1).split('/')[0].strip() # noqa

    def normalize_urls_list(self, common_list):
        """tidy up the url list"""
        lst = []
        for dom in common_list:
            dom = dom.replace('www.', '').replace('http://', '').replace('https://', '')
            lst.append(url_normalize(dom))
        lst = list(set(lst))
        final_list = []
        for link in lst:
            try:
                req = requests.get(link, headers=self.headers)
                if req.status_code == 200:
                    final_list.append(link)
            except Exception as e:
                print(f'normalize_urls_list: {e}')
        return lst

    @staticmethod
    def get_sitemap_tree(common_list):
        """get all links from sitemap"""
        sitemap_tree = []
        for link in common_list:
            web_client = _RequestsWebClient()
            tree = sitemap_tree_for_homepage(link, web_client)
            for page in tree.all_pages():
                sitemap_tree.append(page.url)
        return sitemap_tree

    def find_phone_by_keyword(self, url, word):
        """looking for a phone number on the page by keyword"""
        phone_list = []
        try:
            html = requests.get(url, headers=self.headers).text
            soup = BeautifulSoup(html, 'lxml')
            phone = soup.find(text=re.compile(word)).parent  # TODO
            for match in phonenumbers.PhoneNumberMatcher(str(phone), "CH"):
                result = str(match).split(sep=') ', maxsplit=1)[1]
                if result:
                    phone_list.append(result)
            if not phone_list:
                for match in phonenumbers.PhoneNumberMatcher(
                        str(soup.find(text=re.compile(word)).parent.parent), "CH"):  # noqa
                    result = str(match).split(sep=') ', maxsplit=1)[1]
                    if result:
                        phone_list.append(result)
            return phone_list
        except Exception as e: # noqa
            return phone_list

    def find_email_by_keyword(self, url, word):
        """looking for a email on the page by keyword"""
        email_list = []
        try:
            html = requests.get(url, headers=self.headers).text
            soup = BeautifulSoup(html, 'lxml')
            tag = soup.find(text=re.compile(word)).parent # TODO
            email = tag.find(text=re.compile(r'[\w\.-]+@[\w\.-]+(\.[\w]+)+'))  # noqa
            if email is not None:
                email = email.strip()
                if self.check_email_valid(email) is True:
                    email_list.append(email)
                else:
                    result = email.split(sep=' ')
                    result = [word for word in result if '@' in word]
                    if self.check_email_valid(result[0]) is True:
                        email_list.append(result[0])
            if not email_list:
                tag = soup.find(text=re.compile(word)).parent.parent
                email = tag.find(text=re.compile(r'[\w\.-]+@[\w\.-]+(\.[\w]+)+'))  # noqa
                if email is not None:
                    email = email.strip()
                    if self.check_email_valid(email) is True:
                        email_list.append(email)
                    else:
                        result = email.split(sep=' ')
                        result = [word for word in result if '@' in word]
                        if self.check_email_valid(result[0]) is True:
                            email_list.append(result[0])
            return email_list
        except Exception as e: # noqa
            print(f'find_email_by_keyword: {e}')
            return email_list

    def get_leader_phone_and_email_from_sitemap(self, sitemap_tree):
        """looking for the phone number and the email of the head of the company"""
        leader_phone = []
        leader_email = []
        try:
            for url in sitemap_tree:
                for word in self.words_for_company_leader:
                    if word in url:
                        leader_phone.append(self.find_phone_by_keyword(url, word))
                        leader_email.append(self.find_email_by_keyword(url, word))
        except Exception as e: # noqa
            print(f'get_leader_phone_and_email_from_sitemap: {e}')
        phones = [j for i in leader_phone for j in i]
        phones = self.unique_phones(phones)
        emails = [j for i in leader_email for j in i]
        emails = self.unique_emails(emails)
        return phones, emails

    def get_leader_phone_and_email_from_sitemap_section_team(self, sitemap_tree):
        """looking for leader phone and email number in team section"""
        leader_phone_from_team = []
        leader_email_from_team = []
        try:
            for url in sitemap_tree:
                for word in self.words_for_company_team:
                    if word in url:
                        leader_phone_from_team.append(
                            self.find_phones(requests.get(url, headers=self.headers).text, leader=True)
                        )
                        leader_email_from_team.append(
                            self.find_emails(requests.get(url, headers=self.headers).text, leader=True)
                        )
        except Exception as e: # noqa
            print(f'get_leader_phone_and_email_from_sitemap_section_team: {e}')
        phones = [j for i in leader_phone_from_team for j in i]
        phones = self.unique_phones(phones)
        emails = [j for i in leader_email_from_team for j in i]
        emails = self.unique_emails(emails)
        return phones, emails

    def check_phones_emails_on_every_page_and_count_the_quantity_of_goods(self, sitemap_tree):
        """find the number of products (counting the number of keywords in the links found in the sitemap)
        and looking for phones, emails on each page"""
        counter = 0
        all_pages_phone = []
        all_pages_emails = []

        # 1 way: counting the number of products according to the sitemap links
        urls_list = str(sitemap_tree)

        if self.mode == '1':
            for word in self.words_for_goods:
                counter += urls_list.count(word)

        # 2 way: follow each link in sitemap and check keywords on each page
        # (if no goods were found in the way 1)
        # (using requests, since with selenium it will take much longer)
        if self.mode == '2':
            for word in self.words_for_goods:
                counter += urls_list.count(word)
            if counter == 0:
                counter, all_pages_phone, all_pages_emails = self.check_every_page(sitemap_tree)

        # 3 way: follow each link in sitemap and check keywords on each page (anyway)
        if self.mode == '3':
            counter, all_pages_phone, all_pages_emails = self.check_every_page(sitemap_tree)

        return counter, all_pages_phone, all_pages_emails

    def check_every_page(self, sitemap_tree):
        """check each page for product availability (by keywords)"""
        counter = 0
        phones = []
        emails = []
        for url in sitemap_tree:
            try:
                response = requests.get(url, headers=self.headers)
                text = response.text
                for word in self.words_for_goods:
                    counter += text.count(word)
                phones.append(self.find_phones(text, leader=True))
                emails.append(self.find_emails(text, leader=True))
            except Exception as e:
                print(f'check_every_page: {e}')
        phones = [j for i in phones for j in i]
        phones = self.unique_phones(phones)
        emails = [j for i in emails for j in i]
        emails = self.unique_emails(emails)
        return counter, phones, emails

    def find_phones(self, text, leader=False):
        """the method searches for phone numbers on the page"""
        phones = list()
        try:
            if leader is False:
                for match in phonenumbers.PhoneNumberMatcher(text, "CH"):
                    phone = str(match).split(sep=') ', maxsplit=1)[1]
                    if phone:
                        phones.append(phone)
            if leader is True:
                soup = BeautifulSoup(text, 'lxml')
                for word in self.words_for_company_leader:
                    if word in str(soup):
                        try:
                            for match in phonenumbers.PhoneNumberMatcher(str(soup.find(text=re.compile(word)).parent), "CH"):   # noqa  TODO
                                result = str(match).split(sep=') ', maxsplit=1)[1]
                                if result:
                                    phones.append(result)
                        except Exception:  # noqa
                            continue
                if not phones:  # noqa
                    for word in self.words_for_company_leader:
                        if word in str(soup):
                            try:
                                for match in phonenumbers.PhoneNumberMatcher(str(soup.find(text=re.compile(word)).parent.parent), "CH"):  # noqa  TODO
                                    result = str(match).split(sep=') ', maxsplit=1)[1]
                                    if result:
                                        phones.append(result)
                            except Exception:  # noqa
                                continue
            phones = self.unique_phones(phones)
        except Exception as e:
            print(f'find_phones: {e}')
        return phones

    def find_emails(self, text, leader=False):
        """the method searches for email on the page"""
        emails = list()
        try:
            soup = BeautifulSoup(text, 'lxml')
            if leader is False:
                results = soup.findAll(text=re.compile(r'[\w\.-]+@[\w\.-]+(\.[\w]+)+'))  # noqa
                for email in results:
                    if email is not None:
                        email = email.strip()
                        if self.check_email_valid(email) is True:
                            emails.append(email)
                        else:
                            result = email.split(sep=' ')
                            result = [word for word in result if '@' in word]
                            if self.check_email_valid(result[0]) is True:
                                emails.append(result[0])
            if leader is True:
                for word in self.words_for_company_leader:
                    if word in str(soup):
                        try:
                            tag = soup.find(text=re.compile(word)).parent    # TODO
                            email = tag.find(text=re.compile(r'[\w\.-]+@[\w\.-]+(\.[\w]+)+'))   # noqa
                            if email is not None:
                                email = email.strip()
                                if self.check_email_valid(email) is True:
                                    emails.append(email)
                                else:
                                    result = email.split(sep=' ')
                                    result = [word for word in result if '@' in word]
                                    if self.check_email_valid(result[0]) is True:
                                        emails.append(result[0])
                        except Exception: # noqa
                            continue
                if not emails:
                    for word in self.words_for_company_leader:
                        if word in str(soup):
                            try:
                                tag = soup.find(text=re.compile(word)).parent.parent  # TODO
                                email = tag.find(text=re.compile(r'[\w\.-]+@[\w\.-]+(\.[\w]+)+'))  # noqa
                                if email is not None:
                                    email = email.strip()
                                    if self.check_email_valid(email) is True:
                                        emails.append(email)
                                    else:
                                        result = email.split(sep=' ')
                                        result = [word for word in result if '@' in word]
                                        if self.check_email_valid(result[0]) is True:
                                            emails.append(result[0])
                            except Exception:  # noqa
                                continue
            emails = self.unique_emails(emails) # noqa
            return emails
        except Exception as e:
            print(f'find_emails: {e}')
            return emails

    def task_done(self, future):
        """this is needed to handle the timeout in multithreaded mode""" # noqa
        try:
            result = future.result()  # noqa (blocks until results are ready)
        except TimeoutError as error:
            self.buffer.append(future.item)
            print("Function took longer than %d seconds" % error.args[1])
        except Exception as error:
            self.buffer.append(future.item)
            print("Function raised %s" % error)

    def start(self):
        """start of the program"""
        # get domains from file
        self.get_domains()

        # create a pool for multi-threaded processing
        with ProcessPool(max_workers=5, max_tasks=10) as pool:
            for i in self.domains:
                future = pool.schedule(self.check_domain, args=[i], timeout=self.timeout)
                future.item = i
                future.add_done_callback(self.task_done)

        # add objects to the database with which a connection could not be established
        try:
            self.run_buffer()
        except Exception as e:
            print(f'run_buffer error: {e}')

    def run_buffer(self):
        """add objects to the database with which a connection could not be established"""
        for item in self.buffer:
            main_page_phone = ''
            all_pages_phone = ''
            leader_phone = ''
            leader_phone_from_team = ''
            main_page_email = ''
            all_pages_email = ''
            leader_email = ''
            leader_email_from_team = ''
            domain = str(item['Internet-Adresse']) # noqa
            is_shop = False
            leader_phone_without_sitemap = ''
            leader_email_without_sitemap = ''

            if 'shop' in domain or 'store' in domain:
                is_shop = True

            try:
                is_shop, main_page_phone, main_page_email, phone, email = self.is_shop_and_main_page(domain, is_shop)
                leader_phone_without_sitemap = phone
                leader_email_without_sitemap = email
            except Exception as e:
                is_shop = False
                print(f'start: {e}')

            phone, leader_phone_without_sitemap, leader_phone, leader_phone_from_team, main_page_phone,\
                all_pages_phone = self.phone(
                    leader_phone_without_sitemap=leader_phone_without_sitemap, leader_phone=leader_phone,
                    leader_phone_from_team=leader_phone_from_team,
                    main_page_phone=main_page_phone, all_pages_phone=all_pages_phone
                )

            email, leader_email_without_sitemap, leader_email, leader_email_from_team, main_page_email,\
                all_pages_email = self.email(
                    leader_email_without_sitemap=leader_email_without_sitemap, leader_email=leader_email,
                    leader_email_from_team=leader_email_from_team,
                    main_page_email=main_page_email, all_pages_email=all_pages_email
                )

            self.write_to_file(
                item, is_shop=is_shop, number_of_goods=0, shop_domain='', phone=phone, main_page_phone=main_page_phone,
                leader_phone_without_sitemap=leader_phone_without_sitemap,
                all_pages_phone=all_pages_phone, leader_phone=leader_phone,
                leader_phone_from_team=leader_phone_from_team, email=email,
                leader_email_without_sitemap=leader_email_without_sitemap, leader_email=leader_email,
                leader_email_from_team=leader_email_from_team, main_page_email=main_page_email,
                all_pages_email=all_pages_email
            )
            self.open_db()
            self.cur.execute(
                """INSERT INTO Domains_and_subdomains (
                     DUNS, Handelsregister_Nummer, UID, Internet_Adresse, subdomains, Rechtsform, Filiale_Indikator,
                     Mitarbeiter, Mitarbeiter_Gruppe, is_shop, number_of_goods, phone, phone_main_page,
                     leader_phone_without_sitemap, phones_all_pages, leader_phone_sitemap, 
                     leader_phone_from_team_sitemap, email, email_main_page, leader_email_without_sitemap,  
                     emails_all_pages, leader_email_sitemap, leader_email_from_team_sitemap
                     )
                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""", (   # noqa
                    item['DUNS'],
                    item['Handelsregister-Nummer'],
                    item['UID'],
                    item['Internet-Adresse'],
                    '',
                    item['Rechtsform'],
                    item['Filiale Indikator'],
                    item['Mitarbeiter'],
                    item['Mitarbeiter Gruppe'],
                    is_shop,
                    0,
                    str(phone),
                    str(main_page_phone),
                    str(leader_phone_without_sitemap),
                    str(all_pages_phone),
                    str(leader_phone),
                    str(leader_phone_from_team),
                    str(email),
                    str(main_page_email),
                    str(leader_email_without_sitemap),
                    str(all_pages_email),
                    str(leader_email),
                    str(leader_email_from_team)
                )
            )
            self.connection.commit()
            self.close_db()

    def check_domain(self, item):
        """check subdomains and check if url is a store (by keywords)"""
        counter = 0
        leader_phone = ''
        leader_phone_from_team = ''
        all_pages_phone = ''
        main_page_phone = ''
        phone = ''
        leader_email = ''
        leader_email_from_team = ''
        all_pages_email = ''
        main_page_email = ''
        email = ''
        leader_phone_without_sitemap = ''
        leader_email_without_sitemap = ''

        try:
            domain = item['Internet-Adresse']
            subdomains = []
            subdomains_list = list()
            domain_is_shop = False
            domain = str(domain)
            if domain != 'nan':

                # take a domain
                target = self.clear_url(domain)

                # make a request to an external service
                req = requests.get("https://crt.sh/?q=%.{d}&output=json".format(d=target), headers=self.headers)

                if req.status_code != 200:
                    print("[X] Information not available!")

                else:
                    for (key, value) in enumerate(req.json()):
                        subdomains.append(value['name_value'])

                    subdomains = sorted(set(subdomains))

                    # select the required subdomains
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

                is_shop, main_page_phone, main_page_email, phone, email = self.is_shop_and_main_page(domain, domain_is_shop)   # noqa
                leader_phone_without_sitemap = phone
                leader_email_without_sitemap = email

                if is_shop is True:
                    domain_is_shop = True

                if domain_is_shop is True:
                    # check the quantity of goods
                    common_list = [link for link in subdomains_list]
                    subdomains_list = self.normalize_urls_list(common_list)
                    common_list.append(domain)
                    common_list = self.normalize_urls_list(common_list)
                    sitemap_tree = self.get_sitemap_tree(common_list)
                    if sitemap_tree:
                        leader_phone, leader_email = self.get_leader_phone_and_email_from_sitemap(sitemap_tree)
                        leader_phone_from_team, leader_email_from_team = \
                            self.get_leader_phone_and_email_from_sitemap_section_team(sitemap_tree)
                        counter, all_pages_phone, all_pages_email = \
                            self.check_phones_emails_on_every_page_and_count_the_quantity_of_goods(sitemap_tree)
                    else:
                        pass

                phone, leader_phone_without_sitemap, leader_phone, leader_phone_from_team, main_page_phone,\
                    all_pages_phone = self.phone(
                        leader_phone_without_sitemap=leader_phone_without_sitemap, leader_phone=leader_phone,
                        leader_phone_from_team=leader_phone_from_team,
                        main_page_phone=main_page_phone, all_pages_phone=all_pages_phone
                    )

                email, leader_email_without_sitemap, leader_email, leader_email_from_team, main_page_email,\
                    all_pages_email = self.email(
                        leader_email_without_sitemap=leader_email_without_sitemap, leader_email=leader_email,
                        leader_email_from_team=leader_email_from_team,
                        main_page_email=main_page_email, all_pages_email=all_pages_email
                    )

                self.write_to_file(
                    item, is_shop=domain_is_shop, number_of_goods=counter, shop_domain=subdomains_list, phone=phone,
                    main_page_phone=main_page_phone,
                    leader_phone_without_sitemap=leader_phone_without_sitemap,
                    all_pages_phone=all_pages_phone, leader_phone=leader_phone,
                    leader_phone_from_team=leader_phone_from_team, email=email,
                    leader_email_without_sitemap=leader_email_without_sitemap, leader_email=leader_email,
                    leader_email_from_team=leader_email_from_team, main_page_email=main_page_email,
                    all_pages_email=all_pages_email
                )

                self.open_db()
                self.cur.execute(
                    """INSERT INTO Domains_and_subdomains (
                     DUNS, Handelsregister_Nummer, UID, Internet_Adresse, subdomains, Rechtsform, Filiale_Indikator,
                     Mitarbeiter, Mitarbeiter_Gruppe, is_shop, number_of_goods, phone, phone_main_page,
                     leader_phone_without_sitemap, phones_all_pages, leader_phone_sitemap, 
                     leader_phone_from_team_sitemap, email, email_main_page, leader_email_without_sitemap,  
                     emails_all_pages, leader_email_sitemap, leader_email_from_team_sitemap
                     )
                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""", (   # noqa
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
                        counter,
                        str(phone),
                        str(main_page_phone),
                        str(leader_phone_without_sitemap),
                        str(all_pages_phone),
                        str(leader_phone),
                        str(leader_phone_from_team),
                        str(email),
                        str(main_page_email),
                        str(leader_email_without_sitemap),
                        str(all_pages_email),
                        str(leader_email),
                        str(leader_email_from_team)
                    )
                )
                self.connection.commit()
                self.close_db()

            else:
                self.write_to_file(
                    item, is_shop=False, number_of_goods=0, shop_domain='', phone=phone,
                    main_page_phone=main_page_phone,
                    leader_phone_without_sitemap=leader_phone_without_sitemap,
                    all_pages_phone=all_pages_phone, leader_phone=leader_phone,
                    leader_phone_from_team=leader_phone_from_team, email=email,
                    leader_email_without_sitemap=leader_email_without_sitemap, leader_email=leader_email,
                    leader_email_from_team=leader_email_from_team, main_page_email=main_page_email,
                    all_pages_email=all_pages_email
                )
                self.open_db()
                self.cur.execute(
                    """INSERT INTO Domains_and_subdomains (
                     DUNS, Handelsregister_Nummer, UID, Internet_Adresse, subdomains, Rechtsform, Filiale_Indikator,
                     Mitarbeiter, Mitarbeiter_Gruppe, is_shop, number_of_goods, phone, phone_main_page,
                     leader_phone_without_sitemap, phones_all_pages, leader_phone_sitemap, 
                     leader_phone_from_team_sitemap, email, email_main_page, leader_email_without_sitemap,  
                     emails_all_pages, leader_email_sitemap, leader_email_from_team_sitemap
                     )
                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""", (  # noqa
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
                        0,
                        '',
                        '',
                        '',
                        '',
                        '',
                        '',
                        '',
                        '',
                        '',
                        '',
                        '',
                        ''
                    )
                )
                self.connection.commit()
                self.close_db()

        except Exception as e:
            print(f'check_domain: {e}')
            self.write_to_file(
                item, is_shop=False, number_of_goods=0, shop_domain='', phone=phone, main_page_phone=main_page_phone,
                leader_phone_without_sitemap=leader_phone_without_sitemap,
                all_pages_phone=all_pages_phone, leader_phone=leader_phone,
                leader_phone_from_team=leader_phone_from_team, email=email,
                leader_email_without_sitemap=leader_email_without_sitemap, leader_email=leader_email,
                leader_email_from_team=leader_email_from_team, main_page_email=main_page_email,
                all_pages_email=all_pages_email
            )
            self.open_db()
            self.cur.execute(
                """INSERT INTO Domains_and_subdomains (
                     DUNS, Handelsregister_Nummer, UID, Internet_Adresse, subdomains, Rechtsform, Filiale_Indikator,
                     Mitarbeiter, Mitarbeiter_Gruppe, is_shop, number_of_goods, phone, phone_main_page,
                     leader_phone_without_sitemap, phones_all_pages, leader_phone_sitemap, 
                     leader_phone_from_team_sitemap, email, email_main_page, leader_email_without_sitemap,  
                     emails_all_pages, leader_email_sitemap, leader_email_from_team_sitemap
                     )
                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""", (   # noqa
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
                    0,
                    '',
                    '',
                    '',
                    '',
                    '',
                    '',
                    '',
                    '',
                    '',
                    '',
                    '',
                    ''
                )
            )
            self.connection.commit()
            self.close_db()

    def is_shop_and_main_page(self, domain, domain_is_shop):
        """check if url is a store (by keywords)"""
        shop = False
        main_page_phone = []
        main_page_email = []
        phone = []
        email = []
        try:
            shops = []
            chrome_options = webdriver.ChromeOptions()
            chrome_options.headless = True
            browser = webdriver.Chrome('chromedriver', chrome_options=chrome_options)
            browser.get(domain)
            time.sleep(5)
            html = browser.page_source
            # is shop
            soup = str(BeautifulSoup(html, 'lxml'))
            for word in self.words_for_shop:
                if word in soup:
                    shops.append(domain)
                else:
                    pass

            # main_page_phone
            try:
                main_page_phone = self.find_phones(html)
            except Exception as e:
                main_page_phone = ''
                print(f'is_shop_and_main_page (phones error): {e}')

            # main_page_email
            try:
                main_page_email = self.find_emails(html)
            except Exception as e:
                main_page_email = ''
                print(f'is_shop_and_main_page (emails error): {e}')

            browser.close()

            if len(shops) > 0 or domain_is_shop is True:
                shop = True

                # phone_and_email_from_contacts
                try:
                    contact_links_from_main_page = self.contact(html, domain)
                    print(f'contact_links_from_main_page {contact_links_from_main_page}')
                except Exception as e:
                    contact_links_from_main_page = ''
                    print(f'is_shop_and_main_page (contacts error): {e}')

                try:
                    for link in contact_links_from_main_page:
                        response = requests.get(link, headers=self.headers)
                        text = response.text
                        phone.append(self.find_phones(text, leader=True)) # noqa
                except Exception as e:
                    print(f'is_shop_and_main_page (phone error): {e}')

                try:
                    for link in contact_links_from_main_page:
                        response = requests.get(link, headers=self.headers)
                        text = response.text
                        email.append(self.find_emails(text, leader=True))
                except Exception as e:
                    print(f'is_shop_and_main_page (email error): {e}')
            else:
                shop = False
                main_page_phone = []
                main_page_email = []
                phone = []
                email = []

            phone = self.unique_phones([j for i in phone for j in i])
            email = self.unique_emails([j for i in email for j in i])
            return shop, main_page_phone, main_page_email, phone, email

        except Exception as e:
            print(f'is_shop: {e}')
            return shop, main_page_phone, main_page_email, phone, email

    def contact(self, text, url):
        """looking for a section with contacts on the main page"""
        urls_list = []
        try:
            soup = BeautifulSoup(text, 'lxml')
            links = [[link.get('href'), link] for link in soup.findAll('a')]
            for result in links:
                link = result[0]
                tag_text = str(result[1].text).lower()
                for word in self.words_for_company_team:
                    if link is not None and (word in link or word in tag_text):
                        try:
                            if requests.get(url + '/' + link).status_code == 200:
                                urls_list.append(url + '/' + link)
                        except:  # noqa
                            pass
                        try:
                            if requests.get(url + link).status_code == 200:
                                urls_list.append(url + link)
                        except:  # noqa
                            pass
                        try:
                            if requests.get(link).status_code == 200:
                                urls_list.append(link)
                        except:  # noqa
                            pass
        except Exception: # noqa
            pass
        return urls_list

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

    @staticmethod
    def unique_phones(lst):
        """remove duplicate phones"""
        phones = []
        for ph in lst:
            phone = ph.replace(
                ' ', '').replace('+', '').replace('(', '').replace(')', '').replace('-', '').replace('.', '').replace('/', '') # noqa
            phones.append(phone)
        set_lst = list(set(phones))
        return set_lst

    @staticmethod
    def unique_emails(lst):
        """remove duplicate emails"""
        set_lst = list(OrderedSet(lst))
        return set_lst

    def write_to_file(
            self, item, is_shop, number_of_goods, shop_domain,
            phone, leader_phone_without_sitemap, main_page_phone, all_pages_phone, leader_phone, leader_phone_from_team,
            email, leader_email_without_sitemap, main_page_email, all_pages_email, leader_email, leader_email_from_team
    ):
        """write data to file"""
        lst = list(item.values())
        lst.append(is_shop)
        lst.append(number_of_goods)
        lst.append(shop_domain)
        lst.append(phone)
        lst.append(main_page_phone)
        lst.append(leader_phone_without_sitemap)
        lst.append(all_pages_phone)
        lst.append(leader_phone)
        lst.append(leader_phone_from_team)
        lst.append(email)
        lst.append(main_page_email)
        lst.append(leader_email_without_sitemap)
        lst.append(all_pages_email)
        lst.append(leader_email)
        lst.append(leader_email_from_team)

        # with csv lib
        with open(self.result_file, "a", newline="", encoding='UTF-8') as f:
            writer = csv.writer(f)
            writer.writerows([lst])

    @staticmethod
    def phone(leader_phone_without_sitemap, leader_phone, leader_phone_from_team, all_pages_phone, main_page_phone):
        """choose only one phone"""
        phone = ''
        if not leader_phone_without_sitemap:
            leader_phone_without_sitemap = ''
        else:
            try:
                leader_phone_without_sitemap = leader_phone_without_sitemap[0]
                phone = leader_phone_without_sitemap
            except Exception as e: # noqa
                print(f'phone: phone error: {e}')

        if not leader_phone:
            leader_phone = ''
        else:
            try:
                leader_phone = leader_phone[0]
                if not leader_phone_without_sitemap:
                    phone = leader_phone
            except Exception as e: # noqa
                print(f'phone: leader_phone error: {e}')

        if not leader_phone_from_team:
            leader_phone_from_team = ''
        else:
            try:
                leader_phone_from_team = leader_phone_from_team[0]
                if not leader_phone_without_sitemap and not leader_phone:
                    phone = leader_phone_from_team
            except Exception as e: # noqa
                print(f'phone: leader_phone_from_team error: {e}')

        if not all_pages_phone:
            all_pages_phone = ''
        else:
            try:
                all_pages_phone = all_pages_phone[0]
                if not leader_phone_without_sitemap and not leader_phone and not leader_phone_from_team:
                    phone = all_pages_phone
            except Exception as e: # noqa
                print(f'phone: all_pages_phone error: {e}')

        if not main_page_phone:
            main_page_phone = ''
        else:
            try:
                new_list = [e for e in main_page_phone if e]
                main_page_phone = new_list[0] if type(new_list[0]) is not list else new_list[0][0]
                if not leader_phone_without_sitemap and not leader_phone and not leader_phone_from_team and not all_pages_phone:   # noqa
                    phone = main_page_phone
            except Exception as e: # noqa
                print(f'phone: main_page_phone error: {e}')

        return phone, leader_phone_without_sitemap, leader_phone, leader_phone_from_team, main_page_phone,\
            all_pages_phone

    @staticmethod
    def email(leader_email_without_sitemap, leader_email, leader_email_from_team, all_pages_email, main_page_email):
        """choose only one email"""
        email = ''
        if not leader_email_without_sitemap:
            leader_email_without_sitemap = ''
        else:
            try:
                leader_email_without_sitemap = leader_email_without_sitemap[0]
                email = leader_email_without_sitemap
            except Exception as e: # noqa
                print(f'email: email error: {e}')

        if not leader_email:
            leader_email = ''
        else:
            try:
                leader_email = leader_email[0]
                if not leader_email_without_sitemap:
                    email = leader_email
            except Exception as e: # noqa
                print(f'email: leader_email error: {e}')

        if not leader_email_from_team:
            leader_email_from_team = ''
        else:
            try:
                leader_email_from_team = leader_email_from_team[0]
                if not leader_email_without_sitemap and not leader_email:
                    email = leader_email_from_team
            except Exception as e: # noqa
                print(f'email: leader_email_from_team error: {e}')

        if not all_pages_email:
            all_pages_email = ''
        else:
            try:
                all_pages_email = all_pages_email[0]
                if not leader_email_without_sitemap and not leader_email and not leader_email_from_team:
                    email = all_pages_email
            except Exception as e: # noqa
                print(f'email: all_pages_email error: {e}')

        if not main_page_email:
            main_page_email = ''
        else:
            try:
                new_list = [e for e in main_page_email if e]
                main_page_email = new_list[0] if type(new_list[0]) is not list else new_list[0][0]
                if not leader_email_without_sitemap and not leader_email and not leader_email_from_team and not all_pages_email:   # noqa
                    email = main_page_email
            except Exception as e: # noqa
                print(f'email: all_pages_email error: {e}')

        return email, leader_email_without_sitemap, leader_email, leader_email_from_team, main_page_email,\
            all_pages_email

    @staticmethod
    def check_email_valid(email):
        """check email validity"""
        bool_result = is_email(email)
        return bool_result


if __name__ == '__main__':
    """
        you need to insert the file name, select mode (1, 2 or 3), specify timeout (in seconds))
        for example:
        python store_identifier.py "example.xlsx" 3 360
        Mods:
        1. counting the number of products according to the sitemap links
        2. follow each link in sitemap and check keywords on each page (if no goods were found in the way 1) 
        (using requests, since with selenium it will take much longer)
        3. follow each link in sitemap and check keywords on each page (anyway)
    """

    # get file name
    # file = sys.argv[1]
    # select mode
    # mode = sys.argv[2]
    # specify timeout
    # timeout = int(sys.argv[3])

    file = 'Batch-Company-Adresses_test.xlsx'
    mode = '1'
    timeout = 300

    # create object
    obj = DomainsAndSubdomains(file=file, mode=mode, timeout=timeout)

    # get data
    obj.start()
