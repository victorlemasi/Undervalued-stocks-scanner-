# 📈 Undervalued Stocks Scanner

A Python-based tool that scans a list of stock tickers to identify potentially undervalued investment opportunities using traditional value investing principles and technical indicators.

## 🛠️ How It Works

The scanner evaluates stocks based on six key criteria sets:

1.  **Traditional Value**: Checks for low P/E (< 15) and P/B (< 2) ratios with positive profit margins.
2.  **Quality Metrics**: Looks for strong liquidity (Current Ratio > 1.5), manageable debt (D/E < 100), and healthy operating margins (> 15%).
3.  **Growth at Reasonable Price (GARP)**: Identifies stocks with a low PEG ratio (< 1.5) and solid earnings growth (> 10%).
4.  **Graham Style**: Calculates the **Benjamin Graham Number** and checks if the stock trades below it while offering a decent dividend yield (> 2.5%).
5.  **Profitability**: Filters for high Return on Assets (ROA > 10%) and Return on Equity (ROE > 15%).
6.  **Technical Factors**: Identifies potential "oversold" or "beaten-down" gems trading significantly below their 52-week high and 200-day moving average.

A stock is flagged as a "Top Pick" if it meets **at least 3** of these criteria sets.

## 🚀 Getting Started

### Prerequisites

- Python 3.8+
- Internet connection (to fetch live data from Yahoo Finance)

### Installation

1.  Clone the repository or download the files.
2.  Install the required dependencies using `pip`:

    ```bash
    pip install -r requirements.txt
    ```

### Running the App

Execute the main script to start the analysis:

```bash
python "Version 1.1.py"
```

The app is now **fully interactive**. Upon running, you will be prompted to:
1.  **Market Suffix**: Enter a suffix like `.MX` for Mexico, `.L` for London, etc. (leave blank for US).
2.  **Tweak Thresholds**: Customize the 5 core valuation metrics (P/E, P/B, Dividend Yield, ROE, and Debt/Equity). Press Enter to keep the default value.
3.  **Criteria Threshold**: Choose how many sets of criteria must be met (1-6) to flag a stock as undervalued.

The script will fetch live market data based on these settings, perform the analysis, and output a table of results followed by a detailed investment thesis.

## 📄 Output

- **Summary Table**: Lists tickers, market caps, and key valuation metrics.
- **Investment Thesis**: A detailed breakdown for the top 5 picks, highlighting their specific strengths and potential risks.

---
> [!WARNING]
> This tool is for educational and informational purposes only. It is not financial advice. Always perform your own due diligence before making investment decisions.
