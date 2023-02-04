from datetime import datetime, timedelta
from datetime import time as timed
import math
import threading
import logging

from binance.um_futures import UMFutures

from app.config import const
import time
from pybit.usdt_perpetual import HTTP
import pandas as pd
import urllib.parse

from app.copy_trade_backend.ct_binance import BinanceUMFuturesClient
from app.data.credentials import db_host, db_user, db_pw, db_port

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


class ctGlobal:
    def __init__(self):
        self.stopevent = threading.Event()
        self.dblock = threading.Lock()
        self.apilock = threading.Lock()
        self.past_balances = dict()
        self.has_announced = dict()
        username = urllib.parse.quote_plus(db_user)
        password = urllib.parse.quote_plus(db_pw)
        self.dbpath = f"mongodb://{username}:{password}@{db_host}:{db_port}/"
        logger.info(self.dbpath)
        return

    def round_up(self, n, decimals=0):
        multiplier = 10 ** decimals
        return math.ceil(n * multiplier) / multiplier

    def reload_symbols(self, userdb):
        client = UMFutures()
        exchanges = client.exchange_info()
        for user in userdb.retrieve_users():
            new_lev = {}
            for sym in exchanges['symbols']:
                # Currently only support PERPETUAL and USDT
                if sym['contractType'] == const.PERPETUAL and sym['quoteAsset'] == 'USDT':
                    if sym['symbol'] in user["leverage"]:
                        new_lev[sym['symbol']] = user["leverage"][sym['symbol']]
                    else:
                        new_lev[sym['symbol']] = user["leverage"]["XRPUSDT"]
                        userdb.insert_command(
                            {
                                "cmd": "send_message",
                                "chat_id": user["chat_id"],
                                "message": f"There is a new symbol {sym['symbol']} available,"
                                           f"you might want to adjust its settings.",
                            }
                        )
            userdb.update_leverage(user["chat_id"], new_lev)
            for trader in user["traders"]:
                new_prop = {}
                for sym in exchanges['symbols']:
                    if sym['contractType'] == const.PERPETUAL and sym['quoteAsset'] == 'USDT':
                        if sym['symbol'] in user["traders"][trader]["proportion"]:
                            new_prop[sym['symbol']] = user["traders"][trader]["proportion"][sym['symbol']]
                        else:
                            new_prop[sym['symbol']] = user["traders"][trader]["proportion"]["XRPUSDT"]
                userdb.update_proportion(user["chat_id"], trader, new_prop)

    def check_noti(self, userdb):
        while not self.stopevent.is_set():
            time.sleep(3)
            allnoti = userdb.get_noti()
            todelete = []
            for noti in allnoti:
                if noti["cmd"] == "delete_and_closeall":
                    chat_id = noti["user"]
                    uid = noti["trader"]
                    user = userdb.get_user(chat_id)
                    if "positions" not in user["traders"][uid]:
                        del user["traders"][uid]
                        userdb.update_user(chat_id, user)
                    else:
                        all_positions = user["traders"][uid]["positions"]
                        # bla bla bla: closing position
                        client = BinanceUMFuturesClient(
                            chat_id,
                            user["uname"],
                            user["safety_ratio"],
                            user["api_key"],
                            user["api_secret"],
                            user["slippage"],
                            self,
                            userdb,
                        )
                        txtype, txsymbol, txsize, execprice, isClosedAll = (
                            [],
                            [],
                            [],
                            [],
                            [],
                        )
                        for pos in all_positions:
                            if pos[-4:].upper() == "LONG":
                                txtype.append("CloseLong")
                                symbol = pos[:-4]
                            else:
                                txtype.append("CloseShort")
                                symbol = pos[:-5]
                            txsymbol.append(symbol)
                            mark_price = client.client.mark_price(symbol=symbol)
                            execprice.append(float(mark_price['markPrice']))
                            txsize.append(float(all_positions[pos]))
                            isClosedAll.append(True)
                        txs = pd.DataFrame(
                            {
                                "txtype": txtype,
                                "symbol": txsymbol,
                                "size": txsize,
                                "ExecPrice": execprice,
                                "isClosedAll": isClosedAll,
                            }
                        )
                        prop = user["traders"][uid]["proportion"]
                        for key in prop:
                            prop[key] = 1
                        client.open_trade(
                            txs,
                            uid,
                            prop,
                            user["leverage"],
                            user["tp"],
                            user["sl"],
                            user["traders"][uid]["tmode"],
                            user["traders"][uid]["positions"],
                            user["slippage"],
                            True
                        )
                        del user["traders"][uid]
                        userdb.update_user(chat_id, user)
                        userdb.insert_command(
                            {
                                "cmd": "send_message",
                                "chat_id": chat_id,
                                "message": f"Successfully deleted trader!",
                            }
                        )
                todelete.append(noti["_id"])
            userdb.delete_command(todelete)
