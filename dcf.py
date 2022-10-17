"""
DCF calculator:
    - Take revenues, net income, EBITDA from xls
    - Amortization, Accounts Payable / Receivable, CAPEX, Inventories
    - Assume IRR (later scrap WACC)
    - Calculate FCF projection based on assumptions (maybe first averages, later introduce more options)
    - Assume long-term growth
    - Calculate PV of future FCF
    - Deduct Debt
    - Divide by number of shares to obtain fair value
    - Account for margin of safety
    -
"""
### DCF calculator
# packages
import time
import re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
# import pandas_datareader.data as web
# from pandas.api.types import CategoricalDtype
import os
import datetime
from datetime import date
from datetime import datetime
# from sp500_tickers import sp500_tickers, sp500_yf_tickers

### FUNCTIONS ###
# TBD

### INPUT ###
#input tickers creating a list with all input data
path_ = r"\\emea.ad.jpmorganchase.com\home\xbus\xb\emvdihome76\D628748\HomeData\jpmDesk\Desktop\Projects\valuations"
#tickers = input('Tickers (separated by ",": ')
#z = list(map(str,tickers.split(',')))
z = ["GOOGL"] # sp500_tickers
# Run table
# Including all relevant parameters per scenario specified
# Run 1 - Baseline, IRR = 10%
# Run 2 - IRR = 7.5%
# Run 3 - IRR = 12.5%
# Run 4 - No years proj = 5 years
# Run 5 - No years ratios, rev growth = 5 years
# Run 6 - Income ratio 50%
# Run 7 - Revenue growth 50%
# Run 8 - Double CAPEX
run_table = pd.DataFrame(columns = ['RUN_1', 'RUN_2', 'RUN_3', 'RUN_4',
                                    'RUN_5', 'RUN_6', 'RUN_7', 'RUN_8'], 
                         index = ['IRR', 'no_years_proj_', 'no_years_ratios_', '_avg_inc_ratio_shock_',
                                    'no_years_rev_gwth_', '_rev_gwth_shock_', '_avg_capex_ratio_shock_',
                                    'lng_term_gwth_', 'mos_'])
# IRR
run_table.loc["IRR"] =                     [0.1, 0.075, 0.125, 0.1, 0.1, 0.1, 0.1, 0.1]
run_table.loc["no_years_proj_"] =          [10, 10, 10, 5, 10, 10, 10, 10]
run_table.loc["no_years_ratios_"] =        [10, 10, 10, 10, 5, 10, 10, 10]
run_table.loc["_avg_inc_ratio_shock_"] =   [1, 1, 1, 1, 1, 0.5, 1, 1]
run_table.loc["no_years_rev_gwth_"] =      [10, 10, 10, 10, 5, 10, 10, 10]
run_table.loc["_rev_gwth_shock_"] =        [1, 1, 1, 1, 1, 1, 0.5, 1]
run_table.loc["_avg_capex_ratio_shock_"] = [1, 1, 1, 1, 1, 1, 1, 2]
run_table.loc["lng_term_gwth_"] =          [0.02, 0.02, 0.02, 0.02, 0.02, 0.02, 0.02, 0.02]
run_table.loc["mos_"] =                    [0.15, 0.15, 0.15, 0.15, 0.15, 0.15, 0.15, 0.15]
##############


# Define output storing all the results
out = pd.DataFrame(columns = ['Ticker', 'Revenue Growth', 'Margin of Safety'] + run_table.columns.tolist() + 
                              ['P/E = 10', 'P/E = 15', 'P/E = 20',
                              'P/B = 1', 'P/B = 1.5', 'P/B = 2',
                              'P/S = 1', 'P/S = 3', 'P/S = 5',
                              'NCAV', 'Curr Assets min Tot Liab per share', 'Stock price'])
j = 0
for i in z:
#    print(i)
    ### IMPORT DATA ###
    # Source data
    input_ = pd.read_excel(path_ + "/" + i + "/" + i + ".xlsx", index_col = 0)
    # Remove duplicate rows
    input_ = input_[~input_.index.duplicated(keep = 'last')]
    ### BUILD CASH FLOWS ###
    # Select variables needed in the DCF
    input_to_DCF = input_[["Revenue", "NetIncome", "EBITDA", "EBIT", "IncomeAfterTaxes", "TotalDepreciationAndAmortization-CashFlow", \
                           "CashOnHand","ChangeInInventories", "ChangeInAccountsReceivable", "ChangeInAccountsPayable", "NetChangeInProperty.Plant.AndEquipment", "Inventory", \
                           "FreeCashFlowPerShare", "SharesOutstanding",\
                           "TotalLongTermLiabilities"]]
    # Calculate YoY percentage growth
    input_to_DCF["RevenueGrowth"] = input_["Revenue"].pct_change(periods = 1)
    # Calculate as % of Revenue:
    # - EBITDA
    # - Depreciation
    # - Inventories
    # - Accounts Payable / Receivable
    # - CAPEX
    vars_as_perc = ["EBITDA", "EBIT", "IncomeAfterTaxes", "TotalDepreciationAndAmortization-CashFlow", "ChangeInInventories", "ChangeInAccountsReceivable", "ChangeInAccountsPayable", "Inventory", "NetChangeInProperty.Plant.AndEquipment"]
    for n in vars_as_perc:
        input_to_DCF[n + "_in_perc_of_rev"] = input_to_DCF[n] / input_to_DCF["Revenue"]
    # Calculate a change in Inventory
    # input_to_DCF["ChangeinInventory"] = input_["Inventory"].transform('diff')
    # Calculate historical FCF from components and compare to FCF per share * No shares outstanding
    input_to_DCF["FCF_by_component"] = input_to_DCF["IncomeAfterTaxes"] + input_["TotalDepreciationAndAmortization-CashFlow"] + \
                                       input_to_DCF["ChangeInAccountsReceivable"] + input_to_DCF["ChangeInAccountsPayable"] + \
                                       input_to_DCF["ChangeInInventories"] + input_to_DCF["NetChangeInProperty.Plant.AndEquipment"]
   
    # input_to_DCF["ChangeinInventory_in_perc_of_rev"] = input_to_DCF['ChangeinInventory'] / input_to_DCF["Revenue"]
    input_to_DCF["FCF_historical"] = input_to_DCF['FreeCashFlowPerShare'] * input_to_DCF['SharesOutstanding'] / 1000
    # print("FCF by component - FCF per share * No Shares: ", input_to_DCF["FCF_by_component"] - input_to_DCF["FCF_historical"])

    for j in range(len(run_table.columns)):
        # Define parameters for a specific run
        irr_ = run_table["RUN_" + str(j + 1)]["IRR"]
        no_years_ = run_table["RUN_" + str(j + 1)]["no_years_proj_"]
        no_years_ratios_ = run_table["RUN_" + str(j + 1)]["no_years_ratios_"]
        _avg_inc_ratio_shock_ = run_table["RUN_" + str(j + 1)]['_avg_inc_ratio_shock_']
        no_years_rev_gwth_ = run_table["RUN_" + str(j + 1)]["no_years_rev_gwth_"]
        _rev_gwth_shock_ = run_table["RUN_" + str(j + 1)]["_rev_gwth_shock_"]
        _avg_capex_ratio_shock_ = run_table["RUN_" + str(j + 1)]["_avg_capex_ratio_shock_"]
        lng_term_gwth_ = run_table["RUN_" + str(j + 1)]["lng_term_gwth_"]
        mos_ = run_table["RUN_" + str(j + 1)]["mos_"]
        # Project revenue
        if datetime.strptime(input_to_DCF.index[0], '%Y-%m-%d').month == 3:
            proj_index = pd.date_range(date(datetime.strptime(input_to_DCF.index[-1], '%Y-%m-%d').year, datetime.strptime(input_to_DCF.index[-1], '%Y-%m-%d').month, datetime.strptime(input_to_DCF.index[-1], '%Y-%m-%d').day), \
                                       periods=no_years_, freq = 'AS-MAR')
        elif datetime.strptime(input_to_DCF.index[0], '%Y-%m-%d').month == 6:
            proj_index = pd.date_range(date(datetime.strptime(input_to_DCF.index[-1], '%Y-%m-%d').year, datetime.strptime(input_to_DCF.index[-1], '%Y-%m-%d').month, datetime.strptime(input_to_DCF.index[-1], '%Y-%m-%d').day), \
                                       periods=no_years_, freq = 'AS-JUN')
        elif datetime.strptime(input_to_DCF.index[0], '%Y-%m-%d').month == 9:
            proj_index = pd.date_range(date(datetime.strptime(input_to_DCF.index[-1], '%Y-%m-%d').year, datetime.strptime(input_to_DCF.index[-1], '%Y-%m-%d').month, datetime.strptime(input_to_DCF.index[-1], '%Y-%m-%d').day), \
                                       periods=no_years_, freq = 'AS-SEP')
        else:
            proj_index = pd.date_range(date(datetime.strptime(input_to_DCF.index[-1], '%Y-%m-%d').year, datetime.strptime(input_to_DCF.index[-1], '%Y-%m-%d').month, datetime.strptime(input_to_DCF.index[-1], '%Y-%m-%d').day), \
                                       periods=no_years_, freq = 'AS-DEC')
        DCF_proj = input_to_DCF.append(pd.DataFrame(index=proj_index))
        # Start with average revenue growth in the last n years
        _avg_rev_growth = _rev_gwth_shock_ * np.average(input_to_DCF["RevenueGrowth"][-no_years_rev_gwth_:])
        DCF_proj["Revenue"][proj_index] =  [input_to_DCF["Revenue"][-1] * (1 + _avg_rev_growth) ** (x + 1) for x in range(no_years_)]
        # Calculate average of ratios from the last N years
        _avg_inc_ratio_ = _avg_inc_ratio_shock_ * np.average(input_to_DCF["IncomeAfterTaxes_in_perc_of_rev"][-no_years_ratios_:])
        _avg_dep_ratio_ = np.average(input_to_DCF["TotalDepreciationAndAmortization-CashFlow_in_perc_of_rev"][-no_years_ratios_:])
        _avg_acc_rec_ratio_ = np.average(input_to_DCF["ChangeInAccountsReceivable_in_perc_of_rev"][-no_years_ratios_:])
        _avg_acc_pay_ratio_ = np.average(input_to_DCF["ChangeInAccountsPayable_in_perc_of_rev"][-no_years_ratios_:])
        _avg_inv_ratio_ = np.average(input_to_DCF["ChangeInInventories_in_perc_of_rev"][-no_years_ratios_:])
        _avg_capex_ratio_ = _avg_capex_ratio_shock_ * np.average(input_to_DCF["NetChangeInProperty.Plant.AndEquipment_in_perc_of_rev"][-no_years_ratios_:])
        # Calculate projections per item
        DCF_proj["IncomeAfterTaxes"][proj_index] =  DCF_proj["Revenue"][proj_index] * _avg_inc_ratio_
        DCF_proj["TotalDepreciationAndAmortization-CashFlow"][proj_index] =  DCF_proj["Revenue"][proj_index] * _avg_dep_ratio_
        DCF_proj["ChangeInAccountsReceivable"][proj_index] =  DCF_proj["Revenue"][proj_index] * _avg_acc_rec_ratio_
        DCF_proj["ChangeInAccountsPayable"][proj_index] =  DCF_proj["Revenue"][proj_index] * _avg_acc_pay_ratio_
        DCF_proj["ChangeInInventories"][proj_index] =  DCF_proj["Revenue"][proj_index] * _avg_inv_ratio_
        DCF_proj["NetChangeInProperty.Plant.AndEquipment"][proj_index] =  DCF_proj["Revenue"][proj_index] * _avg_capex_ratio_
        # Combine into FCF projection
        DCF_proj["FCF_by_component"][proj_index] = DCF_proj["IncomeAfterTaxes"][proj_index] + \
                                                   DCF_proj["TotalDepreciationAndAmortization-CashFlow"][proj_index] + \
                                                   DCF_proj["ChangeInAccountsReceivable"][proj_index] + \
                                                   DCF_proj["ChangeInAccountsPayable"][proj_index] + \
                                                   DCF_proj["ChangeInInventories"][proj_index] + \
                                                   DCF_proj["NetChangeInProperty.Plant.AndEquipment"][proj_index]
        # Discount based on different IRRs
        if j == 0:
            out = out.append({'Ticker': str(i),
                        'Revenue Growth' : _avg_rev_growth,
                        'Margin of Safety': mos_}, ignore_index = True)
        # Calculate sum of PV of future FCF
        PV_FCF = sum([DCF_proj["FCF_by_component"][proj_index][x] * (1 + irr_) ** (-(x + 1)) for x in range(no_years_)])
        # Terminal Value
        TV = DCF_proj["FCF_by_component"][-1] * (1 + lng_term_gwth_) / (irr_ - lng_term_gwth_)
        PV_TV = TV / (1 + irr_) ** (no_years_)
        # Intrinsic Value = Enterprise Value  - Net Debt
        EV = PV_TV + DCF_proj["FCF_by_component"][-1]
        IV = EV - (input_to_DCF["TotalLongTermLiabilities"][-1] - input_to_DCF["CashOnHand"][-1])
        # Share price
        share_price = IV / input_to_DCF["SharesOutstanding"][-1]
        # After margin of safety
        share_price_aft_mos = share_price * (1 - mos_)
        # Results
#        print("***************************************")
#        print("Share price of ", i, ":", share_price)
#        print("After margin of safety equal to", mos_, ":", share_price_aft_mos)
#        print("Assmued IRR:", irr_)
#        print("Assmued Revenue growth from the last ", no_years_rev_gwth_, "years:", _avg_rev_growth)
#        print("***************************************")

        #out.at[j, str('RUN_') + str(j + 1)] = share_price
        print(i)
        print(str('RUN_') + str(j))
        out.at[z.index(i), str('RUN_') + str(j + 1)] = share_price_aft_mos
    # Add new valuation options:
    # Last year earnings * (P/E = 10)
    val_pe_10 = input_["EPS-EarningsPerShare"][-1] * 10
    # Last year earnings * (P/E = 10)
    val_pe_15 = input_["EPS-EarningsPerShare"][-1] * 15
    # Last year earnings * (P/E = 10)
    val_pe_20 = input_["EPS-EarningsPerShare"][-1] * 20
    # Book value * (P/B = 1)
    val_pb_1 = input_["BookValuePerShare"][-1] * 1
    # Book value * (P/B = 1.5)
    val_pb_1_5 = input_["BookValuePerShare"][-1] * 1.5
    # Book value * (P/B = 2)
    val_pb_2 = input_["BookValuePerShare"][-1] * 2
    # Revenue * (P/S = 1)
    val_ps_1 = input_["Revenue"][-1] / input_["SharesOutstanding"][-1]
    # Revenue * (P/S = 3)
    val_ps_3 = input_["Revenue"][-1] / input_["SharesOutstanding"][-1] * 3
    # Revenue * (P/S = 5)
    val_ps_5 = input_["Revenue"][-1] / input_["SharesOutstanding"][-1] * 5
    # NCAV / No Shares
    val_ncav = (input_["TotalCurrentAssets"][-1] - input_["TotalCurrentLiabilities"][-1]) / input_["SharesOutstanding"][-1]
    # (Curr Assets - Tot Liab) / No Shares
    val_ca_min_totliab = (input_["TotalCurrentAssets"][-1] - input_["TotalLiabilities"][-1]) / input_["SharesOutstanding"][-1]
   
    # Discount based on different IRRs
    out.at[z.index(i), 'P/E = 10'] = float(val_pe_10)
    out.at[z.index(i),'P/E = 15'] = float(val_pe_15)
    out.at[z.index(i),'P/E = 20'] = float(val_pe_20)
    out.at[z.index(i),'P/B = 1'] = float(val_pb_1)
    out.at[z.index(i),'P/B = 1.5'] = float(val_pb_1_5)
    out.at[z.index(i),'P/B = 2'] = float(val_pb_2)
    out.at[z.index(i),'P/S = 1'] = float(val_ps_1)
    out.at[z.index(i),'P/S = 3'] = float(val_ps_3)
    out.at[z.index(i),'P/S = 5'] = float(val_ps_5)
    out.at[z.index(i),'NCAV'] = float(val_ncav)
    out.at[z.index(i),'Curr Assets min Tot Liab per share'] = float(val_ca_min_totliab)
    # Add stock price
    out.at[z.index(i),'Stock price'] = float(stock_price)
    
    # write to csv
    out.to_csv(os.path.join(path_ + "/GOOGL/DCF_out.csv"))
   
 
    

## Import share prices
#import yfinance as yf
#
#out_ticker = pd.DataFrame(columns = ["Ticker", "Stock Price"])
#
#k = 0
#for i in sp500_yf_tickers:
#    print(i)
#    #define the ticker symbol
#    tickerSymbol = i
#   
#    #get data on this ticker
#    tickerData = yf.Ticker(tickerSymbol)
#   
#    #get the historical prices for this ticker
#    tickerDf = tickerData.history(period='1d')
#   
#    #see your data
#    out_ticker = out_ticker.append({"Ticker": str(i), "Stock Price": tickerDf['Close'][0]}, ignore_index = True)
#    k += 1
#out_ticker.to_csv(os.path.join("STOCKUS/stock_prices.csv"))


