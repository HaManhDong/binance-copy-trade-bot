# User setting
DEFAULT_LEV = 5  # 5x
DEFAULT_PROPORTION = 0
DEFAULT_SLIPPAGE = 0.05
MAX_POSITIONS = 3
DEFAULT_SAFETY_RATIO = 1
DEFAULT_TP = -1
DEFAULT_SL = 50  # 50%

# Binance
BINANCE_LEADER_BOARD_URL_V1 = "https://www.binance.com/bapi/futures/v1/public/future/leaderboard/getOtherPosition"
BINANCE_LEADER_BOARD_URL_V2 = "https://www.binance.com/bapi/futures/v2/public/future/leaderboard/getOtherLeaderboardBaseInfo"
PERPETUAL = "PERPETUAL"


class CandlestickInterval:
    MIN1 = "1m"
    MIN3 = "3m"
    MIN5 = "5m"
    MIN15 = "15m"
    MIN30 = "30m"
    HOUR1 = "1h"
    HOUR2 = "2h"
    HOUR4 = "4h"
    HOUR6 = "6h"
    HOUR8 = "8h"
    HOUR12 = "12h"
    DAY1 = "1d"
    DAY3 = "3d"
    WEEK1 = "1w"
    MON1 = "1m"
    INVALID = None


class OrderSide:
    BUY = "BUY"
    SELL = "SELL"
    INVALID = None


class TimeInForce:
    GTC = "GTC"
    IOC = "IOC"
    FOK = "FOK"
    GTX = "GTX"
    INVALID = None


class TradeDirection:
    BUY = "buy"
    SELL = "sell"
    INVALID = None


class OrderType:
    LIMIT = "LIMIT"
    MARKET = "MARKET"
    STOP = "STOP"
    STOP_MARKET = "STOP_MARKET"
    TAKE_PROFIT = "TAKE_PROFIT"
    TAKE_PROFIT_MARKET = "TAKE_PROFIT_MARKET"
    TRAILING_STOP_MARKET = "TRAILING_STOP_MARKET"
    INVALID = None


class OrderStatus:
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class OrderRespType:
    ACK = "ACK"
    RESULT = "RESULT"
    INVALID = None


class MatchRole:
    MAKER = "maker"
    TAKER = "taker"


class DepthStep:
    STEP0 = "step0"
    STEP1 = "step1"
    STEP2 = "step2"
    STEP3 = "step3"
    STEP4 = "step4"
    STEP5 = "step5"


class SubscribeMessageType:
    RESPONSE = "response"
    PAYLOAD = "payload"


class TransferType:
    ROLL_IN = "ROLL_IN"
    ROLL_OUT = "ROLL_OUT"
    INVALID = None


class WorkingType:
    MARK_PRICE = "MARK_PRICE"
    CONTRACT_PRICE = "CONTRACT_PRICE"
    INVALID = None


class FuturesMarginType:
    ISOLATED = "ISOLATED"
    CROSSED = "CROSSED"


class PositionSide:
    BOTH = "BOTH"
    LONG = "LONG"
    SHORT = "SHORT"
    INVALID = None


class IncomeType:
    TRANSFER = "TRANSFER"
    WELCOME_BONUS = "WELCOME_BONUS"
    REALIZED_PNL = "REALIZED_PNL"
    FUNDING_FEE = "FUNDING_FEE"
    COMMISSION = "COMMISSION"
    INSURANCE_CLEAR = "INSURANCE_CLEAR"
    INVALID = None


class UpdateTime:
    NORMAL = ""
    FAST = "@100ms"
    REALTIME = "@0ms"
    INVALID = ""
