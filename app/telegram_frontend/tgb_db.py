import pymongo
import pandas as pd
import time
import logging
import prettytable

from binance.um_futures import UMFutures
from pybit.usdt_perpetual import HTTP
from telegram import ParseMode

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


class dbOperations:
    def __init__(self, glb, udt):
        self.globals = glb
        self.client = pymongo.MongoClient(glb.dbpath)
        self.db = self.client["binance"]
        self.usertable = self.db["Users"]
        self.commandtable = self.db["Commands"]
        self.tradertable = self.db["Traders"]
        self.notitable = self.db["Notifications"]
        self.updater = udt

    def getall(self, table):
        data = []
        if table == "usertable":
            for x in self.usertable.find():
                data.append(x)
        if table == "commandtable":
            for x in self.commandtable.find():
                data.append(x)
        return data

    def delete_command(self, docids):
        for docid in docids:
            self.commandtable.delete_one({"_id": docid})

    def add_user(self, chat_id, userdoc):
        self.usertable.insert_one(userdoc)
        self.updater.bot.sendMessage(chat_id, "Initialization successful!")

    def get_trader(self, name):
        myquery = {"name": name}
        return self.tradertable.find_one(myquery)

    def add_trader(self, traderdoc):
        self.tradertable.insert_one(traderdoc)

    def get_user(self, chat_id):
        myquery = {"chat_id": chat_id}
        return self.usertable.find_one(myquery)

    def update_user(self, chat_id, userdoc):
        myquery = {"chat_id": chat_id}
        return self.usertable.replace_one(myquery, userdoc)

    def update_trader(self, uid, traderdoc):
        myquery = {"uid": uid}
        return self.tradertable.replace_one(myquery, traderdoc)

    def check_presence(self, chat_id):
        myquery = {"chat_id": chat_id}
        mydoc = self.usertable.find(myquery)
        i = 0
        for doc in mydoc:
            i += 1
        return i >= 1

    def deleteuser(self, chat_id):
        myquery = {"chat_id": chat_id}
        user = self.usertable.find_one(myquery)
        for uid in user["traders"]:
            self.delete_trader(uid)
        self.usertable.delete_many(myquery)
        self.updater.bot.sendMessage(chat_id, "Account successfully deleted.")

    def get_trader_list(self, chat_id):
        myquery = {"chat_id": chat_id}
        user = self.usertable.find_one(myquery)
        data = []
        for x in user["traders"]:
            data.append(user["traders"][x]["name"])
        return data

    def get_trader_fromuser(self, chat_id, tradername):
        myquery = {"chat_id": chat_id}
        user = self.usertable.find_one(myquery)
        for uid in user["traders"]:
            if user["traders"][uid]["name"] == tradername:
                return user["traders"][uid]
        return None

    def delete_trader(self, uid, chat_id=None):
        myquery = {"uid": uid}
        data = self.tradertable.find_one(myquery)
        if data["num_followed"] == 1:
            self.tradertable.delete_one(myquery)
        else:
            data["num_followed"] -= 1
            self.tradertable.replace_one(myquery, data)
        if chat_id is not None:
            user = self.get_user(chat_id)
            del user["traders"][uid]
            myquery = {"chat_id": chat_id}
            self.usertable.replace_one(myquery, user)

    def insert_notification(self, noti):
        self.notitable.insert_one(noti)

    def set_all_leverage(self, chat_id, lev):
        myquery = {"chat_id": chat_id}
        data = self.usertable.find_one(myquery)
        temp = dict()
        for symbol in data["leverage"]:
            temp[f"leverage.{symbol}"] = lev
        newvalues = {"$set": temp}
        self.usertable.update_one(myquery, newvalues)
        self.updater.bot.sendMessage(chat_id, "successfully updated leverage!")

    def get_user_symbols(self, chat_id):
        myquery = {"chat_id": chat_id}
        data = self.usertable.find_one(myquery)
        return list(data["leverage"].keys())

    def set_leverage(self, chat_id, symbol, lev):
        myquery = {"chat_id": chat_id}
        newvalues = {"$set": {f"leverage.{symbol}": lev}}
        self.usertable.update_one(myquery, newvalues)
        self.updater.bot.sendMessage(chat_id, "successfully updated leverage!")

    def set_tp(self, chat_id, tp):
        myquery = {"chat_id": chat_id}
        newvalues = {"$set": {f"tp": tp}}
        self.usertable.update_one(myquery, newvalues)

    def set_sl(self, chat_id, sl):
        myquery = {"chat_id": chat_id}
        newvalues = {"$set": {f"sl": sl}}
        self.usertable.update_one(myquery, newvalues)

    def list_followed_traders(self, chat_id):
        myquery = {"chat_id": chat_id}
        data = self.usertable.find_one(myquery)
        traderlist = []
        for uid in data["traders"]:
            traderlist.append(data["traders"][uid]["name"])
        return traderlist

    def set_all_proportion(self, chat_id, uid, prop):
        myquery = {"chat_id": chat_id}
        data = self.usertable.find_one(myquery)
        temp = dict()
        for symbol in data["traders"][uid]["proportion"]:
            temp[f"traders.{uid}.proportion.{symbol}"] = prop
        newvalues = {"$set": temp}
        self.usertable.update_many(myquery, newvalues)

    def set_proportion(self, chat_id, uid, symbol, prop):
        myquery = {"chat_id": chat_id}
        newvalues = {"$set": {f"traders.{uid}.proportion.{symbol}": prop}}
        self.usertable.update_one(myquery, newvalues)
        self.updater.bot.sendMessage(chat_id, "Successfully changed proportion!")

    def query_field(self, chat_id, *args):
        myquery = {"chat_id": chat_id}
        result = self.usertable.find_one(myquery)
        for key in list(args):
            result = result[key]
        return result

    def set_all_tmode(self, chat_id, uid, tmode):
        myquery = {"chat_id": chat_id}
        data = self.usertable.find_one(myquery)
        temp = dict()
        for symbol in data["traders"][uid]["tmode"]:
            temp[f"traders.{uid}.tmode.{symbol}"] = tmode
        newvalues = {"$set": temp}
        self.usertable.update_many(myquery, newvalues)

    def set_tmode(self, chat_id, uid, symbol, tmode):
        myquery = {"chat_id": chat_id}
        newvalues = {"$set": {f"traders.{uid}.tmode.{symbol}": tmode}}
        self.usertable.update_one(myquery, newvalues)

    def set_safety(self, chat_id, sr):
        myquery = {"chat_id": chat_id}
        newvalues = {"$set": {f"safety_ratio": sr}}
        self.usertable.update_one(myquery, newvalues)

    def set_slippage(self, chat_id, sr):
        myquery = {"chat_id": chat_id}
        newvalues = {"$set": {f"slippage": sr}}
        self.usertable.update_one(myquery, newvalues)

    def set_api(self, chat_id, key, secret):
        myquery = {"chat_id": chat_id}
        newvalues = {"$set": {f"api_key": key, "api_secret": secret}}
        self.usertable.update_one(myquery, newvalues)

    def get_balance(self, chat_id):
        result = self.usertable.find_one({"chat_id": chat_id})
        try:
            client = UMFutures(
                key=result['api_key'],
                secret=result['api_secret']
            )
            balances = client.balance()
            for balance in balances:
                if balance['asset'] == "USDT":
                    usdt_balance = balance
                    break
            tosend = f"Your USDT account balance:\n" \
                     f"Balance: {float(usdt_balance['balance']):.2f}\n" \
                     f"Available: {float(usdt_balance['availableBalance']):.2f}\n" \
                     f"Unrealized PNL: {float(usdt_balance['crossUnPnl']):.2f}"
            self.updater.bot.sendMessage(chat_id=chat_id, text=tosend)
        except Exception as e:
            logger.info(str(e))
            self.updater.bot.sendMessage(
                chat_id=chat_id, text="Unable to retrieve balance."
            )

    def get_positions(self, chat_id):
        result = self.usertable.find_one({"chat_id": chat_id})
        potisions = []
        try:
            client = UMFutures(
                key=result['api_key'],
                secret=result['api_secret']
            )
            potisions = client.get_position_risk()
        except:
            logger.error("Other errors")
        try:
            table = prettytable.PrettyTable(["Symbol", "Type", "Size", "Entry", "Mark price", "Lev", "%", "PNL"])
            for pos in potisions:
                if float(pos["notional"]) != 0:
                    size = float(pos["notional"]) / float(pos["leverage"])
                    pnl = float(pos["unRealizedProfit"])
                    percent = (pnl / size) * 100
                    table.add_row([
                        pos["symbol"],
                        pos["positionSide"],
                        f'{size:.2f}',
                        f'{float(pos["entryPrice"]):.3f}',
                        f'{float(pos["markPrice"]):.3f}',
                        pos["leverage"],
                        f'{percent:.2f}%',
                        f'{float(pos["unRealizedProfit"]):.2f}',
                    ])

            self.updater.bot.sendMessage(chat_id=chat_id, text=f'```{table}```', parse_mode=ParseMode.MARKDOWN_V2)
        except Exception as e:
            logger.info(f"hi {str(e)}")
            self.updater.bot.sendMessage(chat_id, "Unable to get positions.")
        return
