import csv
import os
import re
import sys
import time
from concurrent.futures import TimeoutError

import phonenumbers
import requests
from bs4 import BeautifulSoup
from names_dataset import NameDataset
from ordered_set import OrderedSet
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
        'Geschäftsführer', 'Geschäftsleitung', 'Gruppenleitung', 'CEO', 'COO', 'founder', 'Gründer', 'Inhaber'
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
        names_from_contacts = list()
        full_contacts = list()
        sitemap_leader_name_from_team = list()
        sitemap_contacts_from_team = list()
        all_pages_leader_name = list()
        sitemap_leader_name = list()
        temp_phones = list()
        temp_emails = list()

        try:

            # get main page html
            main_page_html = self.get_html_with_selenium(self.website)

            try:
                # get data from main page
                main_page_phone, main_page_email, _, _ = self.get_contact_information(main_page_html)
            except Exception as e:
                print(f'get data from main page: {e}')

            try:
                # find impressum in main page
                impressum_htmls = self.get_impressum(main_page_html)
                if impressum_htmls:
                    for html in impressum_htmls:
                        phones_i, emails_i, _, _ = self.get_contact_information(html)
                        for phone in phones_i:
                            main_page_phone.append(phone)
                        for email in emails_i:
                            main_page_email.append(email)
                main_page_phone = self.unique_phones(main_page_phone)
                main_page_email = self.unique(main_page_email)
            except Exception as e:
                print(f'find impressum in main page and get data: {e}')

            try:
                # get all contacts htmls from main page html
                contacts_htmls = self.get_contacts_html(main_page_html)

                # get data from each contact html
                if contacts_htmls:
                    for html in contacts_htmls:

                        phones, emails, names, contacts = self.get_contact_information(html, leader=True)

                        phone_leader.append(phones)
                        email_leader.append(emails)
                        names_from_contacts.append(names)
                        full_contacts.append(contacts)

                        # get all phones and emails from contact pages
                        phone_m, email_m, _, _ = self.get_contact_information(html)
                        for phone in phone_m:
                            temp_phones.append(phone)
                        for email in email_m:
                            temp_emails.append(email)

                    # get unique ll phones and emails from contact pages
                    temp_phones = self.unique_phones(temp_phones)
                    # if not main_page_phone and temp_phones:
                    #     main_page_phone = temp_phones

                    temp_emails = self.unique(temp_emails)
                    # if not main_page_email and temp_emails:
                    #     main_page_email = temp_emails

                    # unpacking contacts
                    full_contacts = [j for i in full_contacts for j in i]

                    # unpacking phones and get unique
                    names_from_contacts = [j for i in names_from_contacts for j in i]
                    names_from_contacts = self.unique([i for i in names_from_contacts if i])
                    phone_leader = self.unique_phones([j for i in phone_leader for j in i])

                    # get one phone
                    try:
                        phone_leader = phone_leader[0] if phone_leader[0] else ''
                    except IndexError:
                        pass

                    # unpacking emails and get unique
                    email_leader = self.unique([j for i in email_leader for j in i])

            except Exception as e:
                print(f'get data from contacts: {e}')

            try:
                sitemap_tree = self.get_sitemap_tree()

                # get sitemap tree
                if sitemap_tree:

                    sitemap_leader_phone, sitemap_leader_email, sitemap_leader_name = self.get_leader_phone_and_email_from_sitemap(sitemap_tree) # noqa

                    sitemap_leader_phone_from_team, sitemap_leader_email_from_team, \
                    sitemap_leader_name_from_team, sitemap_contacts_from_team = \
                        self.get_leader_phone_and_email_from_sitemap_section_team(sitemap_tree) # noqa

                    if self.all_pages == 1:
                        all_pages_leader_phone, all_pages_leader_email, all_pages_leader_name = self.check_phones_emails_on_every_page(sitemap_tree) # noqa

            except Exception as e:
                print(f'sitemap_tree: {e}')

            try:
                name_leader = names_from_contacts if names_from_contacts else sitemap_leader_name if sitemap_leader_name else sitemap_leader_name_from_team if sitemap_leader_name_from_team else all_pages_leader_name if all_pages_leader_name else '' # noqa
            except Exception as e:
                print(f'name_leader: {e}')

            try:
                if not phone_leader:
                    phone_leader = sitemap_leader_phone if sitemap_leader_phone else sitemap_leader_phone_from_team if sitemap_leader_phone_from_team else all_pages_leader_phone if all_pages_leader_phone else '' # noqa
                    if phone_leader:
                        phone_leader = phone_leader[0]
            except Exception as e:
                print(f'phone_leader_main: {e}')

            try:
                if not email_leader:
                    email_leader = sitemap_leader_email if sitemap_leader_email else sitemap_leader_email_from_team if sitemap_leader_email_from_team else all_pages_leader_email if all_pages_leader_email else '' # noqa
            except Exception as e:
                print(f'email_leader_main: {e}')

            try:
                if not email_leader and name_leader:
                    email_leader = list()
                    for name in name_leader:
                        if len(name.split(sep=' ')) == 2:
                            em = self.gen_email(name_leader, self.website)
                            if em:
                                email_leader.append(em)
            except IndexError:
                pass

            try:
                if not name_leader and email_leader:
                    for em in email_leader:
                        n = em.split(sep='@')[0].split(sep='.')
                        if len(n) == 2:
                            name_leader.append(' '.join(n))
            except Exception as e:
                print(f'get name_leader by email_leader: {e}')

            try:
                if name_leader and temp_emails:
                    for name in name_leader:
                        if len(name.split(sep=' ')) == 2:
                            firstname, secondname = name.split(sep=' ')
                            firstname = firstname.lower() if len(firstname) > 1 else 'no_firstname'
                            secondname = secondname.lower() if len(secondname) > 1 else 'no_secondname'
                            for mail in temp_emails:
                                mail = mail.lower()
                                if (firstname in mail or secondname in mail) and ('info' not in mail and 'office' not in mail): # noqa
                                    email_leader.append(mail)
                                    temp_emails.remove(mail)
                email_leader = self.unique(email_leader)
            except Exception as e:
                print(f'find_name_by_email_main: {e}')

            try:
                if email_leader:
                    for em in email_leader:
                        em = em.lower()
                        if 'info' in em or 'office' in em:
                            email_leader.remove(em)
            except Exception as e:
                print(f'del info office and other from email_leader: {e}')

            self.write_to_file(
                website=self.website,
                name_leader=name_leader,
                phone_leader=phone_leader,
                sitemap_leader_phone=sitemap_leader_phone,
                sitemap_leader_phone_from_team=sitemap_leader_phone_from_team,
                all_pages_leader_phone=all_pages_leader_phone,
                email_leader=email_leader,
                sitemap_leader_email=sitemap_leader_email,
                sitemap_leader_email_from_team=sitemap_leader_email_from_team,
                all_pages_leader_email=all_pages_leader_email,
                phone_main=main_page_phone,
                mail_main=main_page_email,
                sitemap_leader_name_from_team=sitemap_leader_name_from_team,
                sitemap_contacts_from_team=sitemap_contacts_from_team,
                full_contacts=full_contacts
            )

        except Exception as e:
            print(f'check_domain: {e}')
            self.write_to_file(
                website=self.website,
                name_leader=name_leader,
                phone_leader=phone_leader,
                sitemap_leader_phone=sitemap_leader_phone,
                sitemap_leader_phone_from_team=sitemap_leader_phone_from_team,
                all_pages_leader_phone=all_pages_leader_phone,
                email_leader=email_leader,
                sitemap_leader_email=sitemap_leader_email,
                sitemap_leader_email_from_team=sitemap_leader_email_from_team,
                all_pages_leader_email=all_pages_leader_email,
                phone_main=main_page_phone,
                mail_main=main_page_email,
                sitemap_leader_name_from_team=sitemap_leader_name_from_team,
                sitemap_contacts_from_team=sitemap_contacts_from_team,
                full_contacts=full_contacts
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

    def get_impressum(self, main_page_html: str) -> list:
        """looking for a impressum section on the main page and get htmls"""
        html_list = list()
        main_page_soup = BeautifulSoup(main_page_html, 'lxml')
        try:
            links = [[link.get('href'), link] for link in main_page_soup.findAll('a')]
            for result in links:
                link = result[0]
                tag_text = str(result[1].text).lower()
                if link is not None and ('impressum' in link or 'impressum' in tag_text or 'kontakt' in link or 'kontakt' in tag_text or 'contact' in link or 'contact' in tag_text): # noqa
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
            print(f'get_impressum: {e}')
        return html_list

    def get_contact_information(self, text, leader=False) -> tuple:
        """the method searches for contact information on the page"""
        phones = list()
        names = list()
        emails = list()
        contacts = list()
        soup = BeautifulSoup(text, 'lxml')

        try:
            if leader is False:

                # get phone
                try:
                    for match in phonenumbers.PhoneNumberMatcher(text, "CH"):
                        phone = str(match).split(sep=') ', maxsplit=1)[1]
                        if phone:
                            phones.append(phone)
                except Exception as e:
                    print(f'get contact information (phone. leader_is_false): {e}')

                # get email
                try:
                    results = soup.findAll(text=re.compile(r'[\w\.-]+@[\w\.-]+(\.[\w]+)+'))  # noqa
                    if not results:
                        results = soup.findAll(text=re.compile(r'[\w\.-]+\(at\)[\w\.-]+(\.[\w]+)+'))  # noqa
                    if not results:
                        results = soup.findAll(text=re.compile(r'[\w\.-]+\[at\][\w\.-]+(\.[\w]+)+'))  # noqa
                    if not results:
                        results = soup.findAll(text=re.compile(r'[\w\.-]+\[ät\][\w\.-]+(\.[\w]+)+'))  # noqa
                    if not results:
                        results = soup.findAll(text=re.compile(r'[\w\.-]+\(ät\)[\w\.-]+(\.[\w]+)+'))  # noqa
                    if results is not None:
                        for email in results:
                            email = email.strip()
                            if self.check_email_valid(email) is True or '(at)' in email or '[at]' in email or '[ät]' in email or '(ät)' in email: # noqa
                                emails.append(email)
                            else:
                                result = email.split(sep=' ')
                                result = [word for word in result if '@' in word or '(at)' in word or '[at]' in word or '[ät]' in word or '(ät)' in word] # noqa
                                if self.check_email_valid(result[0]) is True or '(at)' in result[0] or '[at]' in result[0] or '[ät]' in result[0] or '(ät)' in result[0]: # noqa
                                    emails.append(result[0])
                except Exception as e:
                    print(f'get contact information (email. leader_is_false): {e}')

            if leader is True:

                for word in self.words_for_company_leader:
                    temp_contact = dict()
                    if word in str(soup):
                        try:

                            # get name
                            try:
                                text_from_phone = str(soup.find(text=re.compile(word)).parent.text).strip().replace('\n', ' ') # noqa TODO
                                name = self.get_names([text_from_phone])
                                temp_contact['word'] = word
                                if name:
                                    names.append(name)
                                    temp_contact['name'] = name
                                else:
                                    text_from_phone = str(soup.find(text=re.compile(word)).parent.parent.text).strip().replace('\n', ' ')  # noqa TODO
                                    name = self.get_names([text_from_phone])
                                    if name:
                                        names.append(name)
                                        temp_contact['name'] = name
                                    else:
                                        text_from_phone = str(soup.find(text=re.compile(word)).parent.parent.parent.text).strip().replace('\n', ' ')  # noqa TODO
                                        name = self.get_names([text_from_phone])
                                        if name:
                                            names.append(name)
                                            temp_contact['name'] = name
                                        else:
                                            text_from_phone = str(soup.find(text=re.compile(word)).parent.parent.parent.parent.text).strip().replace('\n', ' ')  # noqa TODO
                                            name = self.get_names([text_from_phone])
                                            if name:
                                                names.append(name)
                                                temp_contact['name'] = name
                            except Exception: # noqa
                                pass

                            # get phone
                            try:
                                for match in phonenumbers.PhoneNumberMatcher(str(soup.find(text=re.compile(word)).parent), "CH"):  # noqa TODO
                                    result = str(match).split(sep=') ', maxsplit=1)[1]
                                    if result:
                                        phones.append(result)
                                        temp_contact['phone'] = result
                                    else:
                                        for match in phonenumbers.PhoneNumberMatcher(str(soup.find(text=re.compile(word)).parent.parent), "CH"):  # noqa
                                            result = str(match).split(sep=') ', maxsplit=1)[1]
                                            if result:
                                                phones.append(result)
                                                temp_contact['phone'] = result
                                            else:
                                                for match in phonenumbers.PhoneNumberMatcher(str(soup.find(text=re.compile(word)).parent.parent.parent), "CH"):  # noqa
                                                    result = str(match).split(sep=') ', maxsplit=1)[1]
                                                    if result:
                                                        phones.append(result)
                                                        temp_contact['phone'] = result
                                                    else:
                                                        for match in phonenumbers.PhoneNumberMatcher(str(soup.find(text=re.compile(word)).parent.parent.parent.parent), "CH"):  # noqa
                                                            result = str(match).split(sep=') ', maxsplit=1)[1]
                                                            if result:
                                                                phones.append(result)
                                                                temp_contact['phone'] = result
                            except Exception: # noqa
                                pass

                            # get email
                            try:
                                tag = soup.find(text=re.compile(word)).parent
                                email = tag.find(text=re.compile(r'[\w\.-]+@[\w\.-]+(\.[\w]+)+'))  # noqa
                                if not email:
                                    email = tag.find(text=re.compile(r'[\w\.-]+\(at\)[\w\.-]+(\.[\w]+)+'))  # noqa
                                if not email:
                                    email = tag.find(text=re.compile(r'[\w\.-]+\[at\][\w\.-]+(\.[\w]+)+'))  # noqa
                                if not email:
                                    email = tag.find(text=re.compile(r'[\w\.-]+\[ät\][\w\.-]+(\.[\w]+)+'))  # noqa
                                if not email:
                                    email = tag.find(text=re.compile(r'[\w\.-]+\(ät\)[\w\.-]+(\.[\w]+)+'))  # noqa
                                if email is not None:
                                    email = email.strip()
                                    if self.check_email_valid(email) is True or '(at)' in email or '[at]' in email or '[ät]' in email or '(ät)' in email: # noqa
                                        emails.append(email)
                                        temp_contact['email'] = email
                                    else:
                                        email_temp = email.split(sep=' ')
                                        email_temp = [word for word in email_temp if '@' in word or '(at)' in word or '[at]' in word or '[ät]' in word or '(ät)' in word] # noqa
                                        if self.check_email_valid(email_temp[0]) is True or '(at)' in email_temp[0] or '[at]' in email_temp[0] or '[ät]' in email_temp[0] or '(ät)' in email_temp[0]: # noqa:
                                            emails.append(email_temp[0])
                                            temp_contact['email'] = email_temp[0]
                                if not email:
                                    tag = soup.find(text=re.compile(word)).parent.parent  # TODO
                                    email = tag.find(text=re.compile(r'[\w\.-]+@[\w\.-]+(\.[\w]+)+'))  # noqa
                                    if not email:
                                        email = tag.find(text=re.compile(r'[\w\.-]+\(at\)[\w\.-]+(\.[\w]+)+'))  # noqa
                                    if not email:
                                        email = tag.find(text=re.compile(r'[\w\.-]+\[at\][\w\.-]+(\.[\w]+)+'))  # noqa
                                    if not email:
                                        email = tag.find(text=re.compile(r'[\w\.-]+\[ät\][\w\.-]+(\.[\w]+)+'))  # noqa
                                    if not email:
                                        email = tag.find(text=re.compile(r'[\w\.-]+\(ät\)[\w\.-]+(\.[\w]+)+'))  # noqa
                                    if email is not None:
                                        email = email.strip()
                                        if self.check_email_valid(email) is True or '(at)' in email or '[at]' in email or '[ät]' in email or '(ät)' in email: # noqa
                                            emails.append(email)
                                            temp_contact['email'] = email
                                        else:
                                            email_temp = email.split(sep=' ')
                                            email_temp = [word for word in email_temp if '@' in word or '(at)' in word or '[at]' in word or '[ät]' in word or '(ät)' in word] # noqa
                                            if self.check_email_valid(email_temp[0]) is True or '(at)' in email_temp[0] or '[at]' in email_temp[0] or '[ät]' in email_temp[0] or '(ät)' in email_temp[0]: # noqa:
                                                emails.append(email_temp[0])
                                                temp_contact['email'] = email_temp[0]
                                if not email:
                                    tag = soup.find(text=re.compile(word)).parent.parent.parent  # TODO
                                    email = tag.find(text=re.compile(r'[\w\.-]+@[\w\.-]+(\.[\w]+)+'))  # noqa
                                    if not email:
                                        email = tag.find(text=re.compile(r'[\w\.-]+\(at\)[\w\.-]+(\.[\w]+)+'))  # noqa
                                    if not email:
                                        email = tag.find(text=re.compile(r'[\w\.-]+\[at\][\w\.-]+(\.[\w]+)+'))  # noqa
                                    if not email:
                                        email = tag.find(text=re.compile(r'[\w\.-]+\[ät\][\w\.-]+(\.[\w]+)+'))  # noqa
                                    if not email:
                                        email = tag.find(text=re.compile(r'[\w\.-]+\(ät\)[\w\.-]+(\.[\w]+)+'))  # noqa
                                    if email is not None:
                                        email = email.strip()
                                        if self.check_email_valid(email) is True or '(at)' in email or '[at]' in email or '[ät]' in email or '(ät)' in email: # noqa
                                            emails.append(email)
                                            temp_contact['email'] = email
                                        else:
                                            email_temp = email.split(sep=' ')
                                            email_temp = [word for word in email_temp if '@' in word or '(at)' in word or '[at]' in word or '[ät]' in word or '(ät)' in word] # noqa
                                            if self.check_email_valid(email_temp[0]) is True or '(at)' in email_temp[0] or '[at]' in email_temp[0] or '[ät]' in email_temp[0] or '(ät)' in email_temp[0]: # noqa:
                                                emails.append(email_temp[0])
                                                temp_contact['email'] = email_temp[0]
                                if not email:
                                    tag = soup.find(text=re.compile(word)).parent.parent.parent.parent  # TODO
                                    email = tag.find(text=re.compile(r'[\w\.-]+@[\w\.-]+(\.[\w]+)+'))  # noqa
                                    if not email:
                                        email = tag.find(text=re.compile(r'[\w\.-]+\(at\)[\w\.-]+(\.[\w]+)+'))  # noqa
                                    if not email:
                                        email = tag.find(text=re.compile(r'[\w\.-]+\[at\][\w\.-]+(\.[\w]+)+'))  # noqa
                                    if not email:
                                        email = tag.find(text=re.compile(r'[\w\.-]+\[ät\][\w\.-]+(\.[\w]+)+'))  # noqa
                                    if not email:
                                        email = tag.find(text=re.compile(r'[\w\.-]+\(ät\)[\w\.-]+(\.[\w]+)+'))  # noqa
                                    if email is not None:
                                        email = email.strip()
                                        if self.check_email_valid(email) is True or '(at)' in email or '[at]' in email or '[ät]' in email or '(ät)' in email: # noqa
                                            emails.append(email)
                                            temp_contact['email'] = email
                                        else:
                                            email_temp = email.split(sep=' ')
                                            email_temp = [word for word in email_temp if '@' in word or '(at)' in word or '[at]' in word or '[ät]' in word or '(ät)' in word] # noqa
                                            if self.check_email_valid(email_temp[0]) is True or '(at)' in email_temp[0] or '[at]' in email_temp[0] or '[ät]' in email_temp[0] or '(ät)' in email_temp[0]: # noqa:
                                                emails.append(email_temp[0])
                                                temp_contact['email'] = email_temp[0]
                            except Exception:  # noqa
                                continue

                            contacts.append(temp_contact)

                        except Exception:  # noqa
                            continue

            phones = self.unique_phones(phones)
            emails = self.unique(emails)
            names = [j for i in names for j in i]

        except Exception as e:
            print(f'get_contact_information: {e}')

        return phones, emails, names, contacts

    def get_names(self, text_from_phone: list) -> list:
        """find names in sting"""
        names = []
        try:
            for i in text_from_phone:
                i_list = []
                r = re.sub(r"([A-Z])", r" \1", i).split()
                r = self.unique(r)
                r = [res.replace(',', '').replace('.', '').replace(' ', '').replace('-', '') for res in r if res[0].isupper()] # noqa
                for word in r:
                    if word[0].isupper() is True and (dataset.search_first_name(word) > 5 or dataset.search_last_name(word) > 5) and len(i_list) < 2: # noqa
                        i_list.append(word)
                        try:
                            next_word = r[r.index(word) + 1]
                            if next_word[0].isupper() is True:
                                i_list.append(next_word)
                                break
                        except IndexError:
                            pass
                        try:
                            previous_word = r[r.index(word) - 1]
                            if previous_word[0].isupper() is True:
                                i_list.append(previous_word)
                                break
                        except IndexError:
                            pass
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
        # columns.append('contacts')
        columns.append('sitemap_leader_phone')
        columns.append('sitemap_leader_phone_from_team')
        columns.append('all_pages_leader_phone')
        columns.append('sitemap_leader_email')
        columns.append('sitemap_leader_email_from_team')
        columns.append('all_pages_leader_email')
        columns.append('sitemap_leader_name_from_team')
        # columns.append('sitemap_contacts_from_team')

        if not os.path.exists('results.xlsx'):
            with open(self.result_file, "w", newline="", encoding='UTF-8') as f:
                writer = csv.writer(f)
                writer.writerows([columns])

    def write_to_file(
            self, website, name_leader,
            phone_leader, sitemap_leader_phone, sitemap_leader_phone_from_team, all_pages_leader_phone,
            email_leader, sitemap_leader_email, sitemap_leader_email_from_team, all_pages_leader_email,
            phone_main, mail_main, full_contacts, sitemap_leader_name_from_team, sitemap_contacts_from_team
    ):
        """write data to file"""
        if not website:
            website = ''
        if not name_leader:
            name_leader = ''
        # else:
        #     name_leader = self.unique(name_leader)
        if not phone_leader:
            phone_leader = ''
        # else:
        #     phone_leader = self.unique_phones(phone_leader)
        if not sitemap_leader_phone:
            sitemap_leader_phone = ''
        # else:
        #     sitemap_leader_phone = self.unique_phones(sitemap_leader_phone)
        if not sitemap_leader_phone_from_team:
            sitemap_leader_phone_from_team = ''
        # else:
        #     sitemap_leader_phone_from_team = self.unique_phones(sitemap_leader_phone_from_team)
        if not all_pages_leader_phone:
            all_pages_leader_phone = ''
        # else:
        #     all_pages_leader_phone = self.unique_phones(all_pages_leader_phone)
        if not email_leader:
            email_leader = ''
        # else:
        #     email_leader = self.unique(email_leader)
        if not full_contacts:
            full_contacts = ''
        if not sitemap_leader_email:
            sitemap_leader_email = ''
        # else:
        #     sitemap_leader_email = self.unique(sitemap_leader_email)
        if not sitemap_leader_email_from_team:
            sitemap_leader_email_from_team = ''
        # else:
        #     sitemap_leader_email_from_team = self.unique(sitemap_leader_email_from_team)
        if not all_pages_leader_email:
            all_pages_leader_email = ''
        # else:
        #     all_pages_leader_email = self.unique(all_pages_leader_email)
        if not phone_main:
            phone_main = ''
        # else:
        #     phone_main = self.unique_phones(phone_main)
        if not mail_main:
            mail_main = ''
        # else:
        #     mail_main = self.unique(mail_main)
        if not sitemap_leader_name_from_team:
            sitemap_leader_name_from_team = ''
        # else:
        #     sitemap_leader_name_from_team = self.unique(sitemap_leader_name_from_team)
        if not sitemap_contacts_from_team:
            sitemap_contacts_from_team = ''

        lst = list()
        lst.append(website)
        lst.append(name_leader)
        lst.append(phone_leader)
        lst.append(email_leader)
        lst.append(phone_main)
        lst.append(mail_main)
        # lst.append(full_contacts)
        lst.append(sitemap_leader_phone)
        lst.append(sitemap_leader_phone_from_team)
        lst.append(all_pages_leader_phone)
        lst.append(sitemap_leader_email)
        lst.append(sitemap_leader_email_from_team)
        lst.append(all_pages_leader_email)
        lst.append(sitemap_leader_name_from_team)
        # lst.append(sitemap_contacts_from_team)

        # with csv lib
        with open(self.result_file, "a", newline="", encoding='UTF-8') as f:
            writer = csv.writer(f)
            writer.writerows([lst])

    @staticmethod
    def check_email_valid(email: str) -> bool:
        """check email validity"""
        bool_result = is_email(email)
        return bool_result

    def get_leader_phone_and_email_from_sitemap(self, sitemap_tree: list) -> tuple:
        """looking for the phone number and the email of the head of the company"""
        leader_phone = []
        leader_email = []
        leader_name = []
        try:
            for url in sitemap_tree:
                for word in self.words_for_company_leader:
                    if word in url:
                        phones, emails, names, _ = self.get_contact_information(requests.get(url, headers=self.headers).text, leader=True)  # noqa
                        leader_phone.append(phones)
                        leader_email.append(emails)
                        leader_name.append(names)
        except Exception as e: # noqa
            print(f'get_leader_phone_and_email_from_sitemap: {e}')
        phones = [j for i in leader_phone for j in i]
        phones = self.unique_phones(phones)
        emails = [j for i in leader_email for j in i]
        emails = self.unique(emails)
        names = [j for i in leader_name for j in i]
        names = self.unique(names)
        return phones, emails, names

    def get_leader_phone_and_email_from_sitemap_section_team(self, sitemap_tree: list) -> tuple:
        """looking for leader phone and email number in team section"""
        leader_phone_from_team = []
        leader_email_from_team = []
        leader_name_from_team = []
        leader_contacts_from_team = []
        try:
            for url in sitemap_tree:
                for word in self.words_for_company_team:
                    if word in url:

                        phones, emails, names, contacts = self.get_contact_information(requests.get(url, headers=self.headers).text, leader=True) # noqa
                        leader_phone_from_team.append(phones)
                        leader_email_from_team.append(emails)
                        leader_name_from_team.append(names)
                        leader_contacts_from_team.append(contacts)

        except Exception as e: # noqa
            print(f'get_leader_phone_and_email_from_sitemap_section_team: {e}')
        phones = [j for i in leader_phone_from_team for j in i]
        phones = self.unique_phones(phones)
        emails = [j for i in leader_email_from_team for j in i]
        emails = self.unique(emails)
        names = [j for i in leader_name_from_team for j in i]
        names = self.unique(names)
        contacts = [j for i in leader_contacts_from_team for j in i]
        return phones, emails, names, contacts

    def check_phones_emails_on_every_page(self, sitemap_tree: list) -> tuple:
        """looking for phones, emails on each page"""
        try:
            all_pages_phone, all_pages_emails, all_pages_name, _ = self.check_every_page(sitemap_tree)
            return all_pages_phone, all_pages_emails, all_pages_name
        except Exception as e:
            print(f'check_phones_emails_on_every_page: {e}')

    def check_every_page(self, sitemap_tree: list) -> tuple:
        """check each page for  phones, emails"""
        phones_every_page = []
        emails_every_page = []
        names_every_page = []
        contacts_every_page = []
        for url in sitemap_tree:
            try:
                response = requests.get(url, headers=self.headers)
                text = response.text

                phones, emails, names, contacts = self.get_contact_information(text, leader=True)
                phones_every_page.append(phones)
                emails_every_page.append(emails)
                names_every_page.append(names)
                contacts_every_page.append(contacts)

            except Exception as e:
                print(f'check_every_page: {e}')

        phones_every_page = [j for i in phones_every_page for j in i]
        phones_every_page = self.unique_phones(phones_every_page)
        emails_every_page = [j for i in emails_every_page for j in i]
        emails_every_page = self.unique(emails_every_page)
        names_every_page = [j for i in names_every_page for j in i]
        names_every_page = self.unique(names_every_page)
        contacts_every_page = [j for i in contacts_every_page for j in i]

        return phones_every_page, emails_every_page, names_every_page, contacts_every_page


def get_class(url: str) -> None:
    obj = LeadGeneration(url)   # noqa
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
    site_url = sys.argv[1]
    mode = int(sys.argv[2])

    # run one site
    obj = LeadGeneration(site_url, mode)
    print(f'url_started: {site_url}')
    obj.start()
