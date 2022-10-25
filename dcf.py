"""
DCF calculator:
    - Take revenues, net income, ebitda from xls
    - Amortization, Accounts Payable / Receivable, CAPEX, Inventories
    - Assume IRR (later scrap WACC)
    - Calculate FCF projection based on assumptions (maybe first averages, later introduce more options)
    - Assume long-term growth
    - Calculate PV of future FCF
    - Deduct Debt
    - Divide by number of shares to obtain fair value
    - Account for margin of safety

STOCK Screener:
 Add functionality to filter database based on
 - Last n years revenue growth
 - Last n years income growth
 - Last n years min RoE/RoA
 - Debt-to-Equity
 - Last n years Shares Outstanding change
 - Current Ratio in the LP and last n years (dynamics)
 - Last n year FCF growth
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
import yfinance as yf
import psycopg2 as pg
### FUNCTIONS ######################################################################
# TBD

### INPUT ##########################################################################
#input tickers creating a list with all input data
path_ = ".../STOCKUS"
os.chdir(path_)
from sp500_tickers import sp500_tickers, sp500_yf_tickers
tickers = sp500_tickers # input('Tickers (separated by ",": ')
z = sp500_tickers
#list(map(str,tickers.split(',')))
# Run table
# Including all relevant parameters per scenario specified
# Run 1 - Baseline, IRR = 10%
# Run 2 - IRR = 7.5%
# Run 3 - IRR = 12.5%
# Run 4 - No years proj = 5 years
# Run 5 - No years ratios, rev growth = 5 years
# Run 6 - Income ratio 50%
# Run 7 - revenue growth 50%
# Run 8 - Double CAPEX
run_table = pd.DataFrame(columns = ['RUN_1', 'RUN_2', 'RUN_3', 'RUN_4',
                                    'RUN_5', 'RUN_6', 'RUN_7', 'RUN_8'], 
                         index = ['IRR', 'no_years_proj_', 'no_years_ratios_', '_avg_inc_ratio_shock_',
                                    'no_years_rev_gwth_', '_rev_gwth_shock_', '_avg_capex_ratio_shock_',
                                    'lng_term_gwth_', 'mos_'])
# Parameters per run
run_table.loc["IRR"] =                     [0.1, 0.075, 0.125, 0.1, 0.1, 0.1, 0.1, 0.1]
run_table.loc["no_years_proj_"] =          [10, 10, 10, 5, 10, 10, 10, 10]
run_table.loc["no_years_ratios_"] =        [10, 10, 10, 10, 5, 10, 10, 10]
run_table.loc["_avg_inc_ratio_shock_"] =   [1, 1, 1, 1, 1, 0.5, 1, 1]
run_table.loc["no_years_rev_gwth_"] =      [10, 10, 10, 10, 5, 10, 10, 10]
run_table.loc["_rev_gwth_shock_"] =        [1, 1, 1, 1, 1, 1, 0.5, 1]
run_table.loc["_avg_capex_ratio_shock_"] = [1, 1, 1, 1, 1, 1, 1, 2]
run_table.loc["lng_term_gwth_"] =          [0.02, 0.02, 0.02, 0.02, 0.02, 0.02, 0.02, 0.02]
run_table.loc["mos_"] =                    [0.15, 0.15, 0.15, 0.15, 0.15, 0.15, 0.15, 0.15]
# Database settings
do_from_sql = True
database_name_ = "sp500"
table_name_ = "sp500_v2"
password_ = "..."

# Stock screener params
# Flags switching on/off the params
do_min_avg_rev_gwth_ = True
do_min_avg_inc_gwth_ = True
do_min_roe_ = True
do_min_roa_ = True
do_max_de_ = True
do_max_chg_shs_out_ = True
do_min_crr_rt = True
do_min_avg_fcf_gwth = True
# - Last n years revenue growth
_min_avg_rev_gwth_ = 0.05
_min_avg_rev_gwth_n_yrs = 10
# - Last n years income growth
_min_avg_inc_gwth_ = 0.05
_min_avg_inc_gwth_n_yrs = 10
# - min RoE/RoA
_min_roe_ = 0.1
_min_roa_ = 0.03
# - max Debt-to-Equity
_max_de_ = 1.0
# - Last n years Shares Outstanding change
_max_chg_shs_out_ = 0.0
_max_chg_shs_out_last_n_years = 10
# - Current Ratio in the LP
_min_crr_rt = 1.0
# - Last n year FCF growth
_min_avg_fcf_gwth = 0.05
_min_avg_fcf_gwth_n_yrs = 10
# - Comparison of current stock to the estimates
############## VALUATION ######################################################

## Import share prices
out_ticker = pd.DataFrame(columns = ["Ticker", "Stock Price"])

k = 0
print("***************************************")
print("Start downloading latest stock prices")
for i in sp500_yf_tickers:
    print(i)
    #define the ticker symbol
    tickerSymbol = i
    #get data on this ticker
    tickerData = yf.Ticker(tickerSymbol)
    #get the historical prices for this ticker
    tickerDf = tickerData.history(period='1d')
    #see your data
    out_ticker = out_ticker.append({"Ticker": str(i), "Stock Price": tickerDf['Close'][0]}, ignore_index = True)
    k += 1
out_ticker.to_csv(os.path.join("stock_prices.csv"))
print("Finished downloading latest stock prices")
print("***************************************")
# Define output storing all the results
out = pd.DataFrame(columns = ['ticker', 'revenue growth', 'margin of safety'] + run_table.columns.tolist() + 
                              ['P/E = 10', 'P/E = 15', 'P/E = 20',
                              'P/B = 1', 'P/B = 1.5', 'P/B = 2',
                              'P/S = 1', 'P/S = 3', 'P/S = 5',
                              'NCAV', 'Curr Assets min Tot Liab per share', 'Stock price'])
j = 0
print("***************************************")
print("Start estimating fair price of shares")
if do_from_sql:
    conn  = pg.connect("dbname='" + database_name_ + "' user='postgres' host='localhost' port='5432' password='" + password_ + "'")
    cur = conn.cursor()
    # Query to get column names
    cur.execute("""SELECT * FROM sp500_v2 LIMIT 0""")
    colnames = [desc[0] for desc in cur.description]
    # Query to get values
    cur.execute("""SELECT * FROM sp500_v2""")
    query_results = pd.DataFrame(cur.fetchall())
    query_results.columns = colnames
    # Close the cursor and connection to so the server can allocate
    # bandwidth to other requests
    cur.close()
    conn.close()
    
for i in z:
    print(i)
    ### IMPORT DATA ###
    if do_from_sql == True: 
        input_ = query_results
        # filter the stock
        input_ = input_.loc[input_["date_ticker"].str.contains(i)]
        # create index
        input_.index = input_["date"]
    # Source data
    if do_from_sql == False:    
        input_ = pd.read_excel(path_ + "/" + i + "/" + i + ".xlsx", index_col = 0)
    # Remove duplicate rows
    input_ = input_[~input_.index.duplicated(keep = 'last')]
    ### BUILD CASH FLOWS ###
    # Change all column names to lower case
    input_.columns = [x.lower() for x in input_.columns]
    input_.columns = [x.replace(".", "").replace("-", "") for x in input_.columns]
    # Select variables needed in the DCF
    input_to_DCF = input_[["revenue", "netincome", "ebitda", "ebit", "incomeaftertaxes", "totaldepreciationandamortizationcashflow", \
                           "cashonhand","changeininventories", "changeinaccountsreceivable", "changeinaccountspayable", "netchangeinpropertyplantandequipment", "inventory", \
                           "freecashflowpershare", "sharesoutstanding",\
                           "totallongtermliabilities"]]
    # Convert to floats
    input_to_DCF["revenue"] = input_to_DCF["revenue"].astype(float)
    input_to_DCF["freecashflowpershare"] = input_to_DCF["freecashflowpershare"].astype(float)
    input_to_DCF["sharesoutstanding"] = input_to_DCF["sharesoutstanding"].astype(float)
    # Calculate YoY percentage growth
    input_to_DCF["revenuegrowth"] = input_to_DCF["revenue"].pct_change(periods = 1)
    # Calculate as % of revenue:
    # - ebitda
    # - Depreciation
    # - Inventories
    # - Accounts Payable / Receivable
    # - CAPEX
    vars_as_perc = ["ebitda", "ebit", "incomeaftertaxes", 
                    "totaldepreciationandamortizationcashflow", "changeininventories", "changeinaccountsreceivable", 
                    "changeinaccountspayable", "inventory", "inventory", "netchangeinpropertyplantandequipment"]
    for n in vars_as_perc:
        input_to_DCF[n] = input_to_DCF[n].astype(float)
        input_to_DCF[n + "_in_perc_of_rev"] = input_to_DCF[n] / input_to_DCF["revenue"]
    # Calculate historical FCF from components and compare to FCF per share * No shares outstanding
    input_to_DCF["fcf_by_component"] = input_to_DCF["incomeaftertaxes"] + \
                                       input_to_DCF["totaldepreciationandamortizationcashflow"] + \
                                       input_to_DCF["changeinaccountsreceivable"] + \
                                       input_to_DCF["changeinaccountspayable"] + \
                                       input_to_DCF["changeininventories"] + \
                                       input_to_DCF["netchangeinpropertyplantandequipment"]
   
    input_to_DCF["FCF_historical"] = input_to_DCF['freecashflowpershare'] * input_to_DCF['sharesoutstanding'] / 1000

    for j in range(len(run_table.columns)):
        # Define parameters for a specific run
        irr_                    = run_table["RUN_" + str(j + 1)]["IRR"]
        no_years_               = run_table["RUN_" + str(j + 1)]["no_years_proj_"]
        no_years_ratios_        = run_table["RUN_" + str(j + 1)]["no_years_ratios_"]
        _avg_inc_ratio_shock_   = run_table["RUN_" + str(j + 1)]['_avg_inc_ratio_shock_']
        no_years_rev_gwth_      = run_table["RUN_" + str(j + 1)]["no_years_rev_gwth_"]
        _rev_gwth_shock_        = run_table["RUN_" + str(j + 1)]["_rev_gwth_shock_"]
        _avg_capex_ratio_shock_ = run_table["RUN_" + str(j + 1)]["_avg_capex_ratio_shock_"]
        lng_term_gwth_          = run_table["RUN_" + str(j + 1)]["lng_term_gwth_"]
        mos_                    = run_table["RUN_" + str(j + 1)]["mos_"]
        # Project revenue
        # Set the month of projection based on the historicals
        if datetime.strptime(str(input_to_DCF.index[0]), '%Y-%m-%d').month == 3:
            proj_index = pd.date_range(date(datetime.strptime(str(input_to_DCF.index[-1]), '%Y-%m-%d').year, datetime.strptime(str(input_to_DCF.index[-1]), '%Y-%m-%d').month, datetime.strptime(str(input_to_DCF.index[-1]), '%Y-%m-%d').day), \
                                       periods=no_years_, freq = 'AS-MAR')
        elif datetime.strptime(str(input_to_DCF.index[0]), '%Y-%m-%d').month == 6:
            proj_index = pd.date_range(date(datetime.strptime(str(input_to_DCF.index[-1]), '%Y-%m-%d').year, datetime.strptime(str(input_to_DCF.index[-1]), '%Y-%m-%d').month, datetime.strptime(str(input_to_DCF.index[-1]), '%Y-%m-%d').day), \
                                       periods=no_years_, freq = 'AS-JUN')
        elif datetime.strptime(str(input_to_DCF.index[0]), '%Y-%m-%d').month == 9:
            proj_index = pd.date_range(date(datetime.strptime(str(input_to_DCF.index[-1]), '%Y-%m-%d').year, datetime.strptime(str(input_to_DCF.index[-1]), '%Y-%m-%d').month, datetime.strptime(str(input_to_DCF.index[-1]), '%Y-%m-%d').day), \
                                       periods=no_years_, freq = 'AS-SEP')
        else:
            proj_index = pd.date_range(date(datetime.strptime(str(input_to_DCF.index[-1]), '%Y-%m-%d').year, datetime.strptime(str(input_to_DCF.index[-1]), '%Y-%m-%d').month, datetime.strptime(str(input_to_DCF.index[-1]), '%Y-%m-%d').day), \
                                       periods=no_years_, freq = 'AS-DEC')
        DCF_proj = input_to_DCF.append(pd.DataFrame(index=proj_index))
        # Start with average revenue growth in the last n years
        _avg_rev_growth = _rev_gwth_shock_ * np.average(input_to_DCF["revenuegrowth"][-no_years_rev_gwth_:])
        DCF_proj["revenue"][proj_index] =  [input_to_DCF["revenue"][-1] * (1 + _avg_rev_growth) ** (x + 1) for x in range(no_years_)]
        # Calculate average of ratios from the last N years
        _avg_inc_ratio_     = _avg_inc_ratio_shock_ * np.average(input_to_DCF["incomeaftertaxes_in_perc_of_rev"][-no_years_ratios_:])
        _avg_dep_ratio_     = np.average(input_to_DCF["totaldepreciationandamortizationcashflow_in_perc_of_rev"][-no_years_ratios_:])
        _avg_acc_rec_ratio_ = np.average(input_to_DCF["changeinaccountsreceivable_in_perc_of_rev"][-no_years_ratios_:])
        _avg_acc_pay_ratio_ = np.average(input_to_DCF["changeinaccountspayable_in_perc_of_rev"][-no_years_ratios_:])
        _avg_inv_ratio_     = np.average(input_to_DCF["changeininventories_in_perc_of_rev"][-no_years_ratios_:])
        _avg_capex_ratio_   = _avg_capex_ratio_shock_ * np.average(input_to_DCF["netchangeinpropertyplantandequipment_in_perc_of_rev"][-no_years_ratios_:])
        # Calculate projections per item
        DCF_proj["incomeaftertaxes"][proj_index]                          =  DCF_proj["revenue"][proj_index] * _avg_inc_ratio_
        DCF_proj["totaldepreciationandamortizationcashflow"][proj_index]  =  DCF_proj["revenue"][proj_index] * _avg_dep_ratio_
        DCF_proj["changeinaccountsreceivable"][proj_index]                =  DCF_proj["revenue"][proj_index] * _avg_acc_rec_ratio_
        DCF_proj["changeinaccountspayable"][proj_index]                   =  DCF_proj["revenue"][proj_index] * _avg_acc_pay_ratio_
        DCF_proj["changeininventories"][proj_index]                       =  DCF_proj["revenue"][proj_index] * _avg_inv_ratio_
        DCF_proj["netchangeinpropertyplantandequipment"][proj_index]      =  DCF_proj["revenue"][proj_index] * _avg_capex_ratio_
        # Combine into FCF projection
        DCF_proj["fcf_by_component"][proj_index] = DCF_proj["incomeaftertaxes"][proj_index] + \
                                                   DCF_proj["totaldepreciationandamortizationcashflow"][proj_index] + \
                                                   DCF_proj["changeinaccountsreceivable"][proj_index] + \
                                                   DCF_proj["changeinaccountspayable"][proj_index] + \
                                                   DCF_proj["changeininventories"][proj_index] + \
                                                   DCF_proj["netchangeinpropertyplantandequipment"][proj_index]
        # Discount based on different IRRs
        if j == 0:
            out = out.append({'ticker': str(i),
                              'revenue growth' : _avg_rev_growth,
                              'margin of safety': mos_}, ignore_index = True)
        # Calculate sum of PV of future FCF
        PV_FCF = sum([DCF_proj["fcf_by_component"][proj_index][x] * (1 + irr_) ** (-(x + 1)) for x in range(no_years_)])
        # Terminal Value
        TV = DCF_proj["fcf_by_component"][-1] * (1 + lng_term_gwth_) / (irr_ - lng_term_gwth_)
        PV_TV = TV / (1 + irr_) ** (no_years_)
        # Intrinsic Value = Enterprise Value  - Net Debt
        EV = PV_TV + DCF_proj["fcf_by_component"][-1]
        IV = EV - (input_to_DCF["totallongtermliabilities"].astype(float)[-1] - input_to_DCF["cashonhand"].astype(float)[-1])
        # Share price
        share_price = IV / input_to_DCF["sharesoutstanding"][-1]
        # After margin of safety
        share_price_aft_mos = share_price * (1 - mos_)
        # Results
        print("***************************************")
        print("Share price of ", i, ":", share_price)
        print("After margin of safety equal to", mos_, ":", share_price_aft_mos)
        print("Assmued IRR:", irr_)
        print("Assmued revenue growth from the last ", no_years_rev_gwth_, "years:", _avg_rev_growth)
        print("***************************************")

        #out.at[j, str('RUN_') + str(j + 1)] = share_price
        print(i)
        out.at[z.index(i), str('RUN_') + str(j + 1)] = share_price_aft_mos
    # Add new valuation options:
    input_["epsearningspershare"]      = input_["epsearningspershare"].astype(float)
    input_["bookvaluepershare"]        =  input_["bookvaluepershare"].astype(float)
    input_["revenue"]                  = input_["revenue"].astype(float)
    input_["sharesoutstanding"]        = input_["sharesoutstanding"].astype(float)
    input_["totalcurrentassets"]       = input_["totalcurrentassets"].astype(float)
    input_["totalcurrentliabilities"]  = input_["totalcurrentliabilities"].astype(float)
    input_["totalliabilities"]         = input_["totalliabilities"].astype(float)
    # Last year earnings * (P/E = 10)
    val_pe_10 = input_["epsearningspershare"][-1] * 10
    # Last year earnings * (P/E = 10)
    val_pe_15 = input_["epsearningspershare"][-1] * 15
    # Last year earnings * (P/E = 10)
    val_pe_20 = input_["epsearningspershare"][-1] * 20
    # Book value * (P/B = 1)
    val_pb_1 = input_["bookvaluepershare"][-1] * 1
    # Book value * (P/B = 1.5)
    val_pb_1_5 = input_["bookvaluepershare"][-1] * 1.5
    # Book value * (P/B = 2)
    val_pb_2 = input_["bookvaluepershare"][-1] * 2
    # revenue * (P/S = 1)
    val_ps_1 = input_["revenue"][-1] / input_["sharesoutstanding"][-1]
    # revenue * (P/S = 3)
    val_ps_3 = input_["revenue"][-1] / input_["sharesoutstanding"][-1] * 3
    # revenue * (P/S = 5)
    val_ps_5 = input_["revenue"][-1] / input_["sharesoutstanding"][-1] * 5
    # NCAV / No Shares
    val_ncav = (input_["totalcurrentassets"][-1] - input_["totalcurrentliabilities"][-1]) / input_["sharesoutstanding"][-1]
    # (Curr Assets - Tot Liab) / No Shares
    val_ca_min_totliab = (input_["totalcurrentassets"][-1] - input_["totalliabilities"][-1]) / input_["sharesoutstanding"][-1]
   
    out.at[z.index(i),'P/E = 10']  = float(val_pe_10)
    out.at[z.index(i),'P/E = 15']  = float(val_pe_15)
    out.at[z.index(i),'P/E = 20']  = float(val_pe_20)
    out.at[z.index(i),'P/B = 1']   = float(val_pb_1)
    out.at[z.index(i),'P/B = 1.5'] = float(val_pb_1_5)
    out.at[z.index(i),'P/B = 2']   = float(val_pb_2)
    out.at[z.index(i),'P/S = 1']   = float(val_ps_1)
    out.at[z.index(i),'P/S = 3']   = float(val_ps_3)
    out.at[z.index(i),'P/S = 5']   = float(val_ps_5)
    out.at[z.index(i),'NCAV']      = float(val_ncav)
    out.at[z.index(i),'Curr Assets min Tot Liab per share'] = float(val_ca_min_totliab)
    # Add stock price
    out.at[z.index(i),'Stock price'] = out_ticker.at[z.index(i),'Stock Price']

    # Plot the fair prices along with the stock price as separate line
    plt.rcdefaults()
    fig, ax = plt.subplots()
    
    y_pos = np.arange(len(out.columns[3:-1]))
    ax.barh(y_pos, out[out.columns[3:-1].tolist()].iloc[z.index(i)], align='center')
    ax.set_yticks(y_pos, )
    ax.set_yticklabels(out.columns[3:-1].tolist())
    ax.invert_yaxis()  # labels read top-to-bottom
    ax.set_xlabel('Fair value after margin of safety')
    ax.set_title('How much the stock should be worth?')
    # Plot vertical line equal to stock price
    plt.axvline(x=out.at[z.index(i),'Stock price'], color = "r")
    # plt.show()
    # Save the plot
    plt.savefig(os.path.join(path_ + "/" + str(i) + "/" + str(i) + "-valuations.png"))
    
print("Finish estimating fair price of shares")
print("***************************************")

# write to csv
out.to_csv(os.path.join(path_ + "/DCF_out.csv"))


################# STOCK SCREENER ######################################

# Create a ticker column
if do_from_sql:
    query_results['ticker'] = [x[:x.find('-')] for x in query_results['date_ticker']]
    # Get unique tickers
    uniq_tck = np.unique(query_results["ticker"])
    # Create DataFrame with metrics
    uniq_mtrcks = pd.DataFrame(columns = ['Avg Rev Gwth', 'Avg Income Gwth', 'RoE_RoA',
                                        'Debt_Equity', 'Shares_Outstanding_chg', 'Curr_Ratio', 'FCF Gwth'], 
                             index = uniq_tck)
    # - Last n years revenue growth
    if do_min_avg_rev_gwth_ == True:
        uniq_mtrcks['Avg Rev Gwth'] = [float(np.average(query_results[query_results['ticker'] == uniq_tck[x]]["revenue"].astype(float).pct_change(periods = 1)[-_min_avg_rev_gwth_n_yrs:])) > _min_avg_rev_gwth_ \
                                        if len(query_results[query_results['ticker'] == uniq_tck[x]]) >= _min_avg_rev_gwth_n_yrs \
                                           and float(np.array(query_results[query_results['ticker'] == uniq_tck[x]]["revenue"])[-_min_avg_rev_gwth_n_yrs]) > 0 \
                                        else "-"
                                        for x in range(len(uniq_tck))]
        # Filter out
        uniq_mtrcks = uniq_mtrcks[uniq_mtrcks['Avg Rev Gwth'] == True]
    # - Last n years income growth
    if do_min_avg_inc_gwth_ == True:
        uniq_mtrcks['Avg Income Gwth'] = [float(np.average(query_results[query_results['ticker'] == uniq_mtrcks.index[x]]["netincome"].astype(float).pct_change(periods = 1)[-_min_avg_inc_gwth_n_yrs:])) > _min_avg_inc_gwth_ \
                                            if len(query_results[query_results['ticker'] == uniq_mtrcks.index[x]]) >= _min_avg_inc_gwth_n_yrs \
                                             and float(np.array(query_results[query_results['ticker'] == uniq_mtrcks.index[x]]["netincome"])[-1]) > 0
                                            else "-"
                                            for x in range(len(uniq_mtrcks))]
        # Filter out
        uniq_mtrcks = uniq_mtrcks[uniq_mtrcks['Avg Income Gwth'] == True]        
    # - Min RoE/RoA
    if do_min_roe_ == True:
        uniq_mtrcks['RoE_RoA'] = [(float(np.array(query_results[query_results['ticker'] == uniq_mtrcks.index[x]]["roereturnonequity"])[-1]) > _min_roe_ * 100 \
                                            and float(np.array(query_results[query_results['ticker'] == uniq_mtrcks.index[x]]["roareturnonassets"])[-1]) > _min_roa_ * 100)
                                            for x in range(len(uniq_mtrcks))]
        # Filter out
        uniq_mtrcks = uniq_mtrcks[uniq_mtrcks['RoE_RoA'] == True] 
    # - max Debt-to-Equity
    if do_max_de_ == True:
        uniq_mtrcks['Debt_Equity'] = [(float(np.array(query_results[query_results['ticker'] == uniq_mtrcks.index[x]]['debtequityratio'])[-1]) < _max_de_)
                                            for x in range(len(uniq_mtrcks)) \
                                            if float(np.array(query_results[query_results['ticker'] == uniq_mtrcks.index[x]]["shareholderequity"])[-1]) > 0]
        # Filter out
        uniq_mtrcks = uniq_mtrcks[uniq_mtrcks['Debt_Equity'] == True] 
    # - Last n years Shares Outstanding change
    if do_max_chg_shs_out_ == True:
        uniq_mtrcks['Shares_Outstanding_chg'] = [(float(np.array(query_results[query_results['ticker'] == uniq_mtrcks.index[x]]['sharesoutstanding'])[-1]) - \
                                                  float(np.array(query_results[query_results['ticker'] == uniq_mtrcks.index[x]]["sharesoutstanding"])[-_max_chg_shs_out_last_n_years]) < _max_chg_shs_out_)
                                                  for x in range(len(uniq_mtrcks))]
        # Filter out
        uniq_mtrcks = uniq_mtrcks[uniq_mtrcks['Shares_Outstanding_chg'] == True] 
    # - Current Ratio in the LP
    if do_min_crr_rt == True:
        uniq_mtrcks['Curr_Ratio'] = [(float(np.array(query_results[query_results['ticker'] == uniq_mtrcks.index[x]]['currentratio'])[-1]) > _min_crr_rt)
                                                  for x in range(len(uniq_mtrcks))]
        # Filter out
        uniq_mtrcks = uniq_mtrcks[uniq_mtrcks['Curr_Ratio'] == True] 
        
    # - Last n year FCF growth
    if do_min_avg_fcf_gwth == True:
        # Calc FCF by component
        query_results["fcf_by_component"] = query_results["incomeaftertaxes"].astype(float) + \
                                                   query_results["totaldepreciationandamortizationcashflow"].astype(float) + \
                                                   query_results["changeinaccountsreceivable"].astype(float) + \
                                                   query_results["changeinaccountspayable"] .astype(float)+ \
                                                   query_results["changeininventories"].astype(float) + \
                                                   query_results["netchangeinpropertyplantandequipment"].astype(float)
        query_results["fcf_by_component_per_share"] = [query_results["fcf_by_component"][x].astype(float) / float(query_results["sharesoutstanding"][x]) for x in range(len(query_results))]
                                                   
                                                   
        uniq_mtrcks['FCF Gwth'] = [float(np.average(query_results[query_results['ticker'] == uniq_mtrcks.index[x]]["fcf_by_component_per_share"].astype(float).pct_change(periods = 1)[-_min_avg_fcf_gwth_n_yrs:])) > _min_avg_fcf_gwth \
                                            if len(query_results[query_results['ticker'] == uniq_mtrcks.index[x]]) >= _min_avg_fcf_gwth_n_yrs \
                                             and float(np.array(query_results[query_results['ticker'] == uniq_mtrcks.index[x]]["fcf_by_component_per_share"])[-1]) > 0
                                            else "-"
                                            for x in range(len(uniq_mtrcks))]
        # Filter out
        uniq_mtrcks = uniq_mtrcks[uniq_mtrcks['FCF Gwth'] == True]   
        
        # - Comparison of current stock to the estimates
        
        # Filter stocks fulfilling both fundamental and valuation criteria
        val_columns = run_table.columns.tolist() + \
                                     ['P/E = 10', 'P/E = 15', 'P/E = 20',
                                      'P/B = 1', 'P/B = 1.5', 'P/B = 2',
                                      'P/S = 1', 'P/S = 3', 'P/S = 5',
                                      'NCAV']
        print("Filter stocks fulfilling both fundamental and valuation criteria: ")
        for c in val_columns:
            # Merge to the filtered fundamentals to check wchi stock fulfills all criteria
            stocks_underval = out[out[c] > out["Stock price"]]['ticker']
            print("Criterium: ", str(c))
            print(list(set(uniq_mtrcks.index).intersection(stocks_underval)))

# (For later) Customize method of estimation to company type
# E.g. Bank - rather P/B
# Dividend stocks - maybe some Discounted dividend model
# Growth stocks - different assumptiosn on growth
# DCF - well established companies
# etc

 ######################################################################


