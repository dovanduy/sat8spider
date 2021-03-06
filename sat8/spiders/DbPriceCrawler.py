# -*- coding: utf-8 -*-
# Xpath được lấy tự động từ database
# Mỗi ngày lấy 15000 links
# @author Justin <cong.itsoft@gmail.com>
# @date 2016-04-05
import scrapy
import re
import datetime
import hashlib
from scrapy.spiders import CrawlSpider, Rule
from scrapy.selector import Selector
from scrapy.linkextractors import LinkExtractor
from sat8.items import ProductPriceItem, ProductPriceItemLoader
from urlparse import urlparse
from time import gmtime, strftime
from scrapy.conf import settings

import json,urllib

class DbPriceSpider(CrawlSpider):
    name = "product_link"
    allowed_domains = []
    start_urls = []
    rules = ()

    env = 'production'

    def __init__(self):
        self.conn = settings['MYSQL_CONN']
        self.cursor = self.conn.cursor()

    def parse_item(self, response):
        sel = Selector(response)
        site = response.meta['site']
        linkItem = response.meta['link_item']


        # Nếu là json thì chơi kiểu json
        if site['is_json'] == 1 :
            jsonresponse = json.loads(response.body_as_unicode())
            sel = Selector(text=jsonresponse[site['json_key']])

        product_links = sel.xpath(linkItem['xpath_link_detail'])

        for pl in product_links:
            url = response.urljoin(pl.extract());
            request = scrapy.Request(url, callback = self.parse_detail_content)
            request.meta['site'] = site
            request.meta['link_item'] = linkItem
            request.meta['dont_redirect'] = True
            yield request

    # Return product to crawl
    def get_product(self, response):
        link = response.url

        url_parts = urlparse(link)
        site = response.meta['site']
        linkItem = response.meta['link_item']

        pil = ProductPriceItemLoader(item = ProductPriceItem(), response = response)
        pil.add_xpath('title', linkItem['xpath_name'])
        pil.add_xpath('price', linkItem['xpath_price'])
        pil.add_value('source', site['name'])
        pil.add_value('source_id', linkItem['site_id'])
        pil.add_value('brand_id', linkItem['brand_id'])
        pil.add_value('link', link)
        pil.add_value('is_laptop', linkItem['is_laptop'])
        pil.add_value('is_phone', linkItem['is_phone'])
        pil.add_value('is_tablet', linkItem['is_tablet'])

        product = pil.load_item()

        # Price
        price = pil.get_value(product.get('price', "0").encode('utf-8'))
        price = re.sub('\D', '', price)

        product['title'] = product['title'].strip(' \t\n\r')
        product['title'] = product['title'].strip()
        product['name']  = product['title']

        product['price']      = price
        product['created_at'] = strftime("%Y-%m-%d %H:%M:%S")
        product['updated_at'] = strftime("%Y-%m-%d %H:%M:%S")
        product['crawled_at'] = strftime("%Y-%m-%d %H:%M:%S")

        return product

    # Process crawl product
    def parse_detail_content(self, response):
        yield self.get_product(response)


    # Get sites for crawler
    def get_avaiable_sites(self):
        conn = self.conn
        cursor = self.cursor

        # Ngày trong tuần
        weekday = datetime.datetime.today().weekday()

        # Lấy các site sẽ chạy ngày hôm nay
        siteIds = []
        query = "SELECT site_id FROM site_cronjob WHERE day = %s"
        cursor.execute(query, (weekday))
        rows = cursor.fetchall()
        for row in rows:
            siteIds.append(row['site_id'])

        siteIds = ','.join(str(id) for id in siteIds )

        if len(siteIds) <= 0:
            errMsg = str("----------------------------------------------------------------------------------------------\n")
            errMsg = errMsg + 'Ngày hôm nay chưa có site nào được đặt cronjob, vui lòng đặt cronjob cho từng site trong Admin'
            errMsg = errMsg + "\n----------------------------------------------------------------------------------------------\n";
            raise ValueError(errMsg)

        query = "SELECT * FROM sites JOIN site_metas ON sites.id = site_metas.site_id WHERE allow_crawl = 1 AND sites.id IN("+ siteIds +")"

        # Nếu env = testing thì thêm điều kiện testing
        if self.env == 'testing':
            query = query + " AND sites.env_testing = 1"

        # Nếu muốn chạy ngay thì chạy
        if self.env == 'quick':
            query = query + " AND sites.env_quick = 1";

        cursor.execute(query)
        sites = cursor.fetchall()

        return sites;

    def start_requests(self):
        conn = self.conn
        cursor = self.cursor

        try:
            sites = self.get_avaiable_sites()

            crawlLinks = []

            for site in sites:
                queryLink = "SELECT site_links.request_method, xpath_link_detail, site_metas.xpath_name, site_metas.xpath_price, max_page, link, site_links.site_id, brand_id, is_phone, is_tablet, is_laptop FROM site_links JOIN site_metas ON xpath_id = site_metas.id WHERE site_links.site_id = %s ORDER BY site_links.id DESC"
                cursor.execute(queryLink, (site["id"]))
                links = cursor.fetchall()

                for link in links:
                    if link["max_page"] > 0:
                        for i in range(1, link["max_page"]+1):
                            startLink = link["link"].replace('[0-9]+', str(i))

                            request = scrapy.Request(startLink, callback = self.parse_item, method=site['request_method'])
                            request.meta['site'] = site
                            request.meta['link_item'] = link
                            yield request

        except ValueError as e:
            print e
