import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import numpy as np

def calculate_graham_number(eps, bvps):
    """Calculate Benjamin Graham's number (√(22.5 * EPS * BVPS))"""
    return np.sqrt(22.5 * eps * bvps) if eps > 0 and bvps > 0 else 0

def calculate_peg_ratio(pe_ratio, growth_rate):
    """Calculate PEG ratio"""
    return pe_ratio / growth_rate if growth_rate > 0 else float('inf')

def analyze_stocks(tickers, min_market_cap=1000000000, criteria_threshold=3, custom_thresholds=None):
    """
    Analyze stocks to find potentially undervalued candidates based on various metrics.
    
    Parameters:
    tickers (list): List of stock ticker symbols to analyze
    min_market_cap (float): Minimum market cap in dollars/local currency to consider
    criteria_threshold (int): Minimum number of criteria sets that must be met
    custom_thresholds (dict): User-defined thresholds for valuation metrics
    
    Returns:
    pandas.DataFrame: Analysis results for potentially undervalued stocks
    """
    # Default thresholds
    thresholds = {
        'max_pe': 15,
        'max_pb': 2,
        'min_profit_margin': 0.1,
        'min_current_ratio': 1.5,
        'max_debt_equity': 100,
        'min_operating_margin': 15,
        'max_peg': 1.5,
        'min_earnings_growth': 10,
        'min_div_yield': 2.5,
        'min_roa': 10,
        'min_roe': 15,
        'min_distance_from_high': 20,
        'max_price_to_ma200': -10
    }
    
    if custom_thresholds:
        thresholds.update(custom_thresholds)

    results = []
    
    for ticker in tickers:
        try:
            # Get stock data
            stock = yf.Ticker(ticker)
            info = stock.info
            
            # Skip if market cap is too low
            if info.get('marketCap', 0) < min_market_cap:
                continue
                
            # Get basic financial metrics
            pe_ratio = info.get('forwardPE', float('inf'))
            pb_ratio = info.get('priceToBook', float('inf'))
            profit_margin = info.get('profitMargins', 0)
            current_ratio = info.get('currentRatio', 0)
            debt_to_equity = info.get('debtToEquity', float('inf'))
            
            # Additional value metrics
            eps = info.get('trailingEps', 0)
            bvps = info.get('bookValue', 0)
            graham_number = calculate_graham_number(eps, bvps)
            current_price = info.get('currentPrice', 0)
            dividend_yield = info.get('dividendYield', 0) * 100 if info.get('dividendYield') else 0
            earnings_growth = info.get('earningsGrowth', 0) * 100 if info.get('earningsGrowth') else 0
            peg_ratio = calculate_peg_ratio(pe_ratio, earnings_growth)
            enterprise_value = info.get('enterpriseValue', 0)
            ebitda = info.get('ebitda', 0)
            ev_to_ebitda = enterprise_value / ebitda if ebitda else float('inf')
            operating_margin = info.get('operatingMargins', 0) * 100
            roa = info.get('returnOnAssets', 0) * 100 if info.get('returnOnAssets') else 0
            roe = info.get('returnOnEquity', 0) * 100 if info.get('returnOnEquity') else 0
            
            # Get historical price data for technical analysis
            end_date = datetime.now()
            start_date = end_date - timedelta(days=365)
            hist = stock.history(start=start_date, end=end_date)
            
            if hist.empty:
                continue

            # Calculate technical indicators
            fifty_two_week_high = hist['High'].max()
            fifty_two_week_low = hist['Low'].min()
            current_price = hist['Close'][-1]
            distance_from_high = ((fifty_two_week_high - current_price) / fifty_two_week_high) * 100
            
            # Calculate 200-day moving average
            ma200_series = hist['Close'].rolling(window=200).mean()
            if len(ma200_series) > 0 and not np.isnan(ma200_series.iloc[-1]):
                ma200 = ma200_series.iloc[-1]
                price_to_ma200 = (current_price / ma200 - 1) * 100
            else:
                price_to_ma200 = 0

            # Enhanced screening criteria for undervalued stocks
            value_criteria = {
                'Traditional Value': (
                    pe_ratio < thresholds['max_pe'] and
                    pb_ratio < thresholds['max_pb'] and
                    profit_margin > thresholds['min_profit_margin']
                ),
                'Quality Metrics': (
                    current_ratio > thresholds['min_current_ratio'] and
                    debt_to_equity < thresholds['max_debt_equity'] and
                    operating_margin > thresholds['min_operating_margin']
                ),
                'Growth at Reasonable Price': (
                    peg_ratio < thresholds['max_peg'] and
                    earnings_growth > thresholds['min_earnings_growth']
                ),
                'Graham Style': (
                    graham_number > current_price and
                    dividend_yield > thresholds['min_div_yield']
                ),
                'Profitability': (
                    roa > thresholds['min_roa'] and
                    roe > thresholds['min_roe']
                ),
                'Technical Factors': (
                    distance_from_high > thresholds['min_distance_from_high'] and
                    price_to_ma200 < thresholds['max_price_to_ma200']
                )
            }
            
            # Count how many criteria sets are met
            criteria_met = sum(value_criteria.values())
            
            # Consider stock undervalued if it meets the user-defined threshold
            if criteria_met >= criteria_threshold:
                results.append({
                    'Ticker': ticker,
                    'Company': info.get('longName', 'N/A'),
                    'Market Cap (B)': round(info.get('marketCap', 0) / 1e9, 2),
                    'Criteria Met': criteria_met,
                    # Valuation metrics
                    'P/E Ratio': round(pe_ratio, 2),
                    'P/B Ratio': round(pb_ratio, 2),
                    'EV/EBITDA': round(ev_to_ebitda, 2),
                    'PEG Ratio': round(peg_ratio, 2),
                    # Growth & Income
                    'Earnings Growth (%)': round(earnings_growth, 2),
                    'Dividend Yield (%)': round(dividend_yield, 2),
                    # Profitability metrics
                    'Operating Margin (%)': round(operating_margin, 2),
                    'ROE (%)': round(roe, 2),
                    'ROA (%)': round(roa, 2),
                    # Financial health
                    'Current Ratio': round(current_ratio, 2),
                    'Debt/Equity': round(debt_to_equity, 2),
                    # Technical indicators
                    'Distance from 52w High (%)': round(distance_from_high, 2),
                    'Price to 200MA (%)': round(price_to_ma200, 2),
                    # Additional info
                    'Graham Number': round(graham_number, 2),
                    'Current Price': round(current_price, 2),
                    'Industry': info.get('industry', 'N/A'),
                    # Store which criteria were met for recommendations
                    'Met Criteria': {k: v for k, v in value_criteria.items() if v}
                })
                
        except Exception as e:
            print(f"Error analyzing {ticker}: {str(e)}")
            continue
    
    # Create DataFrame and sort by number of criteria met, then market cap
    df = pd.DataFrame(results)
    if not df.empty:
        df = df.sort_values(['Criteria Met', 'Market Cap (B)'], ascending=[False, False])
    
    return df

def get_stock_recommendations(df, top_n=5):
    """
    Generate detailed recommendations for the top undervalued stocks.
    """
    recommendations = {}
    
    for _, row in df.head(top_n).iterrows():
        met_criteria = row['Met Criteria']
        
        analysis = {
            'Company': row['Company'],
            'Analysis': f"""
                Investment Thesis:
                {row['Company']} shows strong value characteristics across {len(met_criteria)} major criteria:
                {', '.join(met_criteria.keys())}
                
                Key Strengths:
                - {'P/E ratio of ' + str(row['P/E Ratio']) if row['P/E Ratio'] != float('inf') else 'N/A'}
                - {'Earnings growth of ' + str(row['Earnings Growth (%)']) + '%' if row['Earnings Growth (%)'] > 0 else 'N/A'}
                - {'Dividend yield of ' + str(row['Dividend Yield (%)']) + '%' if row['Dividend Yield (%)'] > 0 else 'N/A'}
                - {'ROE of ' + str(row['ROE (%)']) + '%' if row['ROE (%)'] > 0 else 'N/A'}
                
                Valuation Metrics:
                - EV/EBITDA: {row['EV/EBITDA']}
                - PEG Ratio: {row['PEG Ratio']}
                - Trading at {row['Distance from 52w High (%)']}% below 52-week high
                - Price is {abs(row['Price to 200MA (%)']):,.1f}% {'below' if row['Price to 200MA (%)'] < 0 else 'above'} 200-day moving average
                
                Financial Health:
                - Operating Margin: {row['Operating Margin (%)']}%
                - Current Ratio: {row['Current Ratio']}
                - Debt/Equity: {row['Debt/Equity']}
                
                Risk Factors:
                - Industry: {row['Industry']}
                - Market Cap: ${row['Market Cap (B)']}B
                
                Recommendation: 
                The stock meets multiple value criteria suggesting a potential margin of safety.
            """
        }
        recommendations[row['Ticker']] = analysis
    
    return recommendations

def get_user_input(prompt, default_value, value_type=float):
    user_val = input(f"{prompt} [{default_value}]: ").strip()
    if not user_val:
        return default_value
    try:
        return value_type(user_val)
    except ValueError:
        print(f"Invalid input. Using default: {default_value}")
        return default_value

def main():
    print("--- Undervalued Stocks Scanner Settings ---")
    
    # Stock Market Choice
    suffix = input("Enter market suffix (e.g., .MX for Mexico, leave blank for US): ").strip()
    
    # Thresholds Tweaking
    print("\nSet your scouting criteria thresholds:")
    custom_thresholds = {
        'max_pe': get_user_input("Max P/E Ratio", 15),
        'max_pb': get_user_input("Max P/B Ratio", 2),
        'min_div_yield': get_user_input("Min Dividend Yield (%)", 2.5),
        'min_roe': get_user_input("Min ROE (%)", 15),
        'max_debt_equity': get_user_input("Max Debt/Equity Ratio", 100),
    }

    # Overall Threshold
    criteria_threshold = get_user_input("\nHow many criteria sets must be met? (1-6)", 3, int)

    # Market Cap Threshold
    print("\nMinimum Market Cap Settings:")
    print("Example: 1000000000 for $1B, 50000000 for $50M")
    min_market_cap = get_user_input("Min Market Cap", 1000000000, float)

    # Example tickers (US by default)
    base_tickers = [
        'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSM', 'ASML',
        'AVGO', 'ORCL', 'CSCO', 'ADBE', 'CRM', 'QCOM', 'INTC', 'AMD',
        'JPM', 'BAC', 'WFC', 'GS', 'MS', 'C', 'BRK-B', 'V', 'MA',
        'JNJ', 'PFE', 'MRK', 'ABBV', 'LLY', 'NVS', 'PG', 'KO', 'PEP'
    ]
    
    # Mexican market examples if .MX is specified
    if suffix.upper() == '.MX':
        base_tickers = ['WALMEX', 'AMXL', 'FEMSAUBD', 'GFNORTEO', 'GMEXICOB', 'CEMEXCPO', 'TLEVISACPO']

    tickers = [t + suffix if not t.endswith(suffix) else t for t in base_tickers]
    
    print(f"\nAnalyzing {len(tickers)} stocks with Min Market Cap ${min_market_cap:,.0f}...")
    
    # Analyze stocks
    results = analyze_stocks(tickers, min_market_cap=min_market_cap, criteria_threshold=criteria_threshold, custom_thresholds=custom_thresholds)
    
    # Print results
    if not results.empty:
        print("\nPotentially Undervalued Stocks:")
        print(results.to_string(index=False))
        
        # Get detailed recommendations
        recommendations = get_stock_recommendations(results)
        
        print("\nDetailed Analysis of Top Picks:")
        for ticker, analysis in recommendations.items():
            print(f"\n{ticker} - {analysis['Company']}")
            print(analysis['Analysis'])
    else:
        print("No stocks meeting the undervalued criteria were found.")

if __name__ == "__main__":
    main()
