#from asyncore import close_all
#from logging import exception
#from sre_constants import RANGE
import numpy as np
import pandas as pd
import config
import time
from config import API_KEY, SECRET_KEY
import ccxt
#import websocket, json
import sys
#*****************************************************
#ws = websocket.WebSocket()
#ws.connect("ws://localhost:9001")

exchange = ccxt.gate({
    'apiKey': config.API_KEY,
    'secret': config.SECRET_KEY,
    "options": {
        'defaultType': 'swap'
    }
})
#*****************************************************

# ****************************************************
LEVERAGE = 20
PARAMS = {"marginMode": "isolated"}
BUY_ORDERS = []
SELL_ORDERS  = []
CLOSED_ORDERS = []
CLOSED_ORDERS_IDS = []
STARTING_BALANCE = 1000
CURRENT_BALANCE = None
STOP_BALANCE = 1200
TAKE_PROFIT_BALANCE = 1600
THRESHOLD_POSITION = config.THRESHOLD_POSITION
#*******************************************************

# *****************  HELPER FUNCTIONS ****************** 
def create_buy_orders():
    for i in range(config.NUM_BUY_GRID_LINES):
        _, ask_price = fetch_latest_prices()
        price = ask_price - (config.GRID_SIZE * (i+1))
        print(f" ======== Submitting market limit buy order at ${price} ======== ")
        # Amount = 1 => actual size 0.01
        order = exchange.create_order(symbol=config.SYMBOL, type = "limit", side = "buy", amount = config.CONTRACT_SIZE, price = price, params = PARAMS)
        #print(order)
        BUY_ORDERS.append(order)

def create_sell_orders():
    for i in range(config.NUM_SELL_GRID_LINES):
        bid_price, _ = fetch_latest_prices()
        price = bid_price + (config.GRID_SIZE * (i+1))
        print(f" ======== Submitting market limit sell order at ${price} ======== ")
        order = exchange.create_order(symbol=config.SYMBOL, type = "limit", side = "sell", amount = config.CONTRACT_SIZE, price = price, params=PARAMS)
        SELL_ORDERS.append(order)

def fetch_latest_prices():
    ticker = exchange.fetch_order_book(config.SYMBOL)
    return float(ticker['bids'][0][0]), float(ticker['asks'][0][0])

def cancel_all_existing_orders():
    exchange.cancel_all_orders(symbol=config.SYMBOL)
    return

def check_buy_orders():
    if len(BUY_ORDERS) == 0:
        print(" ======== There are no buy orders currently. Creating the Buy Orders ======== ")
        create_buy_orders()
    else:
        print(' ======== Buy orders exist. Continue! ======== ')
    return 

def check_sell_orders():
    if len(SELL_ORDERS) == 0:
        print(" ======== There are no sell orders currently. Creating the Sell Orders ======== ")
        create_sell_orders()
    else:
        print(' ======== Sell orders exist. Continue! ======== ')

def check_open_buy_orders():
    for buy_order in BUY_ORDERS:
        print(f" ======== Checking Limit Buy Order {buy_order['info']['id']} ======== ")
        try:
            order = exchange.fetch_order(buy_order['id'])
        except:
            print(" ======= Request failed. Retrying ======= ")
            continue 

        if order['status'] == 'closed':
            CLOSED_ORDERS.append(order['info'])
            CLOSED_ORDERS_IDS.append(order['info']['id'])
            print(f" ======== Limit Buy Order was executed at {order['info']['price']} ======== ")
            #_, new_ask_price = fetch_latest_prices()
            #new_sell_price = new_ask_price + config.GRID_SIZE
            new_sell_price = float(order['info']['price']) + config.GRID_SIZE
            print(f" ************** Creating New Limit Sell Order at {new_sell_price} ***************** ")
            new_sell_order = exchange.create_order(symbol=config.SYMBOL, type = "limit", side = "sell", amount = config.CONTRACT_SIZE, price = new_sell_price, params = PARAMS)
            SELL_ORDERS.append(new_sell_order)
        

def check_open_sell_orders():
    for sell_order in SELL_ORDERS:
        print(f" ======== Checking Limit Sell Order {sell_order['info']['id']} ========")
        try:
            order = exchange.fetch_order(sell_order['id'])
        except:
            print(" ======== Request failed. Retrying ======== ")
            continue 
        #print(order)
        if order['status'] == 'closed':
            CLOSED_ORDERS.append(order['info'])
            CLOSED_ORDERS_IDS.append(order['info']['id'])
            print(f" ======== Limit Sell Order was executed at {order['info']['price']} ========")
            #new_bid_price, _ = fetch_latest_prices()
            #new_buy_price = new_bid_price - config.GRID_SIZE
            new_buy_price = float(order['info']['price']) - config.GRID_SIZE
            print(f" ************** Creating New Limit Buy Order at {new_buy_price} *************** ")
            new_buy_order = exchange.create_order(symbol=config.SYMBOL, type = "limit", side = "buy", amount = config.CONTRACT_SIZE, price = new_buy_price, params = PARAMS)
            BUY_ORDERS.append(new_buy_order)

def send_data():
    # Concatenate 3 order lists and send as jsonified
    #ws.send(json.dumps(BUY_ORDERS + SELL_ORDERS + CLOSED_ORDERS))
    return

def clear_order_lists():
    global BUY_ORDERS
    global SELL_ORDERS
    for order_id in CLOSED_ORDERS_IDS:
        BUY_ORDERS = [buy_order for buy_order in BUY_ORDERS if buy_order['info']['id'] != order_id]
        SELL_ORDERS = [sell_order for sell_order in SELL_ORDERS if sell_order['info']['id'] != order_id]

def get_current_balance():
    current_bal = exchange.fetch_balance()['USDT']['total']
    return current_bal

def check_take_profit():
    if CURRENT_BALANCE > TAKE_PROFIT_BALANCE:
        print("======== TAKE PROFIT REACHED! Closing all Positions and Open Orders")
        cancel_all_existing_orders() 
        close_all_positions()
        print("======== THE GRID BOT WILL RESTART SOON ========")
        return
    else:
        print(" ======== TAKE PROFIT CONDITION NOT MET YET. GRIDBOT STILL RUNNING ========")
        return 

def check_stop_condition():
    if CURRENT_BALANCE < STOP_BALANCE:
        print("======== STOP LOSS REACHED. Closing all Positions and Open Orders")
        cancel_all_existing_orders()
        close_all_positions()
        print(" ======== SHUTTING DOWN THE GRIDBOT =========")
        sys.exit()
    else:
        print(" ======== STOP CONDITION NOT MET YET. GRIDBOT STILL RUNNING ========")
        return

def fetch_position():
    positions = exchange.fetch_positions()
    for position in positions:
        if position['info']['contract'] == config.SYMBOL:
            return position['side'], float(position['contracts']) 


def close_all_positions():
    # Get current position
    pos_side, size = fetch_position()
    bid, ask = fetch_latest_prices()
    if pos_side == 'long':
        exchange.create_order(symbol=config.SYMBOL, type = "limit", side = 'sell', amount = size, price = (ask - 5), params = PARAMS)
    elif pos_side == "short":
        exchange.create_order(symbol=config.SYMBOL, type = "limit", side = 'buy', amount = size, price = (bid + 5), params = PARAMS)
    else:
        print("Error with fetching position info. Look into it.")
    
    return


def threshold_checker():
    '''
    We check if the current open position is not oversized.
    An oversized position can lead to significant losses if the trend continues. 
    Therefore, it is important to have some threshhold in place in order to close/reduce the position and refresh the orders.
    '''
    global BUY_ORDERS, SELL_ORDERS
    # Get current position
    pos_side, size = fetch_position()
    if size > THRESHOLD_POSITION:
        print(" \n========== Grid Bot is currently in an oversized {pos_side} position. Closing the Position and refreshing the orders. ===========")
        close_all_positions()
        cancel_all_existing_orders()
        # Reset BUY_ORDERS and SELL_ORDERS
        BUY_ORDERS = []
        SELL_ORDERS = []
    
    return





# ************************* MAIN **************************

if __name__ == "__main__":

    
    print(fetch_position())
    print(config.THRESHOLD_POSITION)
    print(" ======== STARTING GRIDBOT ========")
    print(" ======== CLOSING ALL EXISTING POSITIONS =========")
    print(f" ======== STARTING BALANCE: ${STARTING_BALANCE} ========")
    CURRENT_BALANCE = round(get_current_balance(), 2)
    print(f' ======== CURRENT BALANCE: ${CURRENT_BALANCE} ========')
    print(" ======== Cancelling all existing orders! ========")
    cancel_all_existing_orders()
    print(" ======== Proceeding to the Main Logic! ========")
    close_all_positions()    
    while True:
      
        threshold_checker()
        check_take_profit()
        check_stop_condition()
        #send_data()
        check_buy_orders()
        check_sell_orders()
        print(" ======== Checking for Open Limit Sell Orders! ======== ")
        check_open_buy_orders()
        #time.sleep(1)
        print(" ======== Checking for Open Limit Sell Orders! ======== ")
        check_open_sell_orders()
        #time.sleep(1)
        print(" ======== Clearing Order Lists from Closed Orders! ======== ")
        clear_order_lists()



    


