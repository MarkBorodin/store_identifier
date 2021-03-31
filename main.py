# from usp.tree import sitemap_tree_for_homepage
# from url_normalize import url_normalize
# import signal
# from contextlib import contextmanager
# import pandas as pd
# import csv
# import logging
#
# import pandas as pd
# from csv import reader
#
#
# class TimeoutException(Exception):
#     pass
#
#
# @contextmanager
# def time_limit(seconds):
#     def signal_handler(signum, frame):
#         raise TimeoutException("Timed out!")
#     signal.signal(signal.SIGALRM, signal_handler)
#     signal.alarm(seconds)
#     try:
#         yield
#     finally:
#         signal.alarm(0)
#
# # # l = ['https://dev.brandstore.staubli.com/', 'https://www.dev.brandstore.staubli.com/', 'https://www.brandstore.staubli.com/', 'https://brandstore.staubli.com/', 'http://www.staubli.com']
# #
# # # l = ['http://www.staubli.com']
# # l = ['http://www.bally.com']
# #
# #
# # # all_pages() returns an Iterator
# # lst = []
# #
# # for i in l:
# #     with time_limit(120):
# #         try:
# #             tree = sitemap_tree_for_homepage(url_normalize(i))
# #             for page in tree.all_pages():
# #                 lst.append(page.url)
# #         except TimeoutException as e:
# #             continue
# #
# # print(lst)
# # print(len(lst))
# #
# #
# # def get_items(urls_list):
# #     counter = 0
# #     words_for_goods = ['goods', 'product', 'commodity', 'good', 'item', 'article']
# #     urls_list = str(urls_list)
# #     for word in words_for_goods:
# #         counter += urls_list.count(word)
# #     print(counter)
# #
# #
# # get_items(lst)
#
#
# # from sitemapparser import SiteMapParser
# #
# # sm = SiteMapParser('http://www.staubli.com')    # reads /sitemap.xml
# # if sm.has_sitemaps():
# #     sitemaps = sm.get_sitemaps()      # returns iterator of sitemapper.Sitemap instances
# #     print(sitemaps)
# #     print(len(sitemaps))
# # else:
# #     urls = sm.get_urls()         # returns iterator of sitemapper.Url instances
# #     print(urls)
# #     print(len(urls))
# #
#
# #
# #
# # df = pd.read_excel('Batch-Company-Adresses_test.xlsx', engine='openpyxl')
# # # print('Excel Sheet to Dict:', df.to_dict(orient='record'))
# # # for item in df.to_dict(orient='record'):
# # #     print(item)
# #
# # d = df.to_dict(orient='record')
# # print(d)
# # # for item in d.items():
# # #     print(item)
#
#
# def remove_duplicates(common_list):
#     lst = []
#     for dom in common_list:
#         dom = dom.replace('www.', '').replace('http://', '').replace('https://', '')
#         lst.append(url_normalize(dom))
#     lst = list(set(lst))
#     return lst
#
#
# urls = ['https://www.docs.python.org/3/library/urllib.parse.html', 'https://docs.python.org/3/library/urllib.parse.html',
#         'www.docs.python.org/3/library/urllib.parse.html', 'docs.python.org/3/library/urllib.parse.html']
#
#
# print(remove_duplicates(urls))
