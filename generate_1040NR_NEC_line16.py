import pandas as pd
import dateutil
from collections import deque

activity_columns = ['Date', 'Description', 'Symbol', 'Action', 'Quantity', 'Price', 'Amount']
activity = pd.DataFrame(columns=activity_columns)

gain_loss_columns = ['(a) Kind of property and description', '(b) Date acquired', '(c) Date sold', '(d) Sales price',
                     '(e) Cost or other basis', '(f) LOSS', '(g) GAIN']
gain_loss = pd.DataFrame(columns=gain_loss_columns)

transfer_history_columns = ['Date', 'Symbol', 'Side', 'Quantity', 'Cost Basis']
stable_coins = set(['USDC'])
EPS = 1e-10


def append_row(df, row):
    return pd.concat([
        df,
        pd.DataFrame([row], columns=row.index)]
    ).reset_index(drop=True)


def remove_equal_sign(s):
    s = str(s).strip()
    if s.startswith('='):
        s = s[1:]
    if (s.startswith("'") or s.startswith('"')) and (s[0] == s[-1]):
        s = s[1:-1]
    return s


def read_money_value(s):
    if isinstance(s, float):
        return s
    elif isinstance(s, str):
        s = remove_equal_sign(s)
        if s.startswith('$'):
            s = s[1:]
        if s.startswith('-$'):
            s = '-' + s[2:]
        s = s.strip().replace(",", "")
        return float(s)
    else:
        raise Exception(f"Unknown money value type: {s}")


def read_and_compute_cash_app_btc(filename='cash_app_report_btc.csv', tax_year=None):
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
    total_proceeds = 0
    total_gain_loss = 0
    # XXX: assume the amounts of BTC at the beginning and at the end of the year are both 0
    for index, row in cash_app_btc.iterrows():
        tzinfos = {"EST": dateutil.tz.gettz('America/Eastern'),
                   "EDT": dateutil.tz.gettz('America/Eastern')}
        date = dateutil.parser.parse(row['Date'], tzinfos=tzinfos)
        if tax_year is not None and date.year != tax_year:
            continue
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
            # Cryptocurrency is exempt from wash sale rules. See also:
            # https://ttlc.intuit.com/turbotax-support/en-us/help-article/cryptocurrency/wash-sale-rule-cryptocurrency/L1d6BuQpH_US_en_US
            # This script cannot distinguish between short/long term.
            # 1040-NR Schedule NEC does not need to detect it.
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


def get_high_cost(q, sold_amount):
    q_list = list(q)
    idx = 0
    for i in range(len(q_list)):
        if q_list[i][2] > q_list[idx][2]:
            idx = i
    current_amount = min(sold_amount, q_list[idx][1])
    q[idx][1] -= current_amount
    if q[idx][1] <= EPS:
        del q[idx]
    # q_list is not deleted
    return current_amount, q_list[idx][2] * current_amount, q_list[idx][0]  # amount, cost, date


def get_low_cost(q, sold_amount):
    q_list = list(q)
    idx = 0
    for i in range(len(q_list)):
        if q_list[i][2] < q_list[idx][2]:
            idx = i
    current_amount = min(sold_amount, q_list[idx][1])
    q[idx][1] -= current_amount
    if q[idx][1] <= EPS:
        del q[idx]
    # q_list is not deleted
    return current_amount, q_list[idx][2] * current_amount, q_list[idx][0]  # amount, cost, date


def read_and_compute_robinhood_crypto(filenames, tax_year, filter=None, transfers=None, tax_harvest_years=None):
    # tax harvesting: use high cost on sales and low costs on outbound transfers in these years, or FIFO otherwise
    global gain_loss
    assert len(filenames) > 0
    activities = [pd.read_csv(filename) for filename in filenames]
    if filter is not None:
        # Sometimes Robinhood includes activities not in the tax year.
        # We filter each file according to the years to avoid duplicates.
        for i in range(len(filenames)):
            if i in filter.keys():
                activities[i] = activities[i][
                    activities[i].apply(lambda x: dateutil.parser.parse(x['Time Entered']).year in filter[i], axis=1)]
    robinhood_gain_loss = pd.concat(activities)
    transfer_history = pd.DataFrame(columns=transfer_history_columns)
    if transfers is not None:
        transfer_history = pd.read_csv(transfers)
    transfer_id = 0
    asset = {}
    total_gain_loss = 0
    for index, row in robinhood_gain_loss[::-1].iterrows():
        if row['State'] != 'Filled':
            continue
        date = dateutil.parser.parse(row['Time Entered'])
        year = date.year
        while transfer_id < len(transfer_history):
            transfer_row = transfer_history.iloc[transfer_id]
            transfer_date = dateutil.parser.parse(transfer_row['Date'])
            transfer_date_str = transfer_date.strftime("%m/%d/%Y")
            if transfer_date > date:
                break
            # we now process the transfer
            if transfer_row['Symbol'] not in asset.keys():
                print('New cryptocurrency:', transfer_row['Symbol'])
                asset[transfer_row['Symbol']] = deque()
            q = asset[transfer_row['Symbol']]
            if transfer_row['Side'] == 'Received':
                # FIFO
                notional = float(transfer_row['Cost Basis'])
                q.append(
                    [transfer_date_str, float(transfer_row['Quantity']), notional / float(transfer_row['Quantity'])])
                print(f"Received {float(transfer_row['Quantity'])} {transfer_row['Symbol']} with unit price "
                      f"{notional / float(transfer_row['Quantity'])} (total {notional})")
            else:
                assert transfer_row['Side'] == 'Sent'
                cost = 0.0
                sent_amount = transfer_row['Quantity']
                while sent_amount > EPS:
                    assert len(q) > 0
                    if tax_harvest_years is None or year not in tax_harvest_years:
                        # FIFO
                        current_amount = min(sent_amount, q[0][1])
                        cost += q[0][2] * current_amount
                        q[0][1] -= current_amount
                        if q[0][1] <= EPS:
                            q.popleft()
                        sent_amount -= current_amount
                    else:
                        current_amount, current_cost, _ = get_low_cost(q, sent_amount)
                        sent_amount -= current_amount
                        cost += current_cost
                print(f"Sent {transfer_row['Quantity']} {transfer_row['Symbol']} with unit price "
                      f"{cost / transfer_row['Quantity']} (total {cost})")
            transfer_id += 1
        date = date.strftime("%m/%d/%Y")
        if year > tax_year:
            break
        if row['Symbol'] not in asset.keys():
            print('New cryptocurrency:', row['Symbol'])
            asset[row['Symbol']] = deque()
        assert row['Leaves Quantity'] == 0
        q = asset[row['Symbol']]
        if row['Side'] == 'Buy':
            # FIFO
            if row['Notional'].strip()[0] == '-':
                notional = float(row['Notional'].strip()[2:])  # -$x.xx
            else:
                assert row['Notional'].strip()[0] == '('
                assert row['Notional'].strip()[-1] == ')'
                notional = float(row['Notional'].strip()[2:-1])  # ($x.xx)
            q.append(
                [date, float(row['Quantity']), notional / float(row['Quantity'])])
            print(f"Buy {float(row['Quantity'])} {row['Symbol']} with unit price {notional / float(row['Quantity'])}")
            continue
        assert row['Side'] == 'Sell'
        notional = float(row['Notional'].strip()[1:])  # $x.xx
        sold_amount = float(row['Quantity'])
        unit_price = notional / sold_amount
        print(f"Sell {sold_amount} {row['Symbol']} with unit price {unit_price}")
        while sold_amount > EPS:
            assert len(q) > 0
            cost = 0
            if tax_harvest_years is None or transfer_date.year not in tax_harvest_years:
                # FIFO
                current_amount = min(sold_amount, q[0][1])
                # Cryptocurrency is exempt from wash sale rules. See also:
                # https://ttlc.intuit.com/turbotax-support/en-us/help-article/cryptocurrency/wash-sale-rule-cryptocurrency/L1d6BuQpH_US_en_US
                # This script cannot distinguish between short/long term.
                # 1040-NR Schedule NEC does not need to detect it.
                sales_price = unit_price * current_amount
                cost = q[0][2] * current_amount
                q[0][1] -= current_amount
                date_acquired = q[0][0]
                if q[0][1] <= EPS:
                    q.popleft()
            else:
                current_amount, cost, date_acquired = get_high_cost(q, sold_amount)
                sales_price = unit_price * current_amount
            sold_amount -= current_amount
            if year == tax_year:
                loss = max(0, cost - sales_price)
                gain = max(0, sales_price - cost)
                total_gain_loss += gain - loss
                if loss < EPS and gain < EPS and row["Symbol"] in stable_coins:
                    pass
                else:
                    new_item = pd.Series(
                        {'(a) Kind of property and description': f'{current_amount:.9f} {row["Symbol"]} (Robinhood)',
                         '(b) Date acquired': date_acquired,
                         '(c) Date sold': date, '(d) Sales price': sales_price,
                         '(e) Cost or other basis': cost, '(f) LOSS': loss, '(g) GAIN': gain})
                    gain_loss = append_row(gain_loss, new_item)
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
        if row['Symbol'].strip().startswith('The data provided is for informational'):
            continue
        if row['Event'] == 'Wash':
            gain = read_money_value(row['ST G/L'])
            total_gain_loss += gain
            new_item = pd.Series({
                '(a) Kind of property and description':
                    f'Wash sale disallowed loss (determined by Robinhood) of {remove_equal_sign(row["Qty"])} {remove_equal_sign(row["Description"])}',
                '(b) Date acquired': remove_equal_sign(row['Open Date']),
                '(c) Date sold': remove_equal_sign(row['Closed Date']), '(d) Sales price': 0,
                '(e) Cost or other basis': -gain, '(f) LOSS': 0, '(g) GAIN': gain})
            print(f'Wash sale of {gain}.')
            gain_loss = append_row(gain_loss, new_item)
            continue
        sales_price = read_money_value(row['Proceeds'])
        cost = read_money_value(row['Cost'])
        loss = max(0.0, cost - sales_price)
        gain = max(0.0, sales_price - cost)
        total_gain_loss += gain - loss
        new_item = pd.Series({
            '(a) Kind of property and description':
                f'{remove_equal_sign(row["Qty"])} {remove_equal_sign(row["Description"])} {remove_equal_sign(row["Event"])} (Robinhood)',
            '(b) Date acquired': remove_equal_sign(row['Open Date']),
            '(c) Date sold': remove_equal_sign(row['Closed Date']), '(d) Sales price': sales_price,
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
            '(a) Kind of property and description': f'{str(row["Description of property (Example 100 sh. XYZ Co.)"])} (Schwab)',
            '(b) Date acquired': row['Date acquired'],
            '(c) Date sold': row['Date sold or disposed'], '(d) Sales price': sales_price,
            '(e) Cost or other basis': cost, '(f) LOSS': loss, '(g) GAIN': gain})
        gain_loss = append_row(gain_loss, new_item)
    print(f'Computed Schwab gain/loss: {total_gain_loss}.')


def read_morgan_stanley_total(filename):
    # Assume no wash sales.
    global gain_loss
    proceeds = None
    cost = None
    with open(filename, 'r') as fn:
        while True:
            line = fn.readline().strip()
            if proceeds is None:
                proceeds = read_money_value(line)
                continue
            if cost is None:
                cost = read_money_value(line)
            break
    loss = max(0.0, cost - proceeds)
    gain = max(0.0, proceeds - cost)
    new_item = pd.Series({
        '(a) Kind of property and description': 'Various (Morgan Stanley (Total Reportable))',
        '(b) Date acquired': 'Various',
        '(c) Date sold': 'Various', '(d) Sales price': proceeds,
        '(e) Cost or other basis': cost, '(f) LOSS': loss, '(g) GAIN': gain})
    gain_loss = append_row(gain_loss, new_item)
    print(f'Read Morgan Stanley gain/loss: {gain - loss}.')


def generate_1040NR_NEC_line16(filename='1040NR_NEC_line16.csv'):
    gain_loss.to_csv(filename, index=False)
    print('1040-NR Schedule NEC line 16 generated. '
          'Disclaimer: This is for informational purposes only, '
          'and the result can be wrong. '
          'Please consult a professional tax service or personal tax advisor '
          'if you need instructions on how to calculate cost basis and/or '
          'how to prepare your tax return.')


if __name__ == '__main__':
    read_and_compute_cash_app_btc('2023_cash_app_report_btc.csv', tax_year=2023)
    read_and_compute_robinhood_crypto(['2023_Robinhood_crypto_activity.csv',
                                       '2022_Robinhood_crypto_activity.csv'], 2023, {1: [2021, 2022]},
                                      transfers='Robinhood_crypto_transfers.csv',
                                      tax_harvest_years=[2023])
    read_and_compute_robinhood_gain_loss('2023_Robinhood_gain_loss.csv')
    read_and_compute_schwab_gain_loss('2023_schwab_1099B.csv')
    read_morgan_stanley_total('2023_Morgan_Stanley_total.csv')
    generate_1040NR_NEC_line16()
