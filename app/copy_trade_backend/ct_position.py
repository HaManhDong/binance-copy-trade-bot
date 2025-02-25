import logging
import threading
import time

from prettytable import prettytable
from telegram import ParseMode

from app.config import const
from app.config.const import BINANCE_LEADER_BOARD_URL_V1
from app.copy_trade_backend.ct_binance import BinanceUMFuturesClient

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)
import pandas as pd
from datetime import datetime, timedelta
import requests


class WebScraping(threading.Thread):
    def __init__(self, globals, userdb):
        threading.Thread.__init__(self)
        self.i = 0
        self.isStop = threading.Event()
        self.pauseload = threading.Event()
        self.cond = {}
        self.userdb = userdb
        self.globals = globals
        self.changeNotiTime = {}
        self.num_no_data = {}
        self.error = {}
        # self.thislock = threading.Lock()

    @staticmethod
    def format_results(poslist, times):
        symbol = []
        size = []
        entry_price = []
        mark_price = []
        pnl = []
        margin = []
        calculatedMargin = []
        times = datetime.utcfromtimestamp(times / 1000).strftime('%Y-%m-%d %H:%M:%S')
        for dt in poslist:
            symbol.append(dt['symbol'])
            size.append(dt['amount'])
            entry_price.append(dt['entryPrice'])
            mark_price.append(dt['markPrice'])
            pnl.append(f"{round(dt['pnl'], 2)} ({round(dt['roe'] * 100, 2)}%)")
            percentage = dt['roe']
            if float(dt['entryPrice']) == 0:
                margin.append("nan")
                calculatedMargin.append(False)
                continue
            price = (
                            float(dt['markPrice'])
                            - float(dt['entryPrice'])
                    ) / float(dt['entryPrice'])
            if percentage == 0 or price == 0:
                margin.append("nan")
                calculatedMargin.append(False)
            else:
                estimated_margin = abs(round(percentage / price))
                calculatedMargin.append(True)
                margin.append(str(estimated_margin) + "x")
        dictx = {
            "symbol": symbol,
            "size": size,
            "Entry Price": entry_price,
            "Mark Price": mark_price,
            "PNL (ROE%)": pnl,
            "Estimated Margin": margin,
        }
        df = pd.DataFrame(dictx)
        return {"time": times, "data": df}, calculatedMargin

    def changes(self, df, df2):
        txtype = []
        txsymbol = []
        txsize = []
        executePrice = []
        isClosedAll = []
        is_new_position = []
        profit = []
        if (isinstance(df, str) or df is None) and (
                isinstance(df2, str) or df2 is None
        ):
            return None
        if isinstance(df, str):
            for index, row in df2.iterrows():
                size = row["size"]
                if isinstance(size, str):
                    size = size.replace(",", "")
                size = float(size)
                if size > 0:
                    txtype.append("OpenLong")
                    txsymbol.append(row["symbol"])
                    txsize.append(size)
                    executePrice.append(row["Entry Price"])
                    isClosedAll.append(False)
                    is_new_position.append(True)
                    profit.append(0)
                else:
                    txtype.append("OpenShort")
                    txsymbol.append(row["symbol"])
                    txsize.append(size)
                    executePrice.append(row["Entry Price"])
                    isClosedAll.append(False)
                    is_new_position.append(True)
                    profit.append(0)
            txs = pd.DataFrame(
                {
                    "txtype": txtype,
                    "symbol": txsymbol,
                    "size": txsize,
                    "ExecPrice": executePrice,
                    "isClosedAll": isClosedAll,
                    "is_new_position": is_new_position,
                    "profit": profit,
                }
            )
        elif isinstance(df2, str):
            for index, row in df.iterrows():
                size = row["size"]
                if isinstance(size, str):
                    size = size.replace(",", "")
                size = float(size)
                if size > 0:
                    txtype.append("CloseLong")
                    txsymbol.append(row["symbol"])
                    txsize.append(-size)
                    executePrice.append(row["Mark Price"])
                    isClosedAll.append(True)
                    is_new_position.append(False)
                    profit.append(size * ((float(row["Mark Price"])) - float(row["Entry Price"])))
                else:
                    txtype.append("CloseShort")
                    txsymbol.append(row["symbol"])
                    txsize.append(-size)
                    executePrice.append(row["Mark Price"])
                    isClosedAll.append(True)
                    is_new_position.append(False)
                    profit.append(-size * ((float(row["Mark Price"])) - float(row["Entry Price"])))
            txs = pd.DataFrame(
                {
                    "txtype": txtype,
                    "symbol": txsymbol,
                    "size": txsize,
                    "ExecPrice": executePrice,
                    "isClosedAll": isClosedAll,
                    "is_new_position": is_new_position,
                    "profit": profit,
                }
            )
        else:
            df, df2 = df.copy(), df2.copy()
            for index, row in df.iterrows():
                hasChanged = False
                temp = df2["symbol"] == row["symbol"]
                idx = df2.index[temp]
                size = row["size"]
                if isinstance(size, str):
                    size = size.replace(",", "")
                size = float(size)
                oldentry = row["Entry Price"]
                if isinstance(oldentry, str):
                    oldentry = oldentry.replace(",", "")
                oldentry = float(oldentry)
                oldmark = row["Mark Price"]
                if isinstance(oldmark, str):
                    oldmark = oldmark.replace(",", "")
                oldmark = float(oldmark)
                isPositive = size >= 0
                for r in idx:
                    df2row = df2.loc[r].values
                    newsize = df2row[1]
                    if isinstance(newsize, str):
                        newsize = newsize.replace(",", "")
                    newsize = float(newsize)
                    newentry = df2row[2]
                    if isinstance(newentry, str):
                        newentry = newentry.replace(",", "")
                    newentry = float(newentry)
                    newmark = df2row[3]
                    if isinstance(newmark, str):
                        newmark = newmark.replace(",", "")
                    newmark = float(newmark)
                    if newsize == size:
                        df2 = df2.drop(r)
                        hasChanged = True
                        break
                    if isPositive and newsize > 0:
                        changesize = newsize - size
                        if abs(changesize) < 1e-7:
                            df2 = df2.drop(r)
                            hasChanged = True
                            break
                        if changesize > 0:
                            txtype.append("OpenLong")
                            txsymbol.append(df2row[0])
                            txsize.append(changesize)
                            isClosedAll.append(False)
                            is_new_position.append(False)
                            profit.append(0)
                            try:
                                exp = (
                                              newentry * newsize - oldentry * size
                                      ) / changesize
                            except:
                                exp = 0
                            if changesize / newsize < 0.05:
                                executePrice.append(newmark)
                            else:
                                executePrice.append(exp)
                        else:
                            txtype.append("CloseLong")
                            txsymbol.append(df2row[0])
                            txsize.append(changesize)
                            executePrice.append(newmark)
                            isClosedAll.append(False)
                            is_new_position.append(False)
                            profit.append(abs(changesize) * (newmark - newentry))
                        df2 = df2.drop(r)
                        hasChanged = True
                        break
                    if not isPositive and newsize < 0:
                        changesize = newsize - size
                        if abs(changesize) < 1e-7:
                            df2 = df2.drop(r)
                            hasChanged = True
                            break
                        if changesize > 0:
                            txtype.append("CloseShort")
                            txsymbol.append(df2row[0])
                            txsize.append(changesize)
                            executePrice.append(newmark)
                            isClosedAll.append(False)
                            is_new_position.append(False)
                            profit.append(-abs(changesize) * (newmark - newentry))
                        else:
                            txtype.append("OpenShort")
                            txsymbol.append(df2row[0])
                            txsize.append(changesize)
                            isClosedAll.append(False)
                            is_new_position.append(False)
                            profit.append(0)
                            try:
                                exp = (
                                              newentry * newsize - oldentry * size
                                      ) / changesize
                            except:
                                exp = 0
                            if changesize / newsize < 0.05:
                                executePrice.append(newmark)
                            else:
                                executePrice.append(exp)
                        df2 = df2.drop(r)
                        hasChanged = True
                        break
                if not hasChanged:
                    if size > 0:
                        txtype.append("CloseLong")
                        txsymbol.append(row["symbol"])
                        txsize.append(-size)
                        executePrice.append(oldmark)
                        isClosedAll.append(True)
                        is_new_position.append(False)
                        profit.append(abs(size) * (oldmark - oldentry))
                    else:
                        txtype.append("CloseShort")
                        txsymbol.append(row["symbol"])
                        txsize.append(-size)
                        executePrice.append(oldmark)
                        isClosedAll.append(True)
                        is_new_position.append(False),
                        profit.append(-abs(size) * (oldmark - oldentry))

            for index, row in df2.iterrows():
                size = row["size"]
                if isinstance(size, str):
                    size = size.replace(",", "")
                size = float(size)
                if size > 0:
                    txtype.append("OpenLong")
                    txsymbol.append(row["symbol"])
                    txsize.append(size)
                    executePrice.append(row["Entry Price"])
                    isClosedAll.append(False)
                    is_new_position.append(True)
                    profit.append(0)
                else:
                    txtype.append("OpenShort")
                    txsymbol.append(row["symbol"])
                    txsize.append(size)
                    executePrice.append(row["Entry Price"])
                    isClosedAll.append(False)
                    is_new_position.append(True)
                    profit.append(0)

            txs = pd.DataFrame(
                {
                    "txType": txtype,
                    "symbol": txsymbol,
                    "size": txsize,
                    "ExecPrice": executePrice,
                    "isClosedAll": isClosedAll,
                    "is_new_position": is_new_position,
                    "profit": profit,
                }
            )
        return txs  # add this to open trade part

    def position_changes(self, positions, times, uid, prev_df, name, lasttime):
        following_users = self.userdb.fetch_following(uid)
        try:
            prev_position = self.userdb.fetch_trader_position(uid)
        except:
            logger.info(f"{uid} Cannot get past positions.")
            return
        if len(positions) == 0:
            self.num_no_data[uid] = (
                1 if uid not in self.num_no_data else self.num_no_data[uid] + 1
            )
            if self.num_no_data[uid] > 35:
                self.num_no_data[uid] = 4
            if self.num_no_data[uid] >= 3 and prev_position != "x":
                logger.info(f"{name} Change to no position.")
                # self.changeNotiTime[uid] = datetime.now()
                now = datetime.now() + timedelta(hours=8)
                # self.lastPosTime = datetime.now() + timedelta(hours=8)
                tosend = (
                        f"Trader {name}, Current time: " + str(now) + "\nNo positions.\n"
                )
                txlist = self.changes(prev_df, "x")
                table = prettytable.PrettyTable(
                    ["Type", "Symbol", "Size", "ExecPrice", "isClosedAll", "PNL"])
                numrows = txlist.shape[0]
                for i in range(0, numrows):
                    table.add_row([
                        txlist['txtype'][i],
                        txlist["symbol"][i],
                        f'{txlist["size"][i]:.2f}',
                        f'{txlist["ExecPrice"][i]:.3f}',
                        txlist["isClosedAll"][i],
                        txlist["profit"][i],
                    ])

                for users in following_users:
                    self.userdb.insert_command(
                        {
                            "cmd": "send_message",
                            "chat_id": users["chat_id"],
                            "message": tosend,
                        }
                    )
                    if users['traders'][uid]["toTrade"]:
                        tosend = "Making the following trades: \n" + f'```{table}```'
                        self.userdb.insert_command(
                            {
                                "cmd": "send_message",
                                "chat_id": users["chat_id"],
                                "message": tosend,
                                "parse_mode": ParseMode.MARKDOWN_V2
                            }
                        )
                        retries = 0
                        while retries < 3:
                            try:
                                client = BinanceUMFuturesClient(
                                    users["chat_id"],
                                    users["uname"],
                                    users["safety_ratio"],
                                    users["api_key"],
                                    users["api_secret"],
                                    users["slippage"],
                                    self.globals,
                                    self.userdb,
                                )
                                client.open_trade(
                                    txlist,
                                    uid,
                                    users["traders"][uid]["proportion"],
                                    users["leverage"],
                                    users["tp"],
                                    users["sl"],
                                    users["traders"][uid]["tmode"],
                                    users["traders"][uid]["positions"],
                                    users["slippage"],
                                )
                                del client
                                break
                            except Exception as e:
                                retries += 1
                                logger.exception(f"Can not open trade, retries={retries} detail: {e}")
                self.userdb.save_position(uid, "x", True)
            elif self.num_no_data[uid] >= 3:
                self.userdb.save_position(uid, "x", False)
            # diff = datetime.now() - datetime.strptime(lasttime, "%y-%m-%d %H:%M:%S")
            # if diff.total_seconds() / 3600 >= 24:
            #     for users in following_users:
            #         self.userdb.insert_command(
            #             {
            #                 "cmd": "send_message",
            #                 "chat_id": users["chat_id"],
            #                 "message": f"Trader {name}: 24 hours no position update.",
            #             }
            #         )
        else:
            self.num_no_data[uid] = 0
            try:
                output, calmargin = self.format_results(positions, times)
            except Exception as e:
                logger.exception(f"Trader {name} may not share position anymore.")
                return
            if prev_position == "x":
                isChanged = True
                txlist = self.changes(prev_position, output["data"])
            else:
                prev_position = pd.read_json(prev_position)
                try:
                    toComp = output["data"][["symbol", "size", "Entry Price"]]
                    prevdf = prev_position[["symbol", "size", "Entry Price"]]
                except Exception as e:
                    logger.exception(str(e))
                if not toComp.equals(prevdf):
                    txlist = self.changes(prev_position, output["data"])
                    if not txlist.empty:
                        isChanged = True
                    else:
                        isChanged = False
                else:
                    isChanged = False
            if isChanged:
                logger.info(f"{name} changed positions.")
                now = datetime.now() + timedelta(hours=8)
                self.lastPosTime = datetime.now() + timedelta(hours=8)
                numrows = output["data"].shape[0]
                table = prettytable.PrettyTable(
                    ["Symbol", "Type", "Size", "Entry", "Mark price", "Lev", "PNL (ROE%)"])
                if numrows > 0:
                    for i in range(0, numrows):
                        table.add_row([
                            output['data']["symbol"][i],
                            "LONG" if output["data"]['size'][i] > 0 else "SHORT",
                            f'{output["data"]["size"][i]:.2f}',
                            f'{output["data"]["Entry Price"][i]:.3f}',
                            f'{output["data"]["Mark Price"][i]:.3f}',
                            output["data"]["Estimated Margin"][i],
                            output["data"]["PNL (ROE%)"][i],
                        ])
                    for users in following_users:
                        self.userdb.insert_command({
                            "cmd": "send_message",
                            "chat_id": users["chat_id"],
                            "message": f'{name} has changed positions: \n```{table}```',
                            "parse_mode": ParseMode.MARKDOWN_V2
                        })
                for users in following_users:
                    if users["traders"][uid]["toTrade"] and not txlist.empty:
                        tosend = "Making the following trades: \n" + f'```{table}```'
                        self.userdb.insert_command(
                            {
                                "cmd": "send_message",
                                "chat_id": users["chat_id"],
                                "message": tosend,
                                "parse_mode": ParseMode.MARKDOWN_V2
                            }
                        )
                        retries = 0
                        while retries < 3:
                            try:
                                client = BinanceUMFuturesClient(
                                    users["chat_id"],
                                    users["uname"],
                                    users["safety_ratio"],
                                    users["api_key"],
                                    users["api_secret"],
                                    users["slippage"],
                                    self.globals,
                                    self.userdb,
                                )
                                client.open_trade(
                                    txlist,
                                    uid,
                                    users["traders"][uid]["proportion"],
                                    users["leverage"],
                                    users["tp"],
                                    users["sl"],
                                    users["traders"][uid]["tmode"],
                                    users["traders"][uid]["positions"],
                                    users["slippage"],
                                )
                                del client
                                break
                            except Exception as e:
                                retries += 1
                                logger.exception(str(e))
                self.userdb.save_position(uid, output["data"].to_json(), True)
            else:
                self.userdb.save_position(uid, output["data"].to_json(), False)
        self.first_run = False
        # diff = datetime.now() - datetime.strptime(lasttime, "%y-%m-%d %H:%M:%S")
        # if diff.total_seconds() / 3600 >= 24:
        #     for users in following_users:
        #         self.userdb.insert_command(
        #             {
        #                 "cmd": "send_message",
        #                 "chat_id": users["chat_id"],
        #                 "message": f"Trader {self.name}: 24 hours no position update.",
        #             }
        #         )

    def run(self):  # get the positions
        while not self.isStop.is_set():
            if self.pauseload.is_set():
                time.sleep(5)
                continue
            # try:
            urls = self.userdb.retrieve_traders()
            for uid in urls:
                time.sleep(0.5)
                try:
                    r = requests.post(
                        BINANCE_LEADER_BOARD_URL_V1,
                        json={
                            "encryptedUid": uid['uid'],
                            "tradeType": const.PERPETUAL
                        })
                    assert r.status_code == 200
                    positions = r.json()['data']['otherPositionRetList']
                    times = r.json()['data']['updateTimeStamp']
                    assert positions is not None
                    self.error[uid['uid']] = 0
                except:
                    logger.exception(f"{uid['name']} cannot fetch url")
                    following_users = self.userdb.fetch_following(uid['uid'])
                    if uid['uid'] not in self.error:
                        self.error[uid['uid']] = 1
                    else:
                        self.error[uid['uid']] += 1
                        if self.error[uid['uid']] >= 20:
                            self.error[uid['uid']] = 11
                    if 5 <= self.error[uid['uid']] <= 10:
                        for users in following_users:
                            self.userdb.insert_command(
                                {
                                    "cmd": "send_message",
                                    "chat_id": users["chat_id"],
                                    "message": f"Trader {uid['name']}: May have stopped sharing positions!",
                                }
                            )
                    continue
                if uid["positions"] != "x":
                    prevpos = pd.read_json(uid["positions"])
                else:
                    prevpos = "x"
                self.position_changes(
                    positions, times, uid["uid"], prevpos, uid["name"], uid["lastPosTime"]
                )
            time.sleep(3)

    def stop(self):
        self.isStop.set()

    def pause(self):
        self.pauseload.set()

    def resume(self):
        self.pauseload.clear()
