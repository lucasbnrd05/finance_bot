# financial_data.py
import yfinance as yf
import pandas as pd
import numpy as np

# --- Configuration des Tickers (gardez vos listes étendues ici) ---
DEFAULT_ETF_TICKERS = [
    "SPY", "QQQ", "VOO", "VTI", "DIA", "XLK", "XLF", "XLV", "XLE", "XLY", "XLP", "XLU", "XLB", "XLI", "XLRE",
    "VEA", "VWO", "IEUR", "EWJ", "EWG", "EWQ", "AGG", "BND", "GLD", "SLV", "USO",
    "CW8.PA", "EWLD.PA", "C40.PA", "LYXNAS.PA", "BNPPRE.PA", "PME.PA", "ESE.PA", "CE2.PA", "EUNK.PA", "AEEM.PA"
]
DEFAULT_ACTION_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META", "AVGO", "CRM",
    "BRK-B", "JPM", "V", "JNJ", "PG", "UNH", "HD", "XOM", "LLY", "MA", "BAC", "CVX", "KO", "PEP",
    "MC.PA", "OR.PA", "TTE.PA", "SAN.PA", "AIR.PA", "RMS.PA", "SAF.PA", "BNP.PA", "KER.PA", "ACA.PA",
    "DG.PA", "SGO.PA", "AI.PA", "EL.PA", "VIE.PA", "GLE.PA", "CAP.PA", "STM.PA",
    "NESN.SW", "NOVN.SW", "ROG.SW", "ASML.AS", "SAP.DE", "SIE.DE", "VOW3.DE", "IBE.MC"
]

# --- SCORING HEURISTIQUE LONG TERME ---
# ATTENTION: Ces scores sont hautement simplifiés et ne garantissent rien.
# Ils sont basés sur des indicateurs généraux. Faites TOUJOURS vos propres recherches.

def normalize_value(value, good_range_min, good_range_max, lower_is_better=False):
    """Normalise une valeur entre 0 et 10. Assure que value est un float."""
    if value is None:
        return 0 # Pas de contribution si la donnée manque
    try:
        value = float(value)
    except (ValueError, TypeError):
        return 0

    if lower_is_better:
        # Si value est meilleure (plus basse) que good_range_min, score max.
        # Si value est pire (plus haute) que good_range_max, score min.
        if value <= good_range_min: return 10
        if value >= good_range_max: return 0
        return 10 * (good_range_max - value) / (good_range_max - good_range_min)
    else:
        # Si value est meilleure (plus haute) que good_range_max, score max.
        # Si value est pire (plus basse) que good_range_min, score min.
        if value >= good_range_max: return 10
        if value <= good_range_min: return 0
        return 10 * (value - good_range_min) / (good_range_max - good_range_min)

def calculate_long_term_stock_score(info):
    score = 0
    weights = {
        "profit_margin": 0.25,  # Marge bénéficiaire nette
        "revenue_growth": 0.15, # Croissance des revenus (TTM)
        "roe": 0.20,            # Return on Equity
        "forward_pe": 0.20,     # Forward P/E (valorisation)
        "debt_to_equity": 0.10, # Endettement
        "dividend_sustainability": 0.10 # Dividende (si applicable et soutenable)
    }

    # 1. Marge Bénéficiaire (profitMargins)
    pm = info.get('profitMargins') # ex: 0.1 pour 10%
    score += weights["profit_margin"] * normalize_value(pm, 0.05, 0.25) # Bon entre 5% et 25%+

    # 2. Croissance des Revenus (revenueGrowth - TTM, donc proxy limité)
    rg = info.get('revenueGrowth') # ex: 0.1 pour 10%
    score += weights["revenue_growth"] * normalize_value(rg, 0.03, 0.20) # Bon entre 3% et 20%+

    # 3. Return on Equity (returnOnEquity)
    roe = info.get('returnOnEquity') # ex: 0.15 pour 15%
    score += weights["roe"] * normalize_value(roe, 0.10, 0.30) # Bon entre 10% et 30%+

    # 4. Forward P/E (forwardPE) - Plus bas est mieux (avec limites)
    fpe = info.get('forwardPE')
    if fpe is not None and fpe < 5 : fpe = 5 # Eviter P/E trop bas qui peuvent être des pièges
    score += weights["forward_pe"] * normalize_value(fpe, 10, 35, lower_is_better=True) # Bon entre 10 et 35

    # 5. Debt to Equity (debtToEquity) - Plus bas est mieux
    dte = info.get('debtToEquity')
    if dte is not None: # Peut être négatif si fonds propres négatifs
         score += weights["debt_to_equity"] * normalize_value(dte, 0.1, 1.5, lower_is_better=True) # Bon entre 0.1 et 1.5

    # 6. Soutenabilité du dividende (si applicable)
    div_yield = info.get('dividendYield')
    payout_ratio = info.get('payoutRatio')
    if div_yield is not None and div_yield > 0:
        if payout_ratio is not None and 0 < payout_ratio < 0.75: # Payout ratio raisonnable
            score += weights["dividend_sustainability"] * normalize_value(div_yield, 0.01, 0.05) # Bon rendement entre 1-5%
        # elif payout_ratio is None: # Si payout non dispo mais dividende existe, petite contribution
        #     score += (weights["dividend_sustainability"] / 2) * normalize_value(div_yield, 0.01, 0.05)

    return round(score, 2) if pd.notna(score) and np.isfinite(score) else -1000.0

def calculate_long_term_etf_score(info):
    score = 0
    weights = {
        "5y_return": 0.6,
        "expense_ratio": 0.4
    }
    # 1. Performance 5 ans (fiveYearAverageReturn)
    ret_5y = info.get('fiveYearAverageReturn')
    if ret_5y is None: ret_5y = info.get('threeYearAverageReturn') # Fallback 3 ans
    score += weights["5y_return"] * normalize_value(ret_5y, 0.03, 0.15) # Bon entre 3% et 15%+ annuel

    # 2. Expense Ratio (annualReportExpenseRatio) - Souvent non disponible
    er = info.get('annualReportExpenseRatio')
    # Si non dispo, on ne pénalise pas trop, mais on ne peut pas scorer positivement.
    # On pourrait mettre une pénalité par défaut si non trouvé, ou ignorer.
    if er is not None:
        score += weights["expense_ratio"] * normalize_value(er, 0.001, 0.0075, lower_is_better=True) # Frais bons entre 0.1% et 0.75%
    else: # Si frais non trouvés, on ne peut pas vraiment scorer cette partie
        score += weights["expense_ratio"] * 2 # Petite contribution par défaut si pas de frais, ou ne rien ajouter

    return round(score, 2) if pd.notna(score) and np.isfinite(score) else -1000.0

def get_stock_data_with_score(ticker_symbol, is_etf=False, score_type="long_term"):
    """
    score_type peut être "long_term" ou un autre type futur.
    Retourne un dict avec données formatées et score.
    """
    raw_data = {"ticker": ticker_symbol, "raw_price": None, "formatted_string": f"{ticker_symbol}: Données indisponibles",
                "name": ticker_symbol, "score": -1000.0, "info_dict": {}}
    try:
        ticker = yf.Ticker(ticker_symbol)
        info = ticker.info
        raw_data["info_dict"] = info

        name = info.get('longName', info.get('shortName', ticker_symbol))
        raw_data["name"] = name
        price = info.get('currentPrice', info.get('regularMarketPrice', info.get('previousClose')))
        currency = info.get('currency', '')

        current_score = -1000.0
        if info and price is not None:
            raw_data["raw_price"] = float(price)
            if score_type == "long_term":
                current_score = calculate_long_term_etf_score(info) if is_etf else calculate_long_term_stock_score(info)
            # Ajouter d'autres types de scores ici si besoin
            raw_data["score"] = current_score

            change_val = info.get('regularMarketChange')
            change_pct_val = info.get('regularMarketChangePercent')
            change_str = f"{change_val:+.2f}" if change_val is not None else "N/A"
            change_pct_str = f"{change_pct_val * 100:+.2f}%" if change_pct_val is not None else "N/A"

            price_str = f"{price:.2f}" if price is not None else "N/A"
            raw_data["formatted_string"] = f"{name} ({ticker_symbol}): {price_str} {currency} ({change_str} {currency}, {change_pct_str})"
        else: # Si pas de prix ou d'info
            raw_data["formatted_string"] = f"{name} ({ticker_symbol}): Données de prix/infos de base manquantes"


    except Exception as e:
        # print(f"Erreur get_stock_data_with_score pour {ticker_symbol}: {e}") # Pour debug
        raw_data["formatted_string"] = f"{ticker_symbol}: Erreur récupération données"

    return raw_data

def get_selected_items_formatted(item_type="ETF", limit=10, sort_by_score=True, score_type="long_term"):
    is_etf = item_type.upper() == "ETF"
    tickers_list = DEFAULT_ETF_TICKERS if is_etf else DEFAULT_ACTION_TICKERS
    
    # Adaptez le titre en fonction du tri et du type de score
    sort_description = ""
    if sort_by_score:
        if score_type == "long_term":
            sort_description = "par Potentiel LT (Score Desc.)"
        # Ajoutez d'autres descriptions pour d'autres types de scores
        else:
            sort_description = "par Score Desc."
    
    title_prefix = f"📈 **ETFs {sort_description}:**" if is_etf else f"📊 **Actions {sort_description}:**"
    if not sort_by_score: # Si pas de tri par score, titre générique
        title_prefix = f"📈 **ETFs Sélectionnés :**" if is_etf else f"📊 **Actions Sélectionnées :**"

    # Récupérer un peu plus de données pour avoir une meilleure sélection après filtrage et tri
    data_objects = [get_stock_data_with_score(ticker, is_etf, score_type) for ticker in tickers_list[:int(limit * 1.5)]]

    # Filtrer les données invalides (score très bas signifie souvent un problème de données)
    valid_data = [d for d in data_objects if d["score"] > -999.0 and d["raw_price"] is not None]
    
    if sort_by_score and valid_data:
        valid_data.sort(key=lambda x: x["score"], reverse=True)

    # Construire la liste formatée finale
    final_formatted_list = []
    for d in valid_data[:limit]:
        # Inclure le score dans l'affichage si trié par score
        score_display = f" (Score LT: {d['score']:.1f})" if sort_by_score and score_type=="long_term" else ""
        final_formatted_list.append(f"{d['formatted_string']}{score_display}")
    
    if not final_formatted_list:
        final_formatted_list.append("_Aucune donnée exploitable trouvée pour le classement actuel._")
    elif len(valid_data) < limit:
         final_formatted_list.append("\n_Moins d'éléments que demandé ont pu être classés._")

    return title_prefix + "\n" + "\n".join(final_formatted_list)

# --- Fonctions de récupération de données détaillées (inchangées par rapport à la version précédente) ---
def get_detailed_stock_data(ticker_symbol):
    try:
        ticker = yf.Ticker(ticker_symbol)
        info = ticker.info
        if not info or info.get('regularMarketPrice') is None and info.get('currentPrice') is None and info.get('previousClose') is None :
            hist = ticker.history(period="1d")
            if hist.empty:
                 return {"error": f"Aucune donnée pour {ticker_symbol} (invalide/délisté?)."}
        data = {
            "ticker": ticker_symbol, "longName": info.get('longName'), "shortName": info.get('shortName'), "currency": info.get('currency'),
            "currentPrice": info.get('currentPrice', info.get('regularMarketPrice', info.get('previousClose'))),
            "previousClose": info.get('previousClose'), "dayHigh": info.get('dayHigh'), "dayLow": info.get('dayLow'),
            "fiftyTwoWeekHigh": info.get('fiftyTwoWeekHigh'), "fiftyTwoWeekLow": info.get('fiftyTwoWeekLow'),
            "regularMarketChange": info.get('regularMarketChange'), "regularMarketChangePercent": info.get('regularMarketChangePercent'),
            "marketCap": info.get('marketCap'), "volume": info.get('regularMarketVolume', info.get('volume')),
            "averageVolume": info.get('averageVolume'), "trailingPE": info.get('trailingPE'), "forwardPE": info.get('forwardPE'),
            "dividendYield": info.get('dividendYield'), "payoutRatio": info.get('payoutRatio'), "beta": info.get('beta'),
            "sector": info.get('sector'), "industry": info.get('industry'), "website": info.get('website'),
            "longBusinessSummary": info.get('longBusinessSummary')
        }
        return data
    except Exception as e:
        return {"error": f"Erreur récupération données détaillées pour {ticker_symbol}: {str(e)}"}

def get_company_officers(ticker_symbol):
    try:
        ticker = yf.Ticker(ticker_symbol)
        short_name = ticker.info.get('shortName', ticker_symbol)
        officers = ticker.info.get('companyOfficers', [])
        if not officers: return f"Aucune info dirigeant pour {short_name}."
        
        officers_info_list = [f"- {o.get('name')} ({o.get('title')})" for o in officers if o.get('name') and o.get('title')]
        if not officers_info_list: return f"Aucune info détaillée dirigeant pour {short_name}."
        
        return f"🧑‍💼 **Dirigeants de {short_name}:**\n" + "\n".join(officers_info_list)
    except Exception as e:
        return f"Erreur récupération dirigeants pour {ticker_symbol}: {str(e)}"

# if __name__ == '__main__':
#     print("--- Actions triées par Potentiel Long Terme (Score Desc.) ---")
#     print(get_selected_items_formatted(item_type="ACTION", limit=10, sort_by_score=True, score_type="long_term"))
#     print("\n" + "="*40 + "\n")
#     print("--- ETFs triés par Potentiel Long Terme (Score Desc.) ---")
#     print(get_selected_items_formatted(item_type="ETF", limit=10, sort_by_score=True, score_type="long_term"))
#     # print("\n--- Test détaillé AAPL ---")
#     # print(get_detailed_stock_data("AAPL"))