import json
import gemini
import boto3
import base64
from botocore.exceptions import ClientError
from math import log10, floor
from lambda_helpers import *

#FEE_FACTOR always at 0.999 to include the 0.1% maker order fee in your order price 
FEE_FACTOR = 0.999

def validate_event(event, defaults={}):
    options = apply_event_defaults(event, defaults)
    print("validating options: " + json.dumps(options))
    assert "currency" in options, REQUIRED_PARAM.format("currency")
    assert "amount" in options, REQUIRED_PARAM.format("amount")
    assert options["amount"] > 0, "Amount ({}) must be greater than zero".format(options["amount"])
    return options

def _get_exponent_from_details(options, detail_name):
    trader = gemini.PublicClient(options["sandbox"])
    currency_details = trader.symbol_details(options["currency"])
    #example: {"symbol":"BTCUSD","base_currency":"BTC","quote_currency":"USD","tick_size":1E-8,"quote_increment":0.01,"min_order_size":"0.00001","status":"open","wrap_enabled":false}
    assert type(currency_details) is dict
    assert detail_name in currency_details
    base10 = log10(abs(currency_details[detail_name]))
    exponent = abs(floor(base10)) 
    return exponent

def get_quote_increment(options):
    return _get_exponent_from_details(options, "quote_increment")

def get_tick_size(options):
    return _get_exponent_from_details(options, "tick_size")

def place_buy_order(options):
    trader = get_trader(options)
    spot_price = float(trader.get_ticker(options["currency"])['ask'])
    quote_increment = get_quote_increment(options)
    #to set a limit order at a fixed price (ie. $55,525) set execution_price = "55525.00" or execution_price = str(55525.00)
    execution_price = str(round(spot_price * options["orderFillFactor"], quote_increment))
    # get tick size
    tick_size = get_tick_size(options)
    #set amount to the most precise rounding (tick_size) and multiply by 0.999 for fee inclusion - if you make an order for $20.00 there should be $19.98 coin bought and $0.02 (0.1% fee)
    amount = str(round((options["amount"] * FEE_FACTOR) / float(execution_price), tick_size))
    #execute maker buy with the appropriate symbol (options["currency"]), amount, and calculated price
    buy_order = trader.new_order(options["currency"], amount, execution_price, "buy", ["maker-or-cancel"])
    return buy_order

def lambda_handler(event, context):
    response = http_error("Unknown Server Error", 500)
    try:
        """
        {
            "sandbox" : false,
            "currency": "BTCUSD",
            "amount": 10
        }
        """
        # get environment from event
        print("event recieved: " + json.dumps(event))
        options = validate_event(event)
        # place buy order
        buy_order = place_buy_order(options)
        print("buy order: " + json.dumps(buy_order))
        response = http_ok(buy_order)
    except Exception as e:
        response = http_error(str(e))

    return response
