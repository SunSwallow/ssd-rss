import requests
import argparse
import json
from bs4 import BeautifulSoup
import PyRSS2Gen
import re
import datetime
from flask import Flask, Response
import time
import logging
# logging.getLogger('werkzeug').disabled = True

logging.basicConfig(
    filename='app.log',      # 指定日志文件名
    level=logging.WARN,      # 设置日志级别
    format='%(asctime)s - %(levelname)s - %(message)s'  # 设置日志格式
)

def my_print(string):
    print(string)
    logging.warning(string)


def get_refresh_time(inputs):
    '''
    函数的作用是传入特定格式的刷新时间，返回一周内所有的刷新时间，目前支持两种输入：
    1. 如果想每天都刷新种子，传入 ","分割的24小时时间，例如：
        "10"代表每天10点更新，"10,18"代表每天上午10点，下午6点更新
    2. 按周指定时间，每个时间点为0H13，第一个数字代表周几（1代表周一），第二个数字代表小时数
        "1H3,4H20"代表周二凌晨3点与周五晚上8点
    '''
    time_stamps = []
    if "H" not in inputs: # 代表模式1
        hours = [int(i) for i in inputs.split(",")]
        
        for weekday in range(7):
            for hour in hours:
                time_stamps.append((weekday, hour))
    else:
        weekday_hours = inputs.split(",")
        for weekday_hour in weekday_hours:
            weekday, hour = int(weekday_hour.split("H")[0])-1, int(weekday_hour.split("H")[1])
            time_stamps.append((weekday, hour))
    return time_stamps


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
parser.add_argument("--refreshing_hour", default="10", type=str, help="What hour to refresh the torrent")
parser.add_argument("--min", default=0, type=int, help="min size (GB)")
parser.add_argument("--max", default=100, type=int, help="max size (GB)")
args = parser.parse_args()
print(args)
session = requests.Session()
# rss_items = get_torrent_putao(args, session, user_headers)
app = Flask(__name__)

my_print(f'Update Scheduler: {str(get_refresh_time(args.refreshing_hour))}')
my_print(f'Last Time Week: {datetime.datetime.now().isocalendar().week}, Last Time: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
refresh_time = datetime.datetime.now()
rss_items = get_torrent_ssd(args, session, user_headers, refresh_time)
print(refresh_time.strftime("%Y-%m-%d %H:%M:%S"))

@app.route('/')
def rss():
    global rss_items, refresh_time

    now = datetime.datetime.now()
    for (week, hour) in get_refresh_time(args.refreshing_hour):
        if (now.weekday(), now.hour) >= (week, hour): # 当前时间越过某一个更新时刻
            if now.isocalendar().week > refresh_time.isocalendar().week: # 进入新的一周，达到更新时间便更新
                my_print(f'Now  Time Week: {now.isocalendar().week}, Now  Time: {now.strftime("%Y-%m-%d %H:%M:%S")}')
                my_print(f'Last Time Week: {refresh_time.isocalendar().week}, Last Time: {refresh_time.strftime("%Y-%m-%d %H:%M:%S")}')
                my_print(f'Update Scheduler: {str(get_refresh_time(args.refreshing_hour))}')
                refresh_time = datetime.datetime.now()
                rss_items = get_torrent_ssd(args, session, user_headers, refresh_time)
                break
            elif (week, hour)>(refresh_time.weekday(), refresh_time.hour): # 上次更新时刻在该更新时刻之前
                my_print(f'Now  Time Week: {now.isocalendar().week}, Now  Time: {now.strftime("%Y-%m-%d %H:%M:%S")}')
                my_print(f'Last Time Week: {refresh_time.isocalendar().week}, Last Time: {refresh_time.strftime("%Y-%m-%d %H:%M:%S")}')
                my_print(f'Update Scheduler: {str(get_refresh_time(args.refreshing_hour))}')
                refresh_time = datetime.datetime.now()
                rss_items = get_torrent_ssd(args, session, user_headers, refresh_time)
                break
            else:
                pass # do nothing

    rss = PyRSS2Gen.RSS2(title='SSD RSS订阅', link="http://127.0.0.1:{}".format(args.port), description='自定义RSS订阅', pubDate=datetime.datetime.utcnow(), items=rss_items)
    rss = rss.to_xml()
    rss = rss.replace("iso-8859-1", "utf-8")
    r = Response(response=rss, status=200, mimetype="application/xml")
    r.headers["Content-Type"] = "text/xml; charset=utf-8"
    return r

app.run(host='0.0.0.0', port=args.port)

