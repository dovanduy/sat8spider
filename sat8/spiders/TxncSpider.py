# -*- coding: utf-8 -*-

from ProductSpiderV2 import ProductSpiderV2

class TxncSpider(ProductSpiderV2):

    env = 'quick'

    # Get sites for crawler
    def get_avaiable_sites(self):
        conn = self.conn
        cursor = self.cursor

        query = "SELECT sites.* FROM sites WHERE allow_crawl = 1 AND id = 2318"
        query = query + " AND sites.env_quick = 1";

        cursor.execute(query)
        sites = cursor.fetchall()

        if not sites:
            errMsg = str("----------------------------------------------------------------------------------------------\n")
            errMsg = errMsg + 'No site allow crawl or testing'
            errMsg = errMsg + "\n----------------------------------------------------------------------------------------------\n";
            raise ValueError(errMsg)

        return sites;