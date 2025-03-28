import pandas as pd
import dateutil
import dateutil.parser
import os

exempt_detail_columns = ['Symbol (Brokerage)', 'Date', 'Ordinary Dividends', 'Interest Percentage', 'Interest-Related Dividend']
exempt_detail = pd.DataFrame(columns=exempt_detail_columns)

vanguard_cusip_to_symbol = {}
vanguard_interest = {}  # Vanguard percentage = interest / dividend for each month
vanguard_dividend = {}
fidelity_cusip_to_symbol = {}
fidelity_percentage = {}  # Fidelity percentage is for each year
others_cusip_to_symbol = {}
others_percentage = {}  # Percentage for each month


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
        if s == '-' or s == '':
            return 0
        return float(s)
    else:
        raise Exception(f"Unknown money value type: {s}")


def all_capital_letters(s):
    if len(s) == 0:
        return False
    for c in s:
        if not c.isupper():
            return False
    return True


def percentage_to_float(x):
    return float(x.strip('%')) / 100


def read_vanguard_dividend(symbol):
    global vanguard_dividend
    path = f'dividend/vanguard/{symbol}.csv'
    if not os.path.isfile(path):
        return False
    vanguard_dividend[symbol] = {}
    with open(path, 'r') as fn:
        lines = fn.readlines()
        for line in lines:
            line = line.strip().split(',')
            if line[0] == 'Dividend':
                date = dateutil.parser.parse(line[2])
                amount = read_money_value(line[1])
                vanguard_dividend[symbol][date] = amount
    return True


def read_vanguard_exempt_info(tax_year=2023):
    global vanguard_cusip_to_symbol
    global vanguard_interest
    filename = f'dividend/{tax_year}/{tax_year}_VGI_NRA Layout.csv'
    with open(filename, 'r') as fn:
        lines = fn.readlines()
        for line in lines:
            line = line.strip().split(',')
            if len(line) >= 7 and all_capital_letters(line[2].strip()):
                symbol = line[2].strip()
                amount = read_money_value(line[6])
                if amount == 0:
                    continue
                if line[0].strip() == 'TOTALS':
                    continue
                if symbol not in vanguard_interest.keys():
                    cusip = line[1].strip()
                    vanguard_cusip_to_symbol[cusip] = symbol
                    vanguard_interest[symbol] = {}
                if symbol not in vanguard_dividend.keys():
                    read_vanguard_dividend(symbol)
                date = dateutil.parser.parse(line[5])
                vanguard_interest[symbol][date] = amount


def read_fidelity_exempt_info(tax_year=2023):
    global fidelity_cusip_to_symbol
    global fidelity_percentage
    filename = f'dividend/{tax_year}/fidelity{tax_year}.txt'
    with open(filename, 'r') as fn:
        lines = fn.readlines()
        for line in lines:
            line = line.strip().split()
            assert 2 <= len(line) <= 3
            fidelity_percentage[line[0]] = percentage_to_float(line[1])
            if len(line) == 3:
                fidelity_cusip_to_symbol[line[2]] = line[0]


def read_jpmorgan_exempt_info(tax_year=2024):
    global others_cusip_to_symbol
    global others_percentage
    filename = f'dividend/{tax_year}/jpmorgan{tax_year}.txt'
    dates = []
    phase = 0
    symbol = ''
    counter = 0
    with open(filename, 'r', encoding='UTF-8') as fn:
        lines = fn.readlines()
        for line in lines:
            line = line.strip()
            if phase == 0:
                if 'CUSIP' in line:
                    phase = 1
                continue
            if phase == 1:
                # input dates
                if not line[0].isdigit():
                    phase = 2  # name
                    continue
                date = dateutil.parser.parse(line)
                dates.append(date)
                continue
            if phase == 2:
                # symbol
                symbol = line
                others_percentage[symbol] = {}
                phase = 3
                continue
            if phase == 3:
                # cusip
                cusip = line
                others_cusip_to_symbol[cusip] = symbol
                phase = 4
                counter = 0
                continue
            if phase == 4:
                # input percentage
                if line != 'N/A':
                    try:
                        p = percentage_to_float(line)
                    except ValueError as e:
                        # less than 12 months
                        print(f'{symbol} does not have {len(dates)} values. Please double check if some numbers are missing.')
                        phase = 2
                        continue
                    others_percentage[symbol][dates[counter]] = p
                counter += 1
                if counter >= len(dates):
                    phase = 5
                continue
            if phase == 5:
                # name
                phase = 2
                continue


def read_ishares_exempt_info(tax_year=2023):
    global others_cusip_to_symbol
    global others_percentage
    filename = f'dividend/{tax_year}/ishares-qualified-interest-income-qii-percentages-final-{tax_year}.txt'
    dates = []
    phase = 0
    symbol = ''
    counter = 0
    with open(filename, 'r', encoding='UTF-8') as fn:
        lines = fn.readlines()
        for line in lines:
            line = line.strip()
            if phase == 0:
                if line == 'CUSIP':
                    phase = 1
                continue
            if phase == 1:
                # input dates
                if not line[0].isdigit():
                    phase = 2  # name
                    continue
                date = dateutil.parser.parse(line)
                dates.append(date)
                continue
            if phase == 2:
                # symbol
                symbol = line
                others_percentage[symbol] = {}
                phase = 3
                continue
            if phase == 3:
                # cusip
                cusip = line
                others_cusip_to_symbol[cusip] = symbol
                phase = 4
                counter = 0
                continue
            if phase == 4:
                # input percentage
                if line != 'N/A':
                    try:
                        p = percentage_to_float(line)
                    except ValueError as e:
                        # less than 12 months
                        print(f'{symbol} does not have {len(dates)} values. Please double check if some numbers are missing.')
                        phase = 2
                        continue
                    others_percentage[symbol][dates[counter]] = p
                counter += 1
                if counter >= len(dates):
                    phase = 5
                continue
            if phase == 5:
                # name
                phase = 2
                continue


def compute_morgan_stanley_dividend(filename):
    global exempt_detail
    total_dividend = None
    phase = -1
    symbol = None
    is_vanguard = True
    is_fidelity = False
    date = None
    amount = 0
    total_exempt_amount = 0.0
    appeared_symbols = set()
    with open(filename, 'r') as fn:
        lines = fn.readlines()
        for line in lines:
            line = line.strip()
            if phase == -1:
                total_dividend = read_money_value(line)
                phase = 0
                continue
            if phase == 0:
                if line in vanguard_cusip_to_symbol.keys():
                    symbol = vanguard_cusip_to_symbol[line]
                    is_vanguard = True
                    is_fidelity = False
                    phase = 1
                if line in fidelity_cusip_to_symbol.keys():
                    symbol = fidelity_cusip_to_symbol[line]
                    is_vanguard = False
                    is_fidelity = True
                    phase = 1
                if line in others_cusip_to_symbol.keys():
                    symbol = others_cusip_to_symbol[line]
                    is_vanguard = False
                    is_fidelity = False
                    phase = 1
                continue
            if phase == 1:
                date = dateutil.parser.parse(line)
                phase = 2
                continue
            if phase == 2:
                phase = 0
                amount = read_money_value(line)
                if amount == 0:
                    continue
                exempt_percentage = 0
                if is_vanguard:
                    if symbol not in vanguard_dividend.keys():
                        print(
                            f'Missing dividend info for {symbol}. Please go to https://investor.vanguard.com/investment-products/etfs/profile/{symbol.lower()} to get the dividend information.')
                        continue
                    if date not in vanguard_dividend[symbol].keys():
                        print(f'Missing dividend info for {symbol} on {date.strftime("%m/%d/%Y")}.')
                        continue
                    if date not in vanguard_interest[symbol].keys():
                        print(f'Missing interest info for {symbol} on {date.strftime("%m/%d/%Y")}.')
                        continue
                    exempt_percentage = vanguard_interest[symbol][date] / vanguard_dividend[symbol][date]
                elif is_fidelity:
                    exempt_percentage = fidelity_percentage[symbol]
                else:
                    if date not in others_percentage[symbol].keys():
                        print(f'Missing percentage info for {symbol} on {date.strftime("%m/%d/%Y")}.')
                        continue
                    exempt_percentage = others_percentage[symbol][date]
                total_exempt_amount += amount * exempt_percentage
                new_item = pd.Series(
                    {'Symbol (Brokerage)': f"{symbol} (Morgan Stanley)", 'Date': date.strftime("%m/%d/%Y"), 'Ordinary Dividends': amount,
                     'Interest Percentage': f"{exempt_percentage:.2%}", 'Interest-Related Dividend': amount * exempt_percentage})
                exempt_detail = append_row(exempt_detail, new_item)
                appeared_symbols.add(symbol)
                continue
    print(f'Tax-exempt amount for Morgan Stanley: {total_exempt_amount}{f" ({total_exempt_amount / total_dividend * 100:.2f}%, {appeared_symbols})" if len(appeared_symbols) > 0 else ""}.')
    print(f'Remaining dividend for Morgan Stanley: {total_dividend - total_exempt_amount}.')


def compute_schwab_dividend(filename):
    global exempt_detail
    total_dividend = None
    phase = -1
    symbol = None
    is_vanguard = True
    is_fidelity = False
    amount = 0
    total_exempt_amount = 0.0
    min_total_exempt_amount = 0.0
    max_total_exempt_amount = 0.0
    appeared_symbols = set()
    with open(filename, 'r') as fn:
        lines = fn.readlines()
        for line in lines:
            line = line.strip()
            if phase == -1:
                total_dividend = read_money_value(line)
                phase = 0
                continue
            if phase == 0:
                if line in vanguard_cusip_to_symbol.keys():
                    symbol = vanguard_cusip_to_symbol[line]
                    is_vanguard = True
                    is_fidelity = False
                    phase = 1
                if line in fidelity_cusip_to_symbol.keys():
                    symbol = fidelity_cusip_to_symbol[line]
                    is_vanguard = False
                    is_fidelity = True
                    phase = 1
                if line in others_cusip_to_symbol.keys():
                    symbol = others_cusip_to_symbol[line]
                    is_vanguard = False
                    is_fidelity = False
                    phase = 1
                continue
            if phase == 1:
                if '$' in line:
                    phase = 2
                continue
            if phase == 2:
                if '$' in line:
                    phase = 3
                continue
            if phase == 3:
                if '$' in line:
                    phase = 4
                continue
            if phase == 4:
                phase = 0
                amount = read_money_value(line)
                if amount == 0:
                    continue
                exempt_percentage = 0
                min_this_time = 1
                max_this_time = 0
                if is_vanguard:
                    if symbol not in vanguard_dividend.keys():
                        print(
                            f'Missing dividend info for {symbol}. Please go to https://investor.vanguard.com/investment-products/etfs/profile/{symbol.lower()} to get the dividend information.')
                        continue
                    total_int = 0.0
                    total_div = 0.0
                    for date in vanguard_dividend[symbol].keys():
                        if date not in vanguard_interest[symbol].keys():
                            print(f'Missing interest info for {symbol} on {date.strftime("%m/%d/%Y")}.')
                            continue
                        total_int += vanguard_interest[symbol][date]
                        total_div += vanguard_dividend[symbol][date]
                        min_this_time = min(min_this_time, total_int / total_div)
                        max_this_time = max(max_this_time, total_int / total_div)
                    exempt_percentage = total_int / total_div
                elif is_fidelity:
                    min_this_time = fidelity_percentage[symbol]
                    max_this_time = fidelity_percentage[symbol]
                    exempt_percentage = fidelity_percentage[symbol]
                else:
                    min_this_time = min(others_percentage[symbol].values())
                    max_this_time = max(others_percentage[symbol].values())
                    exempt_percentage = sum(others_percentage[symbol].values()) / len(others_percentage[symbol])
                total_exempt_amount += amount * exempt_percentage
                min_total_exempt_amount += amount * min_this_time
                max_total_exempt_amount += amount * max_this_time
                new_item = pd.Series(
                    {'Symbol (Brokerage)': f"{symbol} (Schwab{' Qualified Dividend' if symbol in appeared_symbols else ''})", 'Date': 'Various',
                     'Ordinary Dividends': amount,
                     'Interest Percentage': f"{exempt_percentage:.2%}", 'Interest-Related Dividend': amount * exempt_percentage})
                exempt_detail = append_row(exempt_detail, new_item)
                appeared_symbols.add(symbol)
                continue
    print(f'Tax-exempt amount for Schwab: {total_exempt_amount}{f" ({total_exempt_amount / total_dividend * 100:.2f}%, {appeared_symbols})" if len(appeared_symbols) > 0 else ""}.')
    print(f'Remaining dividend for Schwab: {total_dividend - total_exempt_amount}.')
    if min_total_exempt_amount != max_total_exempt_amount:
        print(
            f'Because Schwab only reports the total dividend amount, the tax-exempt amount can be in [{min_total_exempt_amount}, {max_total_exempt_amount}]. The average amount is reported here.')


def compute_fidelity_dividend(filename):
    global exempt_detail
    total_dividend = None
    phase = -1
    symbol = None
    is_vanguard = True
    is_fidelity = False
    date = None
    amount = 0
    total_exempt_amount = 0.0
    min_total_exempt_amount = 0.0
    max_total_exempt_amount = 0.0
    appeared_symbols = set()
    with open(filename, 'r') as fn:
        lines = fn.readlines()
        for line in lines:
            line = line.strip()
            if phase == -1:
                total_dividend = read_money_value(line)
                phase = 0
                continue
            if phase == 0:
                line = line.split(',')
                if len(line) != 3:
                    continue
                line = line[1].strip()  # symbol
                if line in vanguard_interest.keys():
                    symbol = line
                    is_vanguard = True
                    is_fidelity = False
                    phase = 1
                if line in fidelity_percentage.keys():
                    symbol = line
                    is_vanguard = False
                    is_fidelity = True
                    phase = 1
                if line in others_percentage.keys():
                    symbol = line
                    is_vanguard = False
                    is_fidelity = False
                    phase = 1
                continue
            if phase == 1:
                if line == 'Subtotals':
                    phase = 4
                    continue
                date = dateutil.parser.parse(line)
                phase = 2
                continue
            if phase == 2:
                amount = read_money_value(line)
                phase = 3
                continue
            if phase == 3:
                assert amount == read_money_value(line)
                if is_fidelity:
                    # Compute Fidelity fund in the subtotals only
                    phase = 1
                    continue
                if is_vanguard:
                    if symbol not in vanguard_dividend.keys():
                        print(
                            f'Missing dividend info for {symbol}. Please go to https://investor.vanguard.com/investment-products/etfs/profile/{symbol.lower()} to get the dividend information.')
                        continue
                    if date not in vanguard_dividend[symbol].keys():
                        print(f'Missing dividend info for {symbol} on {date.strftime("%m/%d/%Y")}.')
                        continue
                    if date not in vanguard_interest[symbol].keys():
                        print(f'Missing interest info for {symbol} on {date.strftime("%m/%d/%Y")}.')
                        continue
                    exempt_percentage = vanguard_interest[symbol][date] / vanguard_dividend[symbol][date]
                else:
                    if date not in others_percentage[symbol].keys():
                        print(f'Missing percentage info for {symbol} on {date.strftime("%m/%d/%Y")}.')
                        continue
                    exempt_percentage = others_percentage[symbol][date]
                total_exempt_amount += amount * exempt_percentage
                new_item = pd.Series(
                    {'Symbol (Brokerage)': f"{symbol} (Fidelity)", 'Date': date.strftime("%m/%d/%Y"), 'Ordinary Dividends': amount,
                     'Interest Percentage': f"{exempt_percentage:.2%}", 'Interest-Related Dividend': amount * exempt_percentage})
                exempt_detail = append_row(exempt_detail, new_item)
                appeared_symbols.add(symbol)
                phase = 1
                continue
            if phase == 4:
                amount = read_money_value(line)
                phase = 5
                continue
            if phase == 5:
                assert amount == read_money_value(line)
                if not is_fidelity:
                    phase = 0
                    continue
                # Compute Fidelity fund here
                exempt_percentage = fidelity_percentage[symbol]
                total_exempt_amount += amount * exempt_percentage
                new_item = pd.Series(
                    {'Symbol (Brokerage)': f"{symbol} (Fidelity)", 'Date': 'Various',
                     'Ordinary Dividends': amount,
                     'Interest Percentage': f"{exempt_percentage:.2%}", 'Interest-Related Dividend': amount * exempt_percentage})
                exempt_detail = append_row(exempt_detail, new_item)
                appeared_symbols.add(symbol)
                phase = 0
                continue
    print(f'Tax-exempt amount for Fidelity: {total_exempt_amount}{f" ({total_exempt_amount / total_dividend * 100:.2f}%, {appeared_symbols})" if len(appeared_symbols) > 0 else ""}.')
    print(f'Remaining dividend for Fidelity: {total_dividend - total_exempt_amount}.')


def show_exempt_detail(filename='exempt_detail.csv'):
    exempt_detail.to_csv(filename, index=False)


if __name__ == '__main__':
    read_vanguard_exempt_info(tax_year=2023)
    read_fidelity_exempt_info(tax_year=2023)
    read_ishares_exempt_info(tax_year=2023)
    read_jpmorgan_exempt_info(tax_year=2024)
    compute_morgan_stanley_dividend(filename='examples/2023_Morgan_Stanley_dividend_detail.txt')
    compute_schwab_dividend(filename='examples/2023_Schwab_dividend_detail.txt')
    compute_fidelity_dividend(filename='examples/2023_Fidelity_dividend_detail.txt')
    show_exempt_detail()
