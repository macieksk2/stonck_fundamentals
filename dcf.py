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
import pandas_datareader.data as web
from pandas.api.types import CategoricalDtype
import os
import datetime
from datetime import date
from datetime import datetime

### FUNCTIONS ###
# TBD

### INPUT ###
#input tickers creating a list with all input data
path_ = ".../STOCKUS"
tickers = input('Tickers (separated by ",": ')
z = list(map(str,tickers.split(',')))
# Assumed IRR (list of values)
irr_ = [0.075, 0.1, 0.125]
# No years in projection
no_years_ = 10 # 5
# No years for averaging ratios
no_years_ratios_ = 5
# No years for avg revenue growth
no_years_rev_gwth_ = 5
# Long-term growth
lng_term_gwth_ = 0.02
# Margin of Safety
mos_ = 0.15
#############

for i in z:
    ### IMPORT DATA ###
    # Source data
    input_ = pd.read_excel(path_ + "/" + i + "/" + i + ".xlsx", index_col = 0)
    # Remove duplicate rows
    input_ = input_[~input_.index.duplicated(keep = 'last')]
    ### BUILD CASH FLOWS ###
    # Select variables needed in the DCF
    input_to_DCF = input_[["Revenue", "NetIncome", "EBITDA", "EBIT", "IncomeAfterTaxes", "TotalDepreciationAndAmortization-CashFlow", \
                           "CashOnHand", "ChangeInAccountsReceivable", "ChangeInAccountsPayable", "NetChangeInPropertyPlantAndEquipment", "Inventory", \
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
    vars_as_perc = ["EBITDA", "EBIT", "IncomeAfterTaxes", "TotalDepreciationAndAmortization-CashFlow","ChangeInAccountsReceivable", "ChangeInAccountsPayable", "Inventory", "NetChangeInPropertyPlantAndEquipment"]
    for n in vars_as_perc:
        input_to_DCF[n + "_in_perc_of_rev"] = input_to_DCF[n] / input_to_DCF["Revenue"]
    # Calculate a change in Inventory
    input_to_DCF["ChangeinInventory"] = input_["Inventory"].transform('diff')
    # Calculate historical FCF from components and compare to FCF per share * No shares outstanding
    input_to_DCF["FCF_by_component"] = input_to_DCF["IncomeAfterTaxes"] + input_["TotalDepreciationAndAmortization-CashFlow"] + \
                                       input_to_DCF["ChangeInAccountsReceivable"] + input_to_DCF["ChangeInAccountsPayable"] + \
                                       input_to_DCF["ChangeinInventory"] + input_to_DCF["NetChangeInPropertyPlantAndEquipment"]
    
    input_to_DCF["ChangeinInventory_in_perc_of_rev"] = input_to_DCF['ChangeinInventory'] / input_to_DCF["Revenue"]
    input_to_DCF["FCF_historical"] = input_to_DCF['FreeCashFlowPerShare'] * input_to_DCF['SharesOutstanding'] / 1000
    # print("FCF by component - FCF per share * No Shares: ", input_to_DCF["FCF_by_component"] - input_to_DCF["FCF_historical"])
    # Project revenue
    # !!! CHANGE MONTH !!! -> right now only SEP or DEC
    if datetime.strptime(input_to_DCF.index[0], '%Y-%m-%d').month == 9:
        proj_index = pd.date_range(date(datetime.strptime(input_to_DCF.index[-1], '%Y-%m-%d').year, datetime.strptime(input_to_DCF.index[-1], '%Y-%m-%d').month, datetime.strptime(input_to_DCF.index[-1], '%Y-%m-%d').day), \
                                   periods=no_years_, freq = 'AS-SEP')
    else:
        proj_index = pd.date_range(date(datetime.strptime(input_to_DCF.index[-1], '%Y-%m-%d').year, datetime.strptime(input_to_DCF.index[-1], '%Y-%m-%d').month, datetime.strptime(input_to_DCF.index[-1], '%Y-%m-%d').day), \
                                   periods=no_years_, freq = 'AS-DEC')
    DCF_proj = input_to_DCF.append(pd.DataFrame(index=proj_index))
    # Start with average revenue growth in the last n years
    _avg_rev_growth = np.average(input_to_DCF["RevenueGrowth"][-no_years_rev_gwth_:])
    DCF_proj["Revenue"][proj_index] =  [input_to_DCF["Revenue"][-1] * (1 + _avg_rev_growth) ** (x + 1) for x in range(no_years_)]
    # Calculate average of ratios from the last N years
    _avg_inc_ratio_ = np.average(input_to_DCF["IncomeAfterTaxes_in_perc_of_rev"][-no_years_ratios_:])
    _avg_dep_ratio_ = np.average(input_to_DCF["TotalDepreciationAndAmortization-CashFlow_in_perc_of_rev"][-no_years_ratios_:])
    _avg_acc_rec_ratio_ = np.average(input_to_DCF["ChangeInAccountsReceivable_in_perc_of_rev"][-no_years_ratios_:])
    _avg_acc_pay_ratio_ = np.average(input_to_DCF["ChangeInAccountsPayable_in_perc_of_rev"][-no_years_ratios_:])
    _avg_inv_ratio_ = np.average(input_to_DCF["ChangeinInventory_in_perc_of_rev"][-no_years_ratios_:])
    _avg_capex_ratio_ = np.average(input_to_DCF["NetChangeInPropertyPlantAndEquipment_in_perc_of_rev"][-no_years_ratios_:])
    # Calculate projections per item
    DCF_proj["IncomeAfterTaxes"][proj_index] =  DCF_proj["Revenue"][proj_index] * _avg_inc_ratio_
    DCF_proj["TotalDepreciationAndAmortization-CashFlow"][proj_index] =  DCF_proj["Revenue"][proj_index] * _avg_dep_ratio_
    DCF_proj["ChangeInAccountsReceivable"][proj_index] =  DCF_proj["Revenue"][proj_index] * _avg_acc_rec_ratio_
    DCF_proj["ChangeInAccountsPayable"][proj_index] =  DCF_proj["Revenue"][proj_index] * _avg_acc_pay_ratio_
    DCF_proj["ChangeinInventory"][proj_index] =  DCF_proj["Revenue"][proj_index] * _avg_inv_ratio_
    DCF_proj["NetChangeInPropertyPlantAndEquipment"][proj_index] =  DCF_proj["Revenue"][proj_index] * _avg_capex_ratio_
    # Combine into FCF projection
    DCF_proj["FCF_by_component"][proj_index] = DCF_proj["IncomeAfterTaxes"][proj_index] + \
                                               DCF_proj["TotalDepreciationAndAmortization-CashFlow"][proj_index] + \
                                               DCF_proj["ChangeInAccountsReceivable"][proj_index] + \
                                               DCF_proj["ChangeInAccountsPayable"][proj_index] + \
                                               DCF_proj["ChangeinInventory"][proj_index] + \
                                               DCF_proj["NetChangeInPropertyPlantAndEquipment"][proj_index]
    # Discount based on different IRRs
    for r in irr_:
        # Calculate sum of PV of future FCF
        PV_FCF = sum([DCF_proj["FCF_by_component"][proj_index][x] * (1 + r) ** (-(x + 1)) for x in range(no_years_)])
        # Terminal Value
        TV = DCF_proj["FCF_by_component"][-1] * (1 + lng_term_gwth_) / (r - lng_term_gwth_)
        PV_TV = TV / (1 + r) ** (no_years_)
        # Intrinsic Value = Enterprise Value  - Net Debt
        EV = PV_TV + DCF_proj["FCF_by_component"][-1]
        IV = EV - (input_to_DCF["TotalLongTermLiabilities"][-1] - input_to_DCF["CashOnHand"][-1])
        # Share price
        share_price = IV / input_to_DCF["SharesOutstanding"][-1]
        # After margin of safety
        share_price_aft_mos = share_price * (1 - mos_)
        # Results
        print("***************************************")
        print("Share price of ", i, ":", share_price)
        print("After margin of safety equal to", mos_, ":", share_price_aft_mos)
        print("Assmued IRR:", r)
        print("Assmued Revenue growth from the last ", no_years_rev_gwth_, "years:", _avg_rev_growth)
        print("***************************************")
    
    
    
    
    
