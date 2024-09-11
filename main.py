import requests
import argparse
import json
from bs4 import BeautifulSoup
import PyRSS2Gen
import re
import datetime
from flask import Flask, Response
import time




def time_to_minutes(time_str):

    # Define a dictionary to hold the conversion values for each unit
    conversion = {'年': 525600,"月":1440*30, '天': 1440, '时': 60, '分': 1}

    # Use regular expressions to find all occurrences of time units and their values
    time_components = re.findall(r'(\d+)([年月天时分])', time_str)

    # Convert and sum up the minutes
    total_minutes = sum(int(value) * conversion[unit] for value, unit in time_components)

    return total_minutes

def parse_cookies(cookies_str):
    cookies = {}
    for cookie in cookies_str.split('; '):
        key, value = cookie.split('=', 1)
        cookies[key] = value
    return cookies



def get_torrent_info_putao(table_row, args, refresh_time):

    name = table_row.select("div.torrent-title")[0].select("a")[0].get("title")
    free_flag = "free" in str(table_row)

    survival_time = table_row.select("td.rowfollow.nowrap span")[0].text

    size = table_row.select("td.rowfollow")[-5].text

    download_href = "https://springsunday.net/" + table_row.select("span.bi.bi-download.torrent-icon")[0].parent.get('href')

    survival_time_minutes = time_to_minutes(survival_time)

    description = table_row.select(".torrent-smalldescr")[0].select("span")[-1].get("title")

    size_ok = False
    if "GB" in size:
        num = float(size.split("GB")[0])
        if  args.min<num<args.max:
            size_ok = True
    comments = f"Free:{free_flag} || Size:{size} || Time:{survival_time_minutes} Minuts || Size OK: {size_ok} || "
    comments += "Refresh Time: {}".format(refresh_time.strftime("%Y-%m-%d %H:%M:%S"))
    rss_item = PyRSS2Gen.RSSItem(title=name, link=download_href, description=description, 
        comments=comments)

    return survival_time_minutes, size_ok, rss_item



def get_torrent_ssd(args, session, headers, refresh_time):
    cookies = parse_cookies(args.cookies)
    for name, value in cookies.items():
        session.cookies.set(name, value)

    # should change when release
    proxies= {}

    response = session.get('https://springsunday.net/torrents.php',
                           headers=headers,
                           proxies=proxies)
    
    soup = BeautifulSoup(response.text, 'html.parser')
    table_rows = soup.select('tr.sticky_bg')

    items = []
    for table_row in table_rows:
        rss_item_with_info = get_torrent_info_putao(table_row, args, refresh_time)
        if rss_item_with_info[2] is not None and rss_item_with_info[1]:
            items.append(rss_item_with_info)
    latest_item = None
    latest_survival_time = 1e20
    for i in items:
        if i[0]<latest_survival_time:
            latest_survival_time = i[0]
            latest_item = i[2]
    return [latest_item]


user_headers = {
    'User-Agent': 'Edg/87.0.4280.88',
}

parser = argparse.ArgumentParser(description='Login to a website using cookies from command line.')
parser.add_argument('--cookies',type=str)
parser.add_argument("--port", default=80, type=int)
parser.add_argument("--refreshing_minute", default=0, type=int, help="The frequency to refresh the torrent list")
parser.add_argument("--min", default=0, type=int, help="min size (GB)")
parser.add_argument("--max", default=100, type=int, help="max size (GB)")
args = parser.parse_args()
print(args)
session = requests.Session()
# rss_items = get_torrent_putao(args, session, user_headers)
app = Flask(__name__)

start_time = time.time()
refresh_time = datetime.datetime.now()
rss_items = get_torrent_ssd(args, session, user_headers, refresh_time)
print(refresh_time.strftime("%Y-%m-%d %H:%M:%S"))

@app.route('/')
def rss():
    global start_time, rss_items, refresh_time

    if time.time() - start_time > args.refreshing_minute*60 or args.refreshing_minute==0:
        start_time = time.time()
        refresh_time = datetime.datetime.now()
        rss_items = get_torrent_ssd(args, session, user_headers, refresh_time)
        print("Refresh Now")

    rss = PyRSS2Gen.RSS2(title='SSD RSS订阅', link="http://127.0.0.1:{}".format(args.port), description='自定义RSS订阅', pubDate=datetime.datetime.utcnow(), items=rss_items)
    rss = rss.to_xml()
    rss = rss.replace("iso-8859-1", "utf-8")
    r = Response(response=rss, status=200, mimetype="application/xml")
    r.headers["Content-Type"] = "text/xml; charset=utf-8"
    return r

app.run(host='0.0.0.0', port=args.port)

