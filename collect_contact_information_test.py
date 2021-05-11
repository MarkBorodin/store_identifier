import csv
import os
import re
import time
from concurrent.futures import TimeoutError

import pandas as pd
import phonenumbers
import requests
from bs4 import BeautifulSoup
from names_dataset import NameDataset
from ordered_set import OrderedSet
from pebble import ProcessPool
from pyisemail import is_email
from selenium import webdriver
from usp.tree import sitemap_tree_for_homepage
from usp.web_client.requests_client import RequestsWebClient

from utils import check_email_accessible

dataset = NameDataset()


class TimeoutException(Exception):
    pass


class _RequestsWebClient(RequestsWebClient):
    __USER_AGENT = 'Mozilla/5.0'


class LeadGeneration(object):

    words_for_company_leader = [
        'leader', 'head', 'chief', 'Leiter', 'Chef', 'Geschäftsführer', 'Geschäftsleitung', 'Gruppenleitung',
        'führer', 'Director', 'CEO', 'COO'
    ]

    words_for_company_team = [
        'team', 'staff', 'personnel', 'mitarbeiter', 'Ueber_uns', 'ber uns', 'ber_uns', 'ueber-uns', 'about us',
        'about_us', 'kontakt', 'contact', 'contatti', 'firma', 'corporate', 'company', 'impressum', 'agentur', 'buero'
    ]

    def __init__(self, website: str, all_pages: int = 0) -> None:
        self.website = website
        self.result_file = 'results.xlsx'
        self.headers = {'User-Agent': 'Mozilla/5.0'}
        self.all_pages = all_pages

    def start(self) -> None:
        """run program"""
        self.get_or_create_results_file()
        self.check_domain()

    def check_domain(self) -> None:
        """check domain"""
        name_leader = list()
        phone_leader = list()
        email_leader = list()
        main_page_phone = list()
        main_page_email = list()
        sitemap_leader_phone = list()
        sitemap_leader_phone_from_team = list()
        all_pages_leader_phone = list()
        sitemap_leader_email = list()
        sitemap_leader_email_from_team = list()
        all_pages_leader_email = list()

        text_from_phone = list()
        text_from_email = list()

        text_sitemap_leader_phone_from_team = list()
        text_sitemap_leader_email_from_team = list()

        try:

            # get main page html
            main_page_html = self.get_html_with_selenium(self.website)

            try:
                # get data from main page
                main_page_phone, _ = self.find_phones(main_page_html)
                main_page_email, _ = self.find_emails(main_page_html)
            except Exception as e:
                print(f'get data from main page: {e}')

            try:
                # get all contacts htmls from main page html
                contacts_htmls = self.get_contacts_html(main_page_html)

                # get data from each contact html
                if contacts_htmls:
                    for html in contacts_htmls:

                        phones, phone_text = self.find_phones(html, leader=True)
                        phone_leader.append(phones)
                        text_from_phone.append(phone_text)

                        # if we didn’t find the phone number on the main page:
                        if not main_page_phone:
                            phone_m, _ = self.find_phones(html)
                            for phone in phone_m:
                                main_page_phone.append(phone)

                        emails, email_text = self.find_emails(html, leader=True)
                        email_leader.append(emails)
                        text_from_email.append(email_text)

                        # if we didn’t find the email number on the main page:
                        if not main_page_email:
                            email_m, _ = self.find_emails(html)
                            for email in email_m:
                                main_page_email.append(email)

                    # get unique main page phones and emails
                    main_page_phone = self.unique_phones(main_page_phone)
                    main_page_email = self.unique(main_page_email)

                    # unpacking phones and get unique
                    text_from_phone = [j for i in text_from_phone for j in i]
                    text_from_phone = self.unique([i for i in text_from_phone if i])
                    phone_leader = self.unique_phones([j for i in phone_leader for j in i])

                    # get one phone
                    try:
                        phone_leader = phone_leader[0] if phone_leader[0] else ''
                    except IndexError:
                        pass

                    # unpacking emails and get unique
                    text_from_email = [j for i in text_from_email for j in i]
                    text_from_email = self.unique([i for i in text_from_email if i])
                    email_leader = self.unique([j for i in email_leader for j in i])

                    # get one email
                    # try:
                    #     email_leader = email_leader[0] if email_leader[0] else ''
                    # except IndexError:
                    #     pass

            except Exception as e:
                print(f'get data from contacts: {e}')

            try:
                sitemap_tree = self.get_sitemap_tree()

                # get sitemap tree
                if sitemap_tree:

                    sitemap_leader_phone, sitemap_leader_email = self.get_leader_phone_and_email_from_sitemap(sitemap_tree) # noqa

                    sitemap_leader_phone_from_team, sitemap_leader_email_from_team, \
                    text_sitemap_leader_phone_from_team, text_sitemap_leader_email_from_team = \
                        self.get_leader_phone_and_email_from_sitemap_section_team(sitemap_tree) # noqa

                    text_sitemap_leader_phone_from_team = [j for i in text_sitemap_leader_phone_from_team for j in i] # noqa
                    text_sitemap_leader_phone_from_team = self.unique([i for i in text_sitemap_leader_phone_from_team if i]) # noqa

                    text_sitemap_leader_email_from_team = [j for i in text_sitemap_leader_email_from_team for j in i] # noqa
                    text_sitemap_leader_email_from_team = self.unique([i for i in text_sitemap_leader_email_from_team if i]) # noqa

                    if self.all_pages == 1:
                        all_pages_leader_phone, all_pages_leader_email = self.check_phones_emails_on_every_page(sitemap_tree) # noqa

            except Exception as e:
                print(f'sitemap_tree: {e}')

            try:
                name_leader = text_from_phone if text_from_phone else text_from_email
            except Exception as e:
                print(f'name_leader: {e}')

            try:
                if not email_leader and name_leader:
                    if len(name_leader[0].split(sep=' ')) == 2:
                        email_leader = self.gen_email(name_leader, self.website)
            except IndexError:
                pass

            try:
                if not phone_leader:
                    phone_leader = sitemap_leader_phone if sitemap_leader_phone else sitemap_leader_phone_from_team if sitemap_leader_phone_from_team else '' # noqa
                    if phone_leader:
                        phone_leader = phone_leader[0]
            except Exception as e:
                print(f'phone_leader_main: {e}')

            try:
                if not email_leader:
                    email_leader = sitemap_leader_email if sitemap_leader_email else sitemap_leader_email_from_team if sitemap_leader_email_from_team else '' # noqa
                    if email_leader:
                        email_leader = email_leader[0]
            except Exception as e:
                print(f'email_leader_main: {e}')

            self.write_to_file(
                website=self.website,
                name_leader=name_leader,
                phone_leader=phone_leader,
                text_from_phone=text_from_phone,
                sitemap_leader_phone=sitemap_leader_phone,
                sitemap_leader_phone_from_team=sitemap_leader_phone_from_team,
                text_sitemap_leader_phone_from_team=text_sitemap_leader_phone_from_team,
                all_pages_leader_phone=all_pages_leader_phone,
                email_leader=email_leader,
                text_from_email=text_from_email,
                sitemap_leader_email=sitemap_leader_email,
                sitemap_leader_email_from_team=sitemap_leader_email_from_team,
                text_sitemap_leader_email_from_team=text_sitemap_leader_email_from_team,
                all_pages_leader_email=all_pages_leader_email,
                phone_main=main_page_phone,
                mail_main=main_page_email
            )

        except Exception as e:
            print(f'check_domain: {e}')
            self.write_to_file(
                website=self.website,
                name_leader=name_leader,
                phone_main=main_page_phone,
                phone_leader=phone_leader,
                text_from_phone=text_from_phone,
                sitemap_leader_phone=sitemap_leader_phone,
                sitemap_leader_phone_from_team=sitemap_leader_phone_from_team,
                text_sitemap_leader_phone_from_team=text_sitemap_leader_phone_from_team,
                all_pages_leader_phone=all_pages_leader_phone,
                mail_main=main_page_email,
                text_from_email=text_from_email,
                email_leader=email_leader,
                sitemap_leader_email=sitemap_leader_email,
                sitemap_leader_email_from_team=sitemap_leader_email_from_team,
                text_sitemap_leader_email_from_team=text_sitemap_leader_email_from_team,
                all_pages_leader_email=all_pages_leader_email,
            )

    @staticmethod
    def gen_email(leader_name, homepage):
        """the method generates emails from the name of the head of the company and checks their availability"""

        to_return = list()
        result = list()

        try:
            homepage = homepage.split('www.')[1]
            firstname, lastname = leader_name[0].split(sep=' ')

            temp = "{}.{}@{}".format(firstname, lastname, homepage)
            to_return.append(temp)
            temp = "{}.{}@{}".format(lastname, firstname, homepage)
            to_return.append(temp)
            temp = "{}@{}".format(lastname, homepage)
            to_return.append(temp)
            temp = "{}@{}".format(firstname, homepage)
            to_return.append(temp)
            temp = "{}.{}@{}".format(firstname[0], lastname[0], homepage)
            to_return.append(temp)
            temp = "{}.{}@{}".format(firstname[0], lastname, homepage)
            to_return.append(temp)
            temp = "{}.{}@{}".format(lastname[0], firstname, homepage)
            to_return.append(temp)
            temp = "{}.{}@{}".format(firstname, lastname[0], homepage)
            to_return.append(temp)
            temp = "{}.{}@{}".format(lastname, firstname[0], homepage)
            to_return.append(temp)

            for email in to_return:
                r = check_email_accessible(email)
                if r is True:
                    result.append(email)
            if len(result) > 1:
                result = result[0]
        except Exception as e:
            print(f'gen_email: {e}')

        return result

    @staticmethod
    def get_html_with_selenium(url: str) -> str:
        """get main page html"""
        chrome_options = webdriver.ChromeOptions()
        chrome_options.headless = True
        browser = webdriver.Chrome('chromedriver', chrome_options=chrome_options)
        browser.get(url)
        time.sleep(5)
        html = browser.page_source
        return html

    def get_sitemap_tree(self) -> list:
        """get all links from sitemap"""
        sitemap_tree = list()
        web_client = _RequestsWebClient()
        try:
            tree = sitemap_tree_for_homepage(self.website, web_client)
            for page in tree.all_pages():
                sitemap_tree.append(page.url)
        except Exception as e:
            print(f'get_sitemap_tree: {e}')
        return sitemap_tree

    def get_contacts_html(self, main_page_html: str) -> list:
        """looking for a section with contacts on the main page and get htmls"""
        html_list = list()
        main_page_soup = BeautifulSoup(main_page_html, 'lxml')
        try:
            links = [[link.get('href'), link] for link in main_page_soup.findAll('a')]
            for result in links:
                link = result[0]
                tag_text = str(result[1].text).lower()
                for word in self.words_for_company_team:
                    if link is not None and (word in link or word in tag_text):
                        try:
                            response = requests.get(self.website + '/' + link, headers=self.headers)
                            if response.status_code == 200:
                                html_list.append(response.text)
                        except:  # noqa
                            pass
                        try:
                            response = requests.get(self.website + link, headers=self.headers)
                            if response.status_code == 200:
                                html_list.append(response.text)
                        except:  # noqa
                            pass
                        try:
                            response = requests.get(link, headers=self.headers)
                            if response.status_code == 200:
                                html_list.append(response.text)
                        except:  # noqa
                            pass
        except Exception as e: # noqa
            print(f'get_contacts_urls: {e}')
        return html_list

    def find_phones(self, text, leader=False) -> tuple:
        """the method searches for phone numbers on the page"""
        phones = list()
        names = list()
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
                            try:
                                text_from_phone = str(soup.find(text=re.compile(word)).parent.text).strip().replace('\n', ' ') # noqa TODO
                                name = self.get_names([text_from_phone])
                                if name:
                                    names.append(name)
                            except Exception: # noqa
                                pass
                            for match in phonenumbers.PhoneNumberMatcher(str(soup.find(text=re.compile(word)).parent), "CH"):  # noqa TODO
                                result = str(match).split(sep=') ', maxsplit=1)[1]
                                if result:
                                    phones.append(result)
                        except Exception:  # noqa
                            continue
                if not phones:
                    for word in self.words_for_company_leader:
                        if word in str(soup):
                            try:
                                for match in phonenumbers.PhoneNumberMatcher(str(soup.find(text=re.compile(word)).parent.parent), "CH"): # noqa
                                    result = str(match).split(sep=') ', maxsplit=1)[1]
                                    if result:
                                        phones.append(result)
                                if not names:
                                    try:
                                        text_from_phone = str(soup.find(text=re.compile(word)).parent.parent.text).strip().replace('\n', ' ')  # noqa TODO
                                        name = self.get_names([text_from_phone])
                                        if name:
                                            names.append(name)
                                    except Exception:  # noqa
                                        pass
                            except Exception:  # noqa
                                continue
            phones = self.unique_phones(phones)
            names = [j for i in names for j in i]
        except Exception as e:
            print(f'find_phones: {e}')
        return phones, names

    def find_emails(self, html: str, leader=False) -> tuple:
        """the method searches for email on the page"""
        emails = list()
        names = list()
        try:
            soup = BeautifulSoup(html, 'lxml')
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
                            tag = soup.find(text=re.compile(word)).parent
                            try:
                                text_from_email = str(soup.find(text=re.compile(word)).parent.text).strip().replace('\n', ' ') # noqa TODO
                                name = self.get_names([text_from_email])
                                if name:
                                    names.append(name)
                            except Exception: # noqa
                                pass
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
                                if not names:
                                    try:
                                        text_from_email = str(soup.find(text=re.compile(word)).parent.parent.text).strip().replace('\n', ' ')  # noqa TODO
                                        name = self.get_names([text_from_email])
                                        if name:
                                            names.append(name)
                                    except Exception:  # noqa
                                        pass
                            except Exception:  # noqa
                                continue
            emails = self.unique(emails) # noqa
            names = [j for i in names for j in i]
        except Exception as e:
            print(f'find_emails: {e}')
        return emails, names

    def get_names(self, text_from_phone):
        """find names in sting"""
        names = []
        try:
            for i in text_from_phone:
                i_list = []
                r = re.sub(r"([A-Z])", r" \1", i).split()
                r = self.unique(r)
                r = [res.replace(',', '').replace('.', '').replace(' ', '') for res in r if res[0].isupper()] # noqa
                for word in r:
                    if word[0].isupper() is True and (dataset.search_first_name(word) > 5.0 or dataset.search_last_name(word) > 5.0) and len(i_list) < 2: # noqa
                        i_list.append(word)
                result = ' '.join(i_list)
                if result:
                    names.append(result)
        except Exception as e:  # noqa
            print(f'get_names: {e}')
        return names

    @staticmethod
    def unique_phones(lst: list) -> list:
        """remove duplicate phones"""
        phones = []
        for ph in lst:
            phone = ph.replace(
                ' ', '').replace('+', '').replace('(', '').replace(')', '').replace('-', '').replace('.', '').replace('/', '') # noqa
            phones.append(phone)
        set_lst = list(set(phones))
        return set_lst

    @staticmethod
    def unique(lst: list) -> list:
        """remove duplicate"""
        set_lst = list(OrderedSet(lst))
        return set_lst

    def get_or_create_results_file(self):
        """get or create results file"""

        columns = list()
        columns.append('website')
        columns.append('name_leader')
        columns.append('phone_leader')
        columns.append('email_leader')
        columns.append('phone_main')
        columns.append('mail_main')
        # columns.append('text_from_phone')
        columns.append('sitemap_leader_phone')
        columns.append('sitemap_leader_phone_from_team')
        # columns.append('text_sitemap_leader_phone_from_team')
        columns.append('all_pages_leader_phone')
        # columns.append('text_from_email')
        columns.append('sitemap_leader_email')
        columns.append('sitemap_leader_email_from_team')
        # columns.append('text_sitemap_leader_email_from_team')
        columns.append('all_pages_leader_email')

        if not os.path.exists('results.xlsx'):
            with open(self.result_file, "w", newline="", encoding='UTF-8') as f:
                writer = csv.writer(f)
                writer.writerows([columns])

    def write_to_file(
            self, website, name_leader,
            phone_leader, text_from_phone, sitemap_leader_phone, sitemap_leader_phone_from_team, text_sitemap_leader_phone_from_team, all_pages_leader_phone, # noqa
            email_leader, text_from_email, sitemap_leader_email, sitemap_leader_email_from_team, text_sitemap_leader_email_from_team, all_pages_leader_email, # noqa
            phone_main, mail_main
    ):
        """write data to file"""
        if not website:
            website = ''
        if not name_leader:
            name_leader = ''
        if not phone_leader:
            phone_leader = ''
        # if not text_from_phone:
        #     text_from_phone = ''
        if not sitemap_leader_phone:
            sitemap_leader_phone = ''
        if not sitemap_leader_phone_from_team:
            sitemap_leader_phone_from_team = ''
        # if not text_sitemap_leader_phone_from_team:
        #     text_sitemap_leader_phone_from_team = ''
        if not all_pages_leader_phone:
            all_pages_leader_phone = ''
        if not email_leader:
            email_leader = ''
        # if not text_from_email:
        #     text_from_email = ''
        if not sitemap_leader_email:
            sitemap_leader_email = ''
        if not sitemap_leader_email_from_team:
            sitemap_leader_email_from_team = ''
        # if not text_sitemap_leader_email_from_team:
        #     text_sitemap_leader_email_from_team = ''
        if not all_pages_leader_email:
            all_pages_leader_email = ''
        if not phone_main:
            phone_main = ''
        if not mail_main:
            mail_main = ''

        lst = list()
        lst.append(website)
        lst.append(name_leader)
        lst.append(phone_leader)
        lst.append(email_leader)
        lst.append(phone_main)
        lst.append(mail_main)
        # lst.append(text_from_phone)
        lst.append(sitemap_leader_phone)
        lst.append(sitemap_leader_phone_from_team)
        # lst.append(text_sitemap_leader_phone_from_team)
        lst.append(all_pages_leader_phone)
        # lst.append(text_from_email)
        lst.append(sitemap_leader_email)
        lst.append(sitemap_leader_email_from_team)
        # lst.append(text_sitemap_leader_email_from_team)
        lst.append(all_pages_leader_email)

        # with csv lib
        with open(self.result_file, "a", newline="", encoding='UTF-8') as f:
            writer = csv.writer(f)
            writer.writerows([lst])

    @staticmethod
    def check_email_valid(email: str) -> bool:
        """check email validity"""
        bool_result = is_email(email)
        return bool_result

    def find_phone_by_keyword(self, url: str, word: str) -> list:
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
        except Exception as e:  # noqa
            return phone_list

    def find_email_by_keyword(self, url: str, word: str) -> list:
        """looking for a email on the page by keyword"""
        email_list = []
        try:
            html = requests.get(url, headers=self.headers).text
            soup = BeautifulSoup(html, 'lxml')
            tag = soup.find(text=re.compile(word)).parent
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
            return email_list

    def get_leader_phone_and_email_from_sitemap(self, sitemap_tree: list) -> tuple:
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
        emails = self.unique(emails)
        return phones, emails

    def get_leader_phone_and_email_from_sitemap_section_team(self, sitemap_tree: list) -> tuple:
        """looking for leader phone and email number in team section"""
        leader_phone_from_team = []
        text_leader_phone_from_team = []
        leader_email_from_team = []
        text_leader_email_from_team = []
        try:
            for url in sitemap_tree:
                for word in self.words_for_company_team:
                    if word in url:

                        phones, phones_txt = self.find_phones(requests.get(url, headers=self.headers).text, leader=True)
                        leader_phone_from_team.append(phones)
                        text_leader_phone_from_team.append(phones_txt)

                        emails, emails_txt = self.find_emails(requests.get(url, headers=self.headers).text, leader=True)
                        leader_email_from_team.append(emails)
                        text_leader_email_from_team.append(emails_txt)
        except Exception as e: # noqa
            print(f'get_leader_phone_and_email_from_sitemap_section_team: {e}')
        phones = [j for i in leader_phone_from_team for j in i]
        phones = self.unique_phones(phones)
        emails = [j for i in leader_email_from_team for j in i]
        emails = self.unique(emails)
        return phones, emails, text_leader_phone_from_team, text_leader_email_from_team

    def check_phones_emails_on_every_page(self, sitemap_tree: list) -> tuple:
        """looking for phones, emails on each page"""
        all_pages_phone, all_pages_emails = self.check_every_page(sitemap_tree)
        return all_pages_phone, all_pages_emails

    def check_every_page(self, sitemap_tree: list) -> tuple:
        """check each page for  phones, emails"""
        phones = []
        emails = []
        for url in sitemap_tree:
            try:
                response = requests.get(url, headers=self.headers)
                text = response.text

                ph, _ = self.find_phones(text, leader=True)
                phones.append(ph)

                em, _ = self.find_emails(text, leader=True)
                emails.append(em)

            except Exception as e:
                print(f'check_every_page: {e}')
        phones = [j for i in phones for j in i]
        phones = self.unique_phones(phones)
        emails = [j for i in emails for j in i]
        emails = self.unique(emails)
        return phones, emails


def get_class(url: str) -> None:
    obj = LeadGeneration(url)
    obj.start()
    print(f'url_started: {url}')


def task_done(future):  # noqa
    """this is needed to handle the timeout in multithreaded mode""" # noqa
    try:
        result = future.result()  # noqa (blocks until results are ready)
    except TimeoutError as error:
        print("Function took longer than %d seconds" % error.args[1])
    except Exception as error:
        print("Function raised %s" % error)


if __name__ == '__main__':

    # get one website
    # site_url = sys.argv[1]
    site_url = 'http://www.compag.ch'
    # mode = int(sys.argv[2])
    mode = 0

    # run one site
    obj = LeadGeneration(site_url, mode)
    print(f'url_started: {site_url}')
    obj.start()

    # # get websites from file
    # urls = list()
    # df = pd.read_excel('Batch-Company-Adresses_test.xlsx', engine='openpyxl')
    # domains = df.to_dict(orient='record')
    # for domain in domains:
    #     if type(domain['Internet-Adresse']) is not float:
    #         urls.append(domain['Internet-Adresse'])
    #
    # # multi-threaded with timeout
    # with ProcessPool(max_workers=3, max_tasks=6) as pool:
    #     for u in urls:
    #         future = pool.schedule(get_class, args=[u], timeout=600)
    #         future.add_done_callback(task_done)
