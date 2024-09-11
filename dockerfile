FROM python:3-alpine
MAINTAINER WuJian_Home
COPY . .
RUN pip install --no-cache-dir -r requirements.txt
EXPOSE 80
ENV cookies=none  refreshing_minute=30 min=0 max=100
CMD ["sh", "-c", "python3 main.py --cookies \"$cookies\" --refreshing_minute=$refreshing_minute --min=$min --max=$max"]
