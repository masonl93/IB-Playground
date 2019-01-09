import argparse
import json

import pandas
import requests

# Constants
api = "https://api.iextrading.com/1.0"
ref_data = "/ref-data/symbols"
microcap_min = 15000000
microcap_max = 200000001
min_volume = 100000  # $ amount
FILENAME = 'microcaps'

NOT_MICROCAPS = ['NTC', 'ACP', 'AGD']


def concat_100_symbols(symbols):
    '''
    Input:
        symbols: list of symbols

    Output:
        list of strings of 100 concatenated symbols

    IEX API has a batch endpoint that is must quicker than making
    individual requests. The batch endpoint can take up to 100 symbols
    per request so this method is useful to format those symbols
    '''
    symbol_str_list = []
    symbols_str = ''
    i = 0

    for s in symbols:
        i += 1
        if i % 100 == 0 or i == len(symbols):
            symbols_str += s
            symbol_str_list.append(symbols_str)
            symbols_str = ''
        else:
            symbols_str += s + ','

    return symbol_str_list


def save_microcap_tickers():
    resp = requests.get(api + ref_data)
    api_symbols = json.loads(resp.text)
    symbols = []

    for s in api_symbols:
        # Only want symbols that are type 'cs' (common stock)
        if s['type'] == 'cs' and '#' not in s['symbol']:
            symbols.append(s['symbol'])

    # Retrieving quote data
    quote_data = {}
    batch_req_symb = concat_100_symbols(symbols)
    for sym_str in batch_req_symb:
        resp = requests.get(api+'/stock/market/batch?symbols=' + sym_str + '&types=quote')
        quote_data.update(json.loads(resp.text))

    # Finding microcaps (b/w $50m and $200m)
    microcaps = {}
    for s in quote_data.items():
        if s[1]['quote']['marketCap'] in range(microcap_min, microcap_max):
            microcaps[s[0]] = s[1]['quote']

    # Checking for a reasonable avg daily volume based off
    # avg volume and latest price
    active_microcaps = {}
    for s in microcaps.items():
        if s[1]['avgTotalVolume'] * s[1]['latestPrice'] >= 100000:
            active_microcaps[s[0]] = s[1]

    return active_microcaps.keys()

def main():
    tickers = save_microcap_tickers()
    open(FILENAME + '.txt', 'w').close()
    with open(FILENAME + '.txt', 'w') as f:
        for ticker in tickers:
            if ticker not in NOT_MICROCAPS:
                f.write("%s\n" % ticker)

if __name__ == '__main__':
    main()
