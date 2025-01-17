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

def analyze_stocks(tickers, min_market_cap=1000000000):
    """
    Analyze stocks to find potentially undervalued candidates based on various metrics.
    
    Parameters:
    tickers (list): List of stock ticker symbols to analyze
    min_market_cap (float): Minimum market cap in dollars to consider
    
    Returns:
    pandas.DataFrame: Analysis results for potentially undervalued stocks
    """
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
            
            # Calculate technical indicators
            fifty_two_week_high = hist['High'].max()
            fifty_two_week_low = hist['Low'].min()
            current_price = hist['Close'][-1]
            distance_from_high = ((fifty_two_week_high - current_price) / fifty_two_week_high) * 100
            
            # Calculate 200-day moving average
            ma200 = hist['Close'].rolling(window=200).mean().iloc[-1]
            price_to_ma200 = (current_price / ma200 - 1) * 100

            # Enhanced screening criteria for undervalued stocks
            value_criteria = {
                'Traditional Value': (
                    pe_ratio < 15 and
                    pb_ratio < 2 and
                    profit_margin > 0.1
                ),
                'Quality Metrics': (
                    current_ratio > 1.5 and
                    debt_to_equity < 100 and
                    operating_margin > 15
                ),
                'Growth at Reasonable Price': (
                    peg_ratio < 1.5 and
                    earnings_growth > 10
                ),
                'Graham Style': (
                    graham_number > current_price and
                    dividend_yield > 2.5
                ),
                'Profitability': (
                    roa > 10 and
                    roe > 15
                ),
                'Technical Factors': (
                    distance_from_high > 20 and
                    price_to_ma200 < -10
                )
            }
            
            # Count how many criteria sets are met
            criteria_met = sum(value_criteria.values())
            
            # Consider stock undervalued if it meets at least 3 sets of criteria
            if criteria_met >= 3:
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
    
    Parameters:
    df (pandas.DataFrame): Analysis results from analyze_stocks()
    top_n (int): Number of top stocks to analyze
    
    Returns:
    dict: Detailed analysis and recommendations for top stocks
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
                - {'Low P/E ratio of ' + str(row['P/E Ratio']) if row['P/E Ratio'] < 15 else ''}
                - {'Strong earnings growth of ' + str(row['Earnings Growth (%)']) + '%' if row['Earnings Growth (%)'] > 10 else ''}
                - {'Healthy dividend yield of ' + str(row['Dividend Yield (%)']) + '%' if row['Dividend Yield (%)'] > 2.5 else ''}
                - {'Superior ROE of ' + str(row['ROE (%)']) + '%' if row['ROE (%)'] > 15 else ''}
                
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
                - Industry cyclicality: {row['Industry']}
                - Market cap size: ${row['Market Cap (B)']}B
                - Technical momentum
                
                Recommendation: 
                Consider for value investment portfolio with appropriate position sizing.
                The stock meets multiple value criteria suggesting a potential margin of safety.
            """
        }
        recommendations[row['Ticker']] = analysis
    
    return recommendations

def main():
    # Example usage
    tickers = [
        'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSM', 'ASML',
        'AVGO', 'ORCL', 'CSCO', 'ADBE', 'CRM', 'QCOM', 'INTC', 'AMD',
        'JPM', 'BAC', 'WFC', 'GS', 'MS', 'C', 'BRK-B', 'V', 'MA',
        'JNJ', 'PFE', 'MRK', 'ABBV', 'LLY', 'NVS', 'PG', 'KO', 'PEP'
    ]
    
    # Analyze stocks
    results = analyze_stocks(tickers)
    
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
