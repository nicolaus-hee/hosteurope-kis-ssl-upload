#!/usr/bin/env python3
from splinter import Browser
from time import sleep
import json
import os
import chromedriver_autoinstaller

from create_certificate import create_certificate

class Domain():
    url = ''
    ssl_href = ''

    def __repr__(self):
        return self.url + ' / ' + self.ssl_href

class Certificate():
    urls = []
    local_path = ''
    key_file = ''
    csr_file = ''
    cert_file = ''
    account_file = ''
    ftp_server = ''
    ftp_user = ''
    ftp_pass = ''
    name = ''
    created = False
    testing = False

    def __repr__(self):
        return self.name

class Url():
    url = ''
    challenge_path = ''
    ftp_server = ''
    ftp_user = ''
    ftp_pass = ''    
    kis_domain = ''

    def __repr__(self):
        return self.url

def main():
    print("HostEurope SSL Updater")

    # parse config
    config, certificates = read_config()
    if len(certificates) == 0:
        print('Config file empty, incomplete or not existing.')
        exit()

    print('Found ' + str(len(certificates)) + ' certificate requests in config file.')    
    print(" ")

    # loop through cert requests and create them
    for c in certificates:
        print('Creating certificate: ' + str(c.name))
        if create_certificate(c.urls, config['settings']['email'], c.ftp_server, c.ftp_user, c.ftp_pass, c.local_path, c.key_file, c.csr_file, c.cert_file, c.account_file, c.testing):
            c.created = True

    # check if any certificates were created successfully, else abort
    if sum(c.created == True for c in certificates) == 0:
        print("No certificates were created, abort upload.")
        exit()

    # kis login
    if config['settings']['upload_to_kis'] == False:
        print(" ")
        print("KIS upload disabled, exiting.")
        exit()

    print(" ")
    print("Uploading certificates")    
    print("- Logging into HE KIS.")
    browser = kis_login(config['settings']['kis_user'], config['settings']['kis_password'])
    if not browser:
        print('- Invalid user name or password.')
        exit()

    # pull ssl domains from kis
    hosteurope_domains = get_ssl_domains(browser, config['settings']['kis_webpack_id'])
    print("- Found " + str(len(hosteurope_domains)) + " domains in KIS.")

    # loop through HE domains and update SSL if in config & new certificate exists
    for c in certificates:
        if c.created == True:
            for u in c.urls:
                for h in hosteurope_domains:
                    if h.url == u.kis_domain:
                        print("- Now updating " + str(u.kis_domain))
                        if upload_certificate(browser, h.ssl_href, c.local_path, c.cert_file, c.key_file):
                            print("- Uploaded successfully")
                        else:
                            print("- Upload failed")

    # log out of KIS
    browser.visit('https://kis.hosteurope.de/?logout=1')

    print("Done!")

def read_config():
    # read certificate settings from config.json
    certificates = []
    try:
        config = json.load(open('config.json',encoding='utf-8'))      
        for c in config['certificates']:
            certificate = Certificate()
            urls = []
            for u in c['urls']:
                url = Url()
                url.url = u['url']
                url.challenge_path = u['challenge_path']
                urls.append(url)
                if 'kis_domain' in u:
                    url.kis_domain = u['kis_domain']
            urls.sort(key=lambda url: url.url)
            certificate.urls = urls
            certificate.ftp_server = c['ftp_server']
            certificate.ftp_user = c['ftp_user']
            certificate.ftp_pass = c['ftp_pass']
            certificate.name = c['name']
            certificate.local_path = c['local_path']
            certificate.key_file = c['key_file']
            certificate.csr_file = c['csr_file']
            certificate.cert_file = c['cert_file']
            certificate.account_file = c['account_file']
            if c['testing'] == True:
                certificate.testing = True
            else:
                certificate.testing = False
            certificates.append(certificate)

    except:
        config = json.loads('{}')

    return config, certificates

def kis_login(username, password):
    chromedriver_autoinstaller.install()
    
    browser = Browser('chrome')

    # log into KIS
    browser.visit('https://sso.hosteurope.de/?app=kis&path=')
    browser.fill('identifier', username)
    browser.fill('password', password)
    button = browser.find_by_tag('button')[1]
    button.click()

    # to do: change to while url still with SSO
    sleep(5)
    if 'https://sso.hosteurope.de/' in browser.url:
        return False
        
    return browser

def get_ssl_domains(browser, kis_webpack_id):
    # get list of domains available for SSL
    browser.visit('https://kis.hosteurope.de/administration/webhosting/admin.php?menu=6&mode=ssl_list&wp_id=' + str(kis_webpack_id))
    domain_table = browser.find_by_tag('table')[2]
    domain_table_rows = domain_table.find_by_tag('tr')

    # copy domain properties to collection
    domains = []
    for domain in domain_table_rows:
        if(domain.find_by_tag('td')[3].value == "Ja" or domain.find_by_tag('td')[3].value == "Yes"):
            d = Domain()

            if(domain.find_by_tag('td')[1].value != "- keine Domains zugeordnet -" and domain.find_by_tag('td')[1].value != '- no domain assigned -'):
                d.url = domain.find_by_tag('td')[1].value
            else:
                d.url = domain.find_by_tag('td')[2].value

            d.ssl_href = domain.find_by_tag('td')[4].find_by_tag('a').first['href']
            domains.append(d)

    return domains

def upload_certificate(browser, ssl_href, local_path, cert_file, key_file):
    # open cert upload page for domain
    browser.visit(ssl_href)

    # select files to upload
    browser.attach_file('certfile', os.path.join(local_path, cert_file))
    browser.attach_file('keyfile', os.path.join(local_path, key_file))

    # find & press upload button
    for b in browser.find_by_tag('input'):
        if b['type'] == 'submit':
            b.click()
            break

    # check if successful
    if 'Die Dateien wurden erfolgreich hochgeladen.' in browser.html or 'the files have been successfully uploaded.' in browser.html:
        return True
    else:
        return False

if __name__ == "__main__":
    main()
