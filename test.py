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


url = 'https://www.holliger.com/sitemap.xml'


r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
html = r.text
print(html)

counter = 0

words_for_goods = [
    'goods', 'produ', 'commodity', 'ware', 'item', 'article', 'artikel', 'objekte', 'object',
    'dienstleistungen', 'Dienstleistungen', 'services', 'service', 'Bedienung', 'bedienung'
]
urls_list = str(html)
print(f'urls_list: {urls_list}')
for word in words_for_goods:
    counter += urls_list.count(word)

print(counter)
