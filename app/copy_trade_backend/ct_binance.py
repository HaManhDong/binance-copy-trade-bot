import math
import threading
import time
import logging
import pandas as pd
import os
import signal
import json

import requests
from binance.um_futures import UMFutures
from binance.error import ClientError

from app.config.const import PositionSide, OrderType, OrderSide, TimeInForce, OrderStatus, MAX_POSITIONS, DEFAULT_TP, \
    DEFAULT_SL

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


def round_up(n, decimals=0):
    multiplier = 10 ** decimals
    return math.ceil(n * multiplier) / multiplier


class BinanceUMFuturesClient:
    def __init__(self, chat_id, uname, safety_ratio, key, secret, slippage, glb, udb):
        self.chat_id = chat_id
        self.uname = uname
        self.safety_ratio = safety_ratio
        self.key = key
        self.secret = secret
        self.client = UMFutures(key=key, secret=secret)
        self.globals = glb
        self.userdb = udb
        self.step_size = {}
        self.tick_size = {}
        exchanges = self.client.exchange_info()
        for symbol in exchanges["symbols"]:
            for filter in symbol["filters"]:
                if filter["filterType"] == "PRICE_FILTER":
                    self.tick_size[symbol["symbol"]] = round(
                        -math.log(float(filter["tickSize"]), 10)
                    )
                elif filter["filterType"] == "LOT_SIZE":
                    self.step_size[symbol["symbol"]] = round(
                        -math.log(float(filter["stepSize"]), 10)
                    )

    def get_order(self):
        orders = self.client.get_orders()
        return orders

    def tpsl_trade(self, symbol, side, qty, excprice, leverage, tp, sl, positionSide):
        # make sure everything in numbers not text//side: original side
        logger.info(f"Debug Check Lev: {leverage} / TP: {tp} / SL: {sl}")
        if side == OrderSide.BUY:
            if tp != -1:
                tpPrice1 = excprice * (1 + (tp / leverage) / 100)
                qty1 = "{:0.0{}f}".format(qty, self.step_size[symbol])
                tpPrice1 = "{:0.0{}f}".format(tpPrice1, self.tick_size[symbol])
                try:
                    self.client.new_order(
                        side=side,
                        symbol=symbol,
                        type=OrderType.LIMIT,
                        quantity=str(qty1),
                        timeInForce=TimeInForce.GTC,
                        positionSide=positionSide,
                        price=tpPrice1
                    )
                except Exception as e:
                    logger.error(f"Error in set TP: {e}")
            if sl != -1:
                tpPrice2 = excprice * (1 - (sl / leverage) / 100)
                qty2 = "{:0.0{}f}".format(qty, self.step_size[symbol])
                tpPrice2 = "{:0.0{}f}".format(tpPrice2, self.tick_size[symbol])
                try:
                    self.client.new_order(
                        side=side,
                        symbol=symbol,
                        type=OrderType.LIMIT,
                        quantity=str(qty2),
                        timeInForce=TimeInForce.GTC,
                        positionSide=positionSide,
                        price=tpPrice2
                    )
                except Exception as e:
                    logger.error(f"Error in set SL: {e}")
        else:
            if tp != -1:
                tpPrice1 = excprice * (1 - (tp / leverage) / 100)
                qty1 = "{:0.0{}f}".format(qty, self.step_size[symbol])
                tpPrice1 = "{:0.0{}f}".format(tpPrice1, self.tick_size[symbol])
                try:
                    self.client.new_order(
                        side=side,
                        symbol=symbol,
                        type=OrderType.LIMIT,
                        quantity=str(qty1),
                        timeInForce=TimeInForce.GTC,
                        positionSide=positionSide,
                        price=tpPrice1
                    )
                except Exception as e:
                    logger.error(f"Error in set TP: {e}")
            if sl != -1:
                tpPrice2 = excprice * (1 + (sl / leverage) / 100)
                qty2 = "{:0.0{}f}".format(qty, self.step_size[symbol])
                tpPrice2 = "{:0.0{}f}".format(tpPrice2, self.tick_size[symbol])
                try:
                    self.client.new_order(
                        side=side,
                        symbol=symbol,
                        type=OrderType.LIMIT,
                        quantity=str(qty2),
                        timeInForce=TimeInForce.GTC,
                        positionSide=positionSide,
                        price=tpPrice2
                    )
                except Exception as e:
                    logger.error(f"Error in set SL: {e}")
        return

    def query_trade(self, orderId, symbol, positionKey, isOpen, uname,
                    takeProfit, stopLoss, leverage, positionSide, ref_price, uid, todelete):
        numTries = 0
        time.sleep(1)
        executed_qty = 0
        while True:
            try:
                order = self.client.query_order(symbol=symbol, orderId=orderId)
                if order["status"] == OrderStatus.FILLED:
                    if ref_price != -1:
                        executed_price = float(order["avgPrice"])
                        diff = abs(executed_price - ref_price)
                        slippage = diff / ref_price * 100
                        self.userdb.insert_command(
                            {
                                "cmd": "send_message",
                                "chat_id": self.chat_id,
                                "message": f"Order ID {orderId} ({positionKey}) fulfilled successfully. "
                                           f"The slippage is {slippage:.2f}%.",
                            }
                        )
                    else:
                        self.userdb.insert_command(
                            {
                                "cmd": "send_message",
                                "chat_id": self.chat_id,
                                "message": f"Order ID {orderId} ({positionKey}) fulfilled successfully.",
                            }
                        )
                    if todelete:
                        return
                    resultqty = round(abs(float(order["executedQty"])), 3)
                    resultqty = -resultqty if positionSide == PositionSide.SHORT else resultqty
                    # ADD TO POSITION
                    if isOpen:
                        self.userdb.update_positions(
                            self.chat_id, uid, positionKey, resultqty, 1
                        )
                        try:
                            self.tpsl_trade(
                                symbol,
                                order["side"],
                                float(order["executedQty"]),
                                float(order["avgPrice"]),
                                leverage,
                                takeProfit,
                                stopLoss,
                                positionSide
                            )
                        except:
                            pass
                    else:
                        self.userdb.update_positions(
                            self.chat_id, uid, positionKey, resultqty, 2
                        )
                    return
                elif order["status"] in [OrderStatus.REJECTED, OrderStatus.CANCELED]:
                    self.userdb.insert_command(
                        {
                            "cmd": "send_message",
                            "chat_id": self.chat_id,
                            "message": f"Order ID {orderId} ({positionKey}) is cancelled/rejected.",
                        }
                    )
                    return
                elif order["status"] == OrderStatus.PARTIALLY_FILLED:
                    updatedQty = float(order["executedQty"]) - executed_qty
                    updatedQty = -updatedQty if positionSide == PositionSide.SHORT else updatedQty
                    if todelete:
                        continue
                    if isOpen:
                        self.userdb.update_positions(
                            self.chat_id, uid, positionKey, updatedQty, 1
                        )
                    else:
                        self.userdb.update_positions(
                            self.chat_id, uid, positionKey, updatedQty, 2
                        )
                    executed_qty = float(order["executedQty"])
            except Exception as e:
                logger.exception(f"Can't query trade, detail: {e}")
            if numTries >= 15:
                break
            time.sleep(60)
            numTries += 1

    # txlist:
    #   'txType', 'symbol', 'size', 'ExecPrice', 'isClosedAll'
    #   CloseLong, BTCUSDT, -380.30000, 12.89657, True
    #   OpenLong, APTUSDT, 380.30000, 13.21451, False
    def open_trade(self, txlist, uid, proportion, leverage, tmodes, positions, slippage, todelete=False):
        df = txlist.values
        i = -1
        for tradeinfo in df:
            symbol = tradeinfo[1]
            is_closed_all = tradeinfo[4]
            i += 1
            types = tradeinfo[0].upper()
            if symbol not in proportion:
                self.userdb.insert_command(
                    {
                        "cmd": "send_message",
                        "chat_id": self.chat_id,
                        "message": f"This trade will not be executed since {symbol} is not a valid symbol.",
                    }
                )
                continue
            coin = "USDT"
            if types[:4] == "OPEN":
                is_open = True
                positionSide = types[4:]
                if positionSide == "LONG":
                    side = OrderSide.BUY
                else:
                    side = OrderSide.SELL
                try:
                    self.client.change_leverage(symbol=symbol, leverage=leverage[symbol])
                except Exception as e:
                    logger.error(f"Leverage error {str(e)}")
                    pass
            else:
                is_open = False
                positionSide = types[5:]
                if positionSide == "LONG":
                    side = OrderSide.SELL
                else:
                    side = OrderSide.BUY
            check_key = symbol + positionSide
            if isinstance(tradeinfo[3], str):
                exec_price = float(tradeinfo[3].replace(",", ""))
            else:
                exec_price = float(tradeinfo[3])

            # Check number of positions
            current_positions = 0
            potisions = self.client.get_position_risk()
            for pos in potisions:
                if float(pos["notional"]) != 0:
                    current_positions += 1
            if current_positions > MAX_POSITIONS:
                self.userdb.insert_command(
                    {
                        "cmd": "send_message",
                        "chat_id": self.chat_id,
                        "message": f"You're having {current_positions} positions currently, "
                                   f"that reach MAX_POSITIONS={MAX_POSITIONS}. You need to adjust MAX_POSITIONS.",
                    }
                )
                continue

            # Get balance
            usdt_balance = 0
            usdt_available = 0
            balances = self.client.balance()
            for balance in balances:
                if balance['asset'] == "USDT":
                    usdt_balance = float(balance['balance'])
                    usdt_available = float(balance['availableBalance'])
                    break

            # Calculate quant
            usdt_trade = proportion[symbol] * usdt_balance / 100
            quant = usdt_trade * leverage[symbol] / exec_price
            if not is_open and (
                    (is_open not in positions) or (positions[check_key] == 0)):
                self.userdb.insert_command(
                    {
                        "cmd": "send_message",
                        "chat_id": self.chat_id,
                        "message": f"Close {check_key}: This trade will not be executed "
                                   f"because your opened positions with this strategy is 0.",
                    }
                )
                continue
            if quant == 0:
                self.userdb.insert_command(
                    {
                        "cmd": "send_message",
                        "chat_id": self.chat_id,
                        "message": f"{side} {check_key}: This trade will not be executed "
                                   f"because size = 0 or your available USDT = 0. "
                                   f"Adjust proportion if you want to follow.",
                    }
                )
                continue
            mark_price = self.client.mark_price(symbol=symbol)
            latest_price = float(mark_price['markPrice'])
            if abs(latest_price - exec_price) / exec_price > slippage and is_open:
                self.userdb.insert_command(
                    {
                        "cmd": "send_message",
                        "chat_id": self.chat_id,
                        "message": f"The execute price of {tradeinfo[1]} is {exec_price},"
                                   f"but the current price is {latest_price}, "
                                   f"which is over the preset slippage of {slippage}. "
                                   f"The trade will not be executed.",
                    }
                )
                continue
            req_tick_size = self.tick_size[symbol]
            req_step_size = self.step_size[symbol]
            if not is_open and is_closed_all:
                if abs(positions[check_key]) > abs(quant):
                    quant = abs(positions[check_key])
            collateral = (latest_price * quant) / leverage[symbol]
            quant = round_up(quant, req_step_size)
            quant = str(quant)
            if is_open:
                self.userdb.insert_command(
                    {
                        "cmd": "send_message",
                        "chat_id": self.chat_id,
                        "message": f"For the following trade, you will need {collateral:.3f}{coin} as collateral.",
                    }
                )
                if collateral >= usdt_available * self.safety_ratio:
                    self.userdb.insert_command(
                        {
                            "cmd": "send_message",
                            "chat_id": self.chat_id,
                            "message": f"WARNING: this trade will take up more than {self.safety_ratio} of your "
                                       f"available balance. It will NOT be executed. "
                                       f"Manage your risks accordingly and reduce proportion if necessary.",
                        }
                    )
                    continue
            if tmodes[symbol] == 0 or (tmodes[symbol] == 2 and not is_open):
                try:
                    tosend = f"Trying to execute the following trade:\n" \
                             f"Symbol: {tradeinfo[1]}\nSide: {side}\n" \
                             f"positionSide: {positionSide}\ntype: MARKET\n" \
                             f"quantity: {quant}\nusdt: {usdt_trade:2f}"
                    self.userdb.insert_command(
                        {
                            "cmd": "send_message",
                            "chat_id": self.chat_id,
                            "message": tosend,
                        }
                    )
                    response = self.client.new_order(
                        side=side,
                        symbol=symbol,
                        type=OrderType.MARKET,
                        quantity=str(quant),
                        positionSide=positionSide
                    )
                    self.userdb.insert_command({
                        "cmd": "send_message",
                        "chat_id": self.chat_id,
                        "message": f"Order was opened successfully!!!",
                    })
                    t1 = threading.Thread(
                        target=self.query_trade,
                        args=(
                            response["orderId"],
                            symbol,
                            check_key,
                            is_open,
                            self.uname,
                            DEFAULT_TP,
                            DEFAULT_SL,
                            leverage[symbol],
                            positionSide,
                            -1,
                            uid,
                            todelete
                        ),
                    )
                    t1.start()
                except Exception as e:
                    if e.error_message == 'ReduceOnly Order is rejected.':
                        self.userdb.update_positions(
                            self.chat_id, uid, check_key, 0, 0
                        )
                        self.userdb.insert_command(
                            {
                                "cmd": "send_message",
                                "chat_id": self.chat_id,
                                "message": "Your opened position is 0, no positions has been closed.",
                            }
                        )
                        logger.warning(f"Position of {self.chat_id} is 0, no positions has been closed.")
                    else:
                        logger.exception("Have error when open Market order!!")

            else:
                if isinstance(tradeinfo[3], str):
                    tradeinfo[3] = tradeinfo[3].replace(",", "")
                target_price = float(tradeinfo[3])
                target_price = "{:0.0{}f}".format(target_price, req_tick_size)
                try:
                    tosend = f"Trying to execute the following trade:\nSymbol: {tradeinfo[1]}\nSide: {side}\n" \
                             f"type: LIMIT\nquantity: {quant}\nusdt: {usdt_trade:2f}\nPrice: {target_price}"
                    self.userdb.insert_command({
                        "cmd": "send_message",
                        "chat_id": self.chat_id,
                        "message": tosend,
                    })
                    response = self.client.new_order(
                        side=side,
                        symbol=symbol,
                        type=OrderType.LIMIT,
                        quantity=str(quant),
                        timeInForce=TimeInForce.GTC,
                        positionSide=positionSide,
                        price=target_price
                    )
                    t1 = threading.Thread(
                        target=self.query_trade,
                        args=(
                            response["orderId"],
                            symbol,
                            check_key,
                            is_open,
                            self.uname,
                            DEFAULT_TP,
                            DEFAULT_SL,
                            leverage[symbol],
                            positionSide,
                            -1,
                            uid,
                            todelete
                        ),
                    )
                    t1.start()
                except Exception:
                    logger.exception("Have error when open LIMIT order!!")
