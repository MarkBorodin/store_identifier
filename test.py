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


url = 'https://www.normagroup.com/connectors/de/home/'


r = requests.get(url)
html = r.text


soup = BeautifulSoup(html, 'lxml')

if 'produ' in html:
    print('+')
