import bs4 as bs
import pickle
import requests


FILENAME = 'sp500'

def save_sp500_tickers():
    resp = requests.get('http://en.wikipedia.org/wiki/List_of_S%26P_500_companies')
    soup = bs.BeautifulSoup(resp.text, 'lxml')
    table = soup.find('table', {'class': 'wikitable sortable'})
    tickers = []
    for row in table.findAll('tr')[1:]:
        ticker = row.findAll('td')[0].text
        tickers.append(ticker)
        
    # with open(FILENAME+".pickle", "wb") as f:
    #     pickle.dump(tickers,f)
        
    return tickers


def main():
    tickers = save_sp500_tickers()
    open(FILENAME+'.txt', 'w').close()
    with open(FILENAME+'.txt', 'w') as f:
        for ticker in tickers:
            f.write("%s\n" % ticker)

if __name__ == '__main__':
  main()