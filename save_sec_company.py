from urllib.request import urlopen
import certifi
import json
import re

def get_jsonparsed_data(url):
    response = urlopen(url, cafile=certifi.where())
    data = response.read().decode("utf-8")
    return json.loads(data)

url = ("https://financialmodelingprep.com/api/v3/stock/list?apikey=K9lR2FFwXrJJfDR1RChYZltMCVN9NzYU")
data = get_jsonparsed_data(url)


f = open("./data/company.csv", "w")
f.write("symbol,name,exchange,type\n")
for item in data:
    if item["type"] == "stock":
        if "New York" in item["exchange"] or "NASDAQ" in item["exchange"]:
            symbol = re.sub(",", " ", item["symbol"])
            name = re.sub(",", " ", item["name"])
            exchange = re.sub(",", " ", item["exchange"])
            type = re.sub(",", " ", item["type"])
            line = "{},{},{},{}\n".format(symbol, name, exchange, type)
            f.write(line)
f.close()