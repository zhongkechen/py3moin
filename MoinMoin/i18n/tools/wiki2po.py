#!/usr/bin/python
"""
    get latest translation page content from the wiki and write it to *.po
"""

master_url = "https://master19.moinmo.in/?action=xmlrpc2"

DOMAIN = "MoinMoin"


def run():
    import sys, xmlrpc.client
    sys.path.insert(0, '../..')

    excluded = ["en", ]  # languages managed in repository, not in wiki

    lang = sys.argv[1]

    if lang not in excluded:
        wiki = xmlrpc.client.ServerProxy(master_url)

        pagename = "MoinI18n/%s" % lang
        print(pagename)
        pagedata = wiki.getPage(pagename).encode('utf-8').replace("\n", "\r\n")

        f = open("%s.%s.po" % (lang, DOMAIN), "w")
        f.write(pagedata)
        f.close()


if __name__ == "__main__":
    run()
