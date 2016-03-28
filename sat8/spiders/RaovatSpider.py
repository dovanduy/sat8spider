# -*- coding: utf-8 -*-
import scrapy
import hashlib
from scrapy.conf import settings
from scrapy.spiders import CrawlSpider, Rule
from scrapy.selector import Selector

from sat8.items import RaovatItem, RaovatItemLoader

from sat8.Classifields.EsRaovat import EsRaovat

from time import gmtime, strftime
from scrapy.linkextractors import LinkExtractor
from urlparse import urlparse

import urllib
import logging


class RaovatSpider(CrawlSpider):
    name = "raovat_spider"

    allowed_domains = ['vatgia.com']

    questionId = 0
    productId = 0;

    def __init__(self):
        self.conn = settings['MYSQL_CONN']
        self.cursor = self.conn.cursor()


    def parse_item(self, response):
        sel = Selector(response)
        product_links = sel.xpath('//*[@class="raovat_listing"]/li[@class="info"]');
        for pl in product_links:
            yield self.parse_raovat(pl, response)

    def parse_raovat(self, selector, response):
        productId = response.meta['productId']
        raovatItemLoader = RaovatItemLoader(item = RaovatItem(), selector = selector)
        raovatItemLoader.add_xpath('title', './/a[@class="tooltip"]//text()')
        raovatItemLoader.add_xpath('link', './/a[@class="tooltip"]/@href')
        raovatItemLoader.add_xpath('teaser', './/div[@class="detail_small"]/div[@class="teaser"]//text()')
        raovatItemLoader.add_value('is_crawl', 1)
        raovatItemLoader.add_xpath('user_name', './/span[@class="raovat_user"]/a[@class="tooltip_user text_link"]/text()')
        raovatItemLoader.add_xpath('price', './/div[@class="more"]/div[@class="price"]//text()')
        raovatItemLoader.add_value('created_at', strftime("%Y-%m-%d %H:%M:%S"))
        raovatItemLoader.add_value('updated_at', strftime("%Y-%m-%d %H:%M:%S"))

        raovatItem = raovatItemLoader.load_item()
        raovatItem['link'] = 'http://vatgia.com' + raovatItem['link'];
        raovatItem['hash_link'] = hashlib.md5(raovatItem['link']).hexdigest()

        if 'user_name' not in raovatItem:
            raovatItem['user_name'] = ''

        if 'price' not in raovatItem:
            raovatItem['price'] = 0

        query = "SELECT id,link FROM classifields WHERE hash_link = %s"
        self.cursor.execute(query, (raovatItem['hash_link']))
        result = self.cursor.fetchone()

        raovatId = 0;
        if result:
            raovatId = result['id']
            logging.info("Item already stored in db: %s" % raovatItem['link'])
        else:
            sql = "INSERT INTO classifields (product_id, title, teaser, user_name, is_crawl, price, link, hash_link, created_at, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            self.cursor.execute(sql, (productId, raovatItem['title'], raovatItem['teaser'],raovatItem['user_name'], raovatItem['is_crawl'] ,raovatItem['price'], raovatItem['link'], raovatItem['hash_link'] ,raovatItem['created_at'], raovatItem['updated_at']))
            self.conn.commit()
            logging.info("Item stored in db: %s" % raovatItem['link'])
            raovatId = self.cursor.lastrowid

        # Insert elasticsearch
        esRaovat = EsRaovat()
        esRaovat.insertOrUpdate(raovatId, raovatItem.toJson())

        # yield raovatItem


    def start_requests(self):
        print '------------------------------', "\n"
        self.conn = settings['MYSQL_CONN']
        self.cursor = self.conn.cursor()
        self.cursor.execute("SELECT DISTINCT id,keyword,rate_keyword FROM products WHERE rate_keyword != '' OR rate_keyword != NULL ORDER BY updated_at DESC")
        products = self.cursor.fetchall()

        url = 'http://vatgia.com/raovat/quicksearch.php?keyword=Sony+Xperia+Z3'
        request = scrapy.Request(url, callback = self.parse_item)
        request.meta['productId'] = 0
        yield request

        # for product in products:
        #     url = 'http://vatgia.com/raovat/quicksearch.php?keyword=%s' %product['rate_keyword']
        #     # self.start_urls.append(url)
        #     request = scrapy.Request(url, callback = self.parse_item)
        #     request.meta['productId'] = product['id']
        #     yield request

        # yield scrapy.Request(response.url, callback=self.parse_item)
        print '------------------------------', "\n\n"
