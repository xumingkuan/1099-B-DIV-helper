# 1099-B Helper
A tool to convert Form 1099-B by Schwab, Robinhood, Cash App, and Morgan Stanley to a `.csv` file similar to the format in Form 1040-NR Schedule NEC line 16 for non-resident aliens (NRAs) in the US.

Supported input:
- 1099-B in `.csv` format by Schwab (e.g., `2023_Schwab_1099B.csv`);
- 1099-B in `.csv` format by Cash App (e.g., `2023_cash_app_report_btc.csv`), only supports Bitcoin Boost and Bitcoin Sales, assuming the amount of Bitcoin at the beginning and at the end are both 0, and a FIFO cost basis method is used;
- Realized gain/loss `.csv` file by Robinhood (e.g., `2023_Robinhood_gain_loss.csv`);
- Crypto account activity `.csv` file by Robinhood (e.g., [2023_Robinhood_crypto_activity.csv](examples/2023_Robinhood_crypto_activity.csv)), supports transfers (e.g., [Robinhood_crypto_transfers.csv](examples/Robinhood_crypto_transfers.csv)), and switching between the FIFO cost basis method and tax loss harvesting (high cost when selling, low cost when transferring out);
- A one-liner for Morgan Stanley (e.g., [2023_Morgan_Stanley_total.csv](examples/2023_Morgan_Stanley_total.csv)), including the proceeds and cost basis, to append one line for it (assuming no wash sales).

### Usage
Edit the file names hard-coded in [generate_1040NR_NEC_line16.py](generate_1040NR_NEC_line16.py) and then run `python generate_1040NR_NEC_line16.py`.

# 1099-DIV Helper
A tool to compute the tax-exempt interest-related dividend portion from Vanguard, Fidelity, and iShares ETFs to be subtracted from the total dividend amount before filling into Form 1040-NR Schedule NEC line 1 for non-resident aliens (NRAs) in the US from Form 1099-DIV by Morgan Stanley, Schwab, and Fidelity.

Supported input:
- A `.txt` file copied from Morgan Stanley "1099 Consolidated Tax Statement", the "1099-DIV DIVIDENDS & DISTRIBUTIONS Ordinary Dividends" part (e.g., [2023_Morgan_Stanley_dividend_detail.txt](examples/2023_Morgan_Stanley_dividend_detail.txt));
- A `.txt` file copied from Schwab "FORM 1099 COMPOSITE", the "Detail Information of Dividends and Distributions" part (e.g., [2023_schwab_dividend_detail.txt](examples/2023_Schwab_dividend_detail.txt));
- A `.txt` file copied from Fidelity "Consolidated Form 1099", the "Total Ordinary Dividends and Distributions Detail" part (e.g., [2023_Fidelity_dividend_detail.txt](examples/2023_Fidelity_dividend_detail.txt)).

Please prepend the total dividend amount (Form 1099-DIV Box 1a) to the first line of each `.txt` file.

### Usage
- For Vanguard: for the tax years not included in this repo, please download the files for the corresponding tax years from websites like https://advisors.vanguard.com/content/dam/fas/pdfs/2023_VGI_NRA%20Layout.xls and export it to a `.csv` file like [2023_VGI_NRA%20Layout.csv](dividend/2023/2023_VGI_NRA%20Layout.csv). 
  - In addition, please go to Vanguard's website (https://investor.vanguard.com/investment-products/etfs/profile/vcit) to find the dividend income and prepare the `.csv` file ([VCIT.csv](dividend/vanguard/VCIT.csv)) for each ETF with interest-related dividends.
- For Fidelity: for the tax years not included in this repo, please download the files for the corresponding tax years from websites like https://www.fidelity.com/bin-public/060_www_fidelity_com/documents/taxes/ty23-nra-supplemental-letter.pdf and export it to a `.txt` file like [fidelity2023.txt](dividend/2023/fidelity2023.txt).
  - If you have Fidelity funds in any other brokerage accounts than Fidelity, please also include the CUSIP for them (you can find the information on Fidelity's website like https://institutional.fidelity.com/app/funds-and-products/458/fidelity-government-money-market-fund-spaxx.html). Otherwise, it is OK to not include the CUSIP at the end of each line in the file.
- For iShares: for the tax years not included in this repo, please download the files for the corresponding tax years from websites like https://www.ishares.com/us/literature/tax-information/qualified-interest-income-qii-percentages-final-2023.pdf and export it to a `.txt` file like [ishares-qualified-interest-income-qii-percentages-final-2023.txt](dividend/2023/ishares-qualified-interest-income-qii-percentages-final-2023.txt).

After that, please edit the file names hard-coded in [generate_1040NR_NEC_line1.py](generate_1040NR_NEC_line1.py) and then run `python generate_1040NR_NEC_line1.py`.

## Installation
The tools are portable. If you have not installed pandas, please install it by calling `pip install pandas`.

## Disclaimer
The tools do not check errors, so the results may be wrong if some assumptions I made when implementing the tool is not satisfied.
Please consult a professional tax service or personal tax advisor for further information.
