# 1099-B-helper
A tool to convert Form 1099-B by Schwab, Robinhood, Cash App, and Morgan Stanley to a CSV file similar to the format in Form 1040-NR Schedule NEC line 16 for non-resident aliens (NRAs) in the US.

Supported input:
- 1099-B in CSV format by Schwab (e.g., `2023_schwab_1099B.csv`);
- 1099-B in CSV format by Cash App (e.g., `2023_cash_app_report_btc.csv`), only supports Bitcoin Boost and Bitcoin Sales, assuming the amount of Bitcoin at the beginning and at the end are both 0, and a FIFO cost basis method is used;
- Realized gain/loss CSV file by Robinhood (e.g., `2023_Robinhood_gain_loss.csv`);
- Crypto account activity CSV file by Robinhood (e.g., `2023_Robinhood_crypto_activity.csv`), supports transfers, and switching between the FIFO cost basis method and tax loss harvesting (high cost when selling, low cost when transferring out);
- A one-liner for Morgan Stanley (e.g., `2023_Morgan_Stanley_total.csv`), including the proceeds and cost basis, to append one line for it (assuming no wash sales).

This tool does not check errors, so the results may be wrong if some assumptions I made when implementing the tool is not satisfied.
