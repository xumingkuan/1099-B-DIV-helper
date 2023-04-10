import pandas as pd
import dateutil
from collections import deque

activity_columns = ['Date', 'Description', 'Symbol', 'Action', 'Quantity', 'Price', 'Amount']
activity = pd.DataFrame(columns=activity_columns)

gain_loss_columns = ['(a) Kind of property and description', '(b) Date acquired', '(c) Date sold', '(d) Sales price',
                     '(e) Cost or other basis', '(f) LOSS', '(g) GAIN']
gain_loss = pd.DataFrame(columns=gain_loss_columns)


def append_row(df, row):
    return pd.concat([
        df,
        pd.DataFrame([row], columns=row.index)]
    ).reset_index(drop=True)


def read_and_compute_cash_app_btc(filename='cash_app_report_btc.csv'):
    global gain_loss
    cash_app_btc = pd.read_csv(filename)
    cash_app_btc.rename({
        'Notes': 'Description',
        'Asset Type': 'Symbol',
        'Transaction Type': 'Action',
        'Asset Amount': 'Quantity',
        'Asset Price': 'Price',
        'Amount': 'Amount without fee',
        'Net Amount': 'Amount'
    }, axis=1, inplace=True)
    cash_app_btc.sort_values('Date', inplace=True)
    # activity = pd.concat([activity, cash_app_btc], join='inner')
    asset = deque()
    EPS = 1e-10
    total_proceeds = 0
    total_gain_loss = 0
    # XXX: assume the amounts of BTC at the beginning and at the end of the year are both 0
    for index, row in cash_app_btc.iterrows():
        tzinfos = {"EST": dateutil.tz.gettz('America/Eastern'),
                   "EDT": dateutil.tz.gettz('America/Eastern')}
        date = dateutil.parser.parse(row['Date'], tzinfos=tzinfos)
        date = date.strftime("%m/%d/%Y")
        assert row['Symbol'] == "BTC"
        if row['Action'] == "Bitcoin Boost":
            # FIFO
            asset.append(
                [date, float(row['Quantity']), float(row['Amount'][1:].replace(',', '')) / float(row['Quantity'])])
            print(f"Buy {float(row['Quantity'])}")
            continue
        assert row['Action'] == "Bitcoin Sale"
        sold_amount = float(row['Quantity'])
        unit_price = float(row['Amount'][1:].replace(',', '')) / sold_amount
        total_proceeds += float(row['Amount'][1:].replace(',', ''))
        print(f"Sell {float(row['Quantity'])}")
        while sold_amount > EPS:
            assert len(asset) > 0
            current_amount = min(sold_amount, asset[0][1])
            # cannot detect wash sale
            # cannot distinguish between short/long term
            # 1040-NR Schedule NEC does not need to detect them
            sales_price = unit_price * current_amount
            cost = asset[0][2] * current_amount
            loss = max(0, cost - sales_price)
            gain = max(0, sales_price - cost)
            total_gain_loss += gain - loss
            new_item = pd.Series(
                {'(a) Kind of property and description': f'{current_amount:.9f} BTC (Cash App)',
                 '(b) Date acquired': asset[0][0],
                 '(c) Date sold': date, '(d) Sales price': sales_price,
                 '(e) Cost or other basis': cost, '(f) LOSS': loss, '(g) GAIN': gain})
            gain_loss = append_row(gain_loss, new_item)
            asset[0][1] -= current_amount
            if asset[0][1] <= EPS:
                asset.popleft()
            sold_amount -= current_amount
    assert len(asset) == 0
    print(f'Computed Cash App Bitcoin with total proceeds {total_proceeds} and total gain/loss {total_gain_loss}.')


def read_and_compute_robinhood_crypto(filename, tax_year):
    global gain_loss
    robinhood_gain_loss = pd.read_csv(filename)
    # we only support these cryptocurrencies for now
    asset = {'BTC': deque(), 'ETH': deque()}
    EPS = 1e-10
    total_gain_loss = 0
    for index, row in robinhood_gain_loss[::-1].iterrows():
        date = dateutil.parser.parse(row['Time Entered'])
        year = date.year
        date = date.strftime("%m/%d/%Y")
        if row['State'] != 'Filled':
            continue
        if year > tax_year:
            break
        if row['Symbol'] not in asset.keys():
            print('Unsupported cryptocurrency:', row['Symbol'])
            continue
        assert row['Leaves Quantity'] == 0
        q = asset[row['Symbol']]
        if row['Side'] == 'Buy':
            # FIFO
            notional = float(row['Notional'][2:])  # -$x.xx
            q.append(
                [date, float(row['Quantity']), notional / float(row['Quantity'])])
            print(f"Buy {float(row['Quantity'])} {row['Symbol']} with unit price {notional / float(row['Quantity'])}")
            continue
        assert row['Side'] == 'Sell'
        notional = float(row['Notional'][1:])  # $x.xx
        sold_amount = float(row['Quantity'])
        unit_price = notional / sold_amount
        print(f"Sell {sold_amount} {row['Symbol']} with unit price {unit_price}")
        while sold_amount > EPS:
            assert len(q) > 0
            current_amount = min(sold_amount, q[0][1])
            # cannot detect wash sale
            # cannot distinguish between short/long term
            # 1040-NR Schedule NEC does not need to detect them
            sales_price = unit_price * current_amount
            cost = q[0][2] * current_amount
            # print(f'- {current_amount}, {sales_price}, {cost}')
            if year == tax_year:
                loss = max(0, cost - sales_price)
                gain = max(0, sales_price - cost)
                total_gain_loss += gain - loss
                new_item = pd.Series(
                    {'(a) Kind of property and description': f'{current_amount:.9f} {row["Symbol"]} (Robinhood)',
                     '(b) Date acquired': q[0][0],
                     '(c) Date sold': date, '(d) Sales price': sales_price,
                     '(e) Cost or other basis': cost, '(f) LOSS': loss, '(g) GAIN': gain})
                gain_loss = append_row(gain_loss, new_item)
            q[0][1] -= current_amount
            if q[0][1] <= EPS:
                q.popleft()
            sold_amount -= current_amount
    for symbol, q in asset.items():
        cost = 0
        quantity = 0
        for item in q:
            quantity += item[1]
            cost += item[1] * item[2]
        if quantity > 0:
            print(
                f'Remaining {symbol} as of the end of year {tax_year}: quantity={quantity}, average cost={cost / quantity}, total cost={cost}')
    print(f'Computed Robinhood crypto with total gain/loss {total_gain_loss}.')


def read_and_compute_robinhood_gain_loss(filename):
    global gain_loss
    robinhood_gain_loss = pd.read_csv(filename)
    total_gain_loss = 0
    for index, row in robinhood_gain_loss[::-1].iterrows():
        if row['Event'] == 'Wash':
            gain = float(row['ST G/L'][1:])
            total_gain_loss += gain
            new_item = pd.Series({
                '(a) Kind of property and description':
                    f'Wash sale disallowed loss (determined by Robinhood) of {str(row["Qty"])} {row["Description"]}',
                '(b) Date acquired': row['Open Date'],
                '(c) Date sold': row['Closed Date'], '(d) Sales price': 0,
                '(e) Cost or other basis': -gain, '(f) LOSS': 0, '(g) GAIN': gain})
            print(f'Wash sale of {gain}.')
            gain_loss = append_row(gain_loss, new_item)
            continue
        sales_price = float(row['Proceeds'][1:])
        cost = float(row['Cost'][1:])
        loss = max(0.0, cost - sales_price)
        gain = max(0.0, sales_price - cost)
        total_gain_loss += gain - loss
        new_item = pd.Series({
            '(a) Kind of property and description': f'{str(row["Qty"])} {row["Description"]} {row["Event"]}',
            '(b) Date acquired': row['Open Date'],
            '(c) Date sold': row['Closed Date'], '(d) Sales price': sales_price,
            '(e) Cost or other basis': cost, '(f) LOSS': loss, '(g) GAIN': gain})
        gain_loss = append_row(gain_loss, new_item)
    print(f'Computed Robinhood gain/loss: {total_gain_loss}.')


def read_and_compute_schwab_gain_loss(filename):
    global gain_loss
    with open(filename, 'r') as fn:
        # Ignore the 1099-DIV, 1099-INT, ... parts
        while fn.readline().strip() != '"Form 1099 B",':
            pass
        fn.readline()  # Ignore the line with numbers
        schwab_gain_loss = pd.read_csv(fn, header='infer')
    total_gain_loss = 0
    for index, row in schwab_gain_loss.iterrows():
        if float(row["Wash sale loss disallowed"][1:]) != 0.0:
            gain = float(row["Wash sale loss disallowed"][1:])
            total_gain_loss += gain
            new_item = pd.Series({
                '(a) Kind of property and description':
                    f'Wash sale disallowed loss (determined by Schwab) of {str(row["Description of property (Example 100 sh. XYZ Co.)"])}',
                '(b) Date acquired': row['Date acquired'],
                '(c) Date sold': row['Date sold or disposed'], '(d) Sales price': 0,
                '(e) Cost or other basis': -gain, '(f) LOSS': 0, '(g) GAIN': gain})
            print(f'Wash sale of {gain}.')
            gain_loss = append_row(gain_loss, new_item)
        sales_price = float(row['Proceeds'])
        cost = float(row['Cost or other basis']) + float(row['Accrued market discount'][1:])
        loss = max(0.0, cost - sales_price)
        gain = max(0.0, sales_price - cost)
        total_gain_loss += gain - loss
        new_item = pd.Series({
            '(a) Kind of property and description': f'{str(row["Description of property (Example 100 sh. XYZ Co.)"])}',
            '(b) Date acquired': row['Date acquired'],
            '(c) Date sold': row['Date sold or disposed'], '(d) Sales price': sales_price,
            '(e) Cost or other basis': cost, '(f) LOSS': loss, '(g) GAIN': gain})
        gain_loss = append_row(gain_loss, new_item)
    print(f'Computed Schwab gain/loss: {total_gain_loss}.')


def generate_1040NR_NEC_line16(filename='1040NR_NEC_line16.csv'):
    gain_loss.to_csv(filename, index=False)
    print('1040-NR Schedule NEC line 16 generated. '
          'Disclaimer: This is for informational purposes only, '
          'and the result can be wrong. '
          'Please consult a professional tax service or personal tax advisor '
          'if you need instructions on how to calculate cost basis and/or '
          'how to prepare your tax return.')


if __name__ == '__main__':
    read_and_compute_cash_app_btc('2022_cash_app_report_btc.csv')
    read_and_compute_robinhood_crypto('2022_Robinhood_crypto_activity.csv', 2022)
    read_and_compute_robinhood_gain_loss('2022_Robinhood_gain_loss.csv')
    read_and_compute_schwab_gain_loss('2022_schwab_1099B.csv')
    generate_1040NR_NEC_line16()
