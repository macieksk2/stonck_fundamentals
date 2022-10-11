"""
1. Scrap macrotrends.com (DONE)
2. Store historicals relevant for fundamental analysis: (DONE)
    - Revenue
    - Net Income
    - Expenses
    - Capex
    - Depr/Amort
    - FCF
    - P/E, P/B, P/S, 
    - Casf Flow Statement
    - Debt, D/E
    - No shares outstanding
    - Dividends
    - RoE, RoA
3. Create a screener based on downloaded database
4. Visualize historicals (DONE, to be improved)
5. DCF calculator (DONE, to be improved)
6. Scrap sec.gov to get into more details in reports
"""
### 1. Scrap macrotrends
# retrieve the HTML
# Scraping all financial data available from MacroTrends.net
# packages
import selenium
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
import time
import re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import requests
import pandas_datareader.data as web
from pandas.api.types import CategoricalDtype
import os
from webdriver_manager.chrome import ChromeDriverManager

### FUNCTIONS ###
def retrieve_data(driver, url, item = "financial-statements"):
    """
    Retrieve data (numbers, dates) for each item from macrotrends:
        - financial-statements
        - balance-sheet
        - cash-flow-statement
        - financial-ratios
    """
    if item != "financial-statements":
        surl = url + item
        driver.get(surl)
    driver.set_window_size(2000, 2000)
    if item == "financial-statements":
        time.sleep(10)
    sa = driver.find_element(By.CSS_SELECTOR, "#contenttablejqxgrid").text
    if item == "financial-statements":
        da = driver.find_element(By.CSS_SELECTOR, "#columntablejqxgrid").text
    arrow = driver.find_element(By.CSS_SELECTOR, ".jqx-icon-arrow-right")
    webdriver.ActionChains(driver).click_and_hold(arrow).perform()
    time.sleep(4)
    sb = driver.find_element(By.CSS_SELECTOR, "#contenttablejqxgrid").text
    if item == "financial-statements":
        db = driver.find_element(By.CSS_SELECTOR, "#columntablejqxgrid").text
        return sa, da, sb, db
    else:
        return sa, sb

def repl_sp_signs(obj):
    return obj.replace(".","").replace("$","").replace(",","").replace(" ", "")
    

def def_headers(obj):
    #define headers for data
    last_key = None
    out = {}
    for i in obj:
        if not (i.isnumeric() or i == '-' or i.startswith('-')):
            last_key = i
        elif last_key in out:
            out[last_key].append(i)
        else:
            out[last_key] = [i] 
    return out

### INPUT ###
#input tickers creating a list with all input data
url_ = 'https://www.macrotrends.net/'
tickers = input('Tickers (separated by ",": ')
z = list(map(str,tickers.split(',')))

### SCRAP ###
#getting correct urls for each ticker
for i in z:
    a=i
    print(a)
    driver = webdriver.Chrome(ChromeDriverManager().install())
    url = url_
    driver.get(url)
    box = driver.find_element(By.CSS_SELECTOR, ".js-typeahead")
    box.send_keys(a)
    time.sleep(1)
    box.send_keys(Keys.DOWN, Keys.RETURN)
    time.sleep(1)
    geturl = driver.current_url
    time.sleep(4)
    driver.quit()
    #check if the ticker is available in MacroTrends
    if "stocks" in geturl:
        # Split URL by /
        geturlsp = geturl.split("/", 10)
        # Create new URL for charts
        geturlf = url+"stocks/charts/"+geturlsp[5]+"/"+geturlsp[6]+"/"
        # Again, open the browser
        driver = webdriver.Chrome(ChromeDriverManager().install())
        #check if the data in the ticker is available
        fsurl = geturlf + "financial-statements"
        driver.get(fsurl)
        if driver.find_elements(By.CSS_SELECTOR, "div.jqx-grid-column-header:nth-child(1) > div:nth-child(1) > div:nth-child(1) > span:nth-child(1)"):
            # financial-statements
            out = retrieve_data(driver, url = geturlf, item = "financial-statements")
            fsa, da, fsb, db = out[0], out[1], out[2], out[3]
            # balance-sheet
            out = retrieve_data(driver, url = geturlf, item = "balance-sheet")
            bsa, bsb = out[0], out[1]
            # cash-flow
            out = retrieve_data(driver, url = geturlf, item = "cash-flow-statement")
            cfa, cfb = out[0], out[1]
            # financial-ratio
            out = retrieve_data(driver, url = geturlf, item = "financial-ratios")
            fra, frb = out[0], out[1]
            driver.quit()
            # Transform data
            raw_data = [da, db, fsa, fsb, bsa, bsb, cfa, cfb, fra, frb]
            output = []
            for i in range(len(raw_data)):
                # remove blanks from variables, split variables into lists
                # Do not remove dots in the financial ratios
                out = repl_sp_signs(raw_data[i]).splitlines()
                #removing title from dates dataframe (only last two items)
                if i == 0 or i == 1:
                    out = np.delete(out, (0), axis=0)
                # define headers for data and creating dataframes
                if i == 0 or i == 1:
                    out = pd.DataFrame(out)
                else:
                    out = pd.DataFrame(def_headers(out))
                #treating dataframes
                if i > 1:
                    out = out.replace("-","0").astype(float)
                #naming dates dataframe
                if i == 0 or i == 1:
                    out = out.set_axis(["Dates"], axis=1)
                #merging dataframes
                if i > 1:
                    if i % 2 == 0:
                        out = out.merge(output[0], left_index=True, right_index=True)
                    else:
                        out = out.merge(output[1], left_index=True, right_index=True)
                    #defining dates as rows headers
                    out = out.set_index("Dates")
                    
                output.append(out)
            #concatenate whole data
            fsconcatdd = pd.concat([output[2],output[3]])
            fsdados = fsconcatdd.drop_duplicates()
            bsconcatdd = pd.concat([output[4],output[5]])
            bsdados = bsconcatdd.drop_duplicates()
            cfconcatdd = pd.concat([output[6],output[7]])
            cfdados = cfconcatdd.drop_duplicates()
            frconcatdd = pd.concat([output[8],output[9]])
            frdados = frconcatdd.drop_duplicates()
            #creating final dataframe
            ca = fsdados.merge(bsdados, left_index=True, right_index=True)
            cb = ca.merge(cfdados, left_index=True, right_index=True)
            complete = cb.merge(frdados, left_index=True, right_index=True)    
            #managing plots
            fig1, f1_axes = plt.subplots(ncols=2, nrows=5, figsize=(30,20))
            fig1.suptitle (a, size=50)
            # Rev vs Income
            f1_axes[0, 0].plot(complete['Revenue'], lw=2, marker='.', markersize=10, label="Revenue")
            f1_axes[0, 0].plot(complete['GrossProfit'], lw=2, marker='.', markersize=10, label="Gross Profit")
            f1_axes[0, 0].plot(complete['NetIncome'], lw=2, marker='.', markersize=10, label="Net Income")
            f1_axes[0, 0].plot(complete['EBITDA'], lw=2, marker='.', markersize=10, label="EBITDA")
            # Cash vs Debt
            f1_axes[1, 0].plot(complete['CashOnHand'], lw=2, marker='.', markersize=10, label="Cash on Hand")
            f1_axes[1, 0].plot(complete['LongTermDebt'], lw=2, marker='.', markersize=10, label="Long Term Debt")
            # Cashflows
            f1_axes[2, 0].plot(complete['CashFlowFromOperatingActivities'], lw=2, marker='.', markersize=10, label="CF from Operating Activity")
            f1_axes[2, 0].plot(complete['FreeCashFlowPerShare'] * complete['SharesOutstanding'] / 1000, lw=2, marker='.', markersize=10, label="FCF")
            f1_axes[2, 0].plot(complete['CashFlowFromInvestingActivities'], lw=2, marker='.', markersize=10, label="CF from Investing Activities")
            f1_axes[2, 0].plot(complete['NetIncome'], lw=2, marker='.', markersize=10, label="Net Income")
            # Assets vs Equity
            f1_axes[3, 0].plot(complete['TotalAssets'], lw=2, marker='.', markersize=10, label="Total Assets")
            f1_axes[3, 0].plot(complete['ShareHolderEquity'], lw=2, marker='.', markersize=10, label="Shareholder Equity")
            # Current Ratio
            f1_axes[4, 0].plot(complete['CurrentRatio']/10000, lw=2, marker='.', markersize=10, label="Current Ratio")
            # Assets / Liab
            f1_axes[0, 1].plot(complete['TotalAssets'], lw=2, marker='.', markersize=10, label="Total Assets")
            f1_axes[0, 1].plot(complete['TotalLiabilities'], lw=2, marker='.', markersize=10, label="Total Liabilities")
            f1_axes[0, 1].plot(complete['TotalCurrentAssets'], lw=2, marker='.', markersize=10, label="Current Assets")
            f1_axes[0, 1].plot(complete['TotalCurrentLiabilities'], lw=2, marker='.', markersize=10, label="Current Liabilities")
            # EPS
            f1_axes[1, 1].plot(complete['EPS-EarningsPerShare'], lw=2, marker='.', markersize=10, label="EPS")
            # Ratios
            f1_axes[2, 1].plot(complete['ROE-ReturnOnEquity']/10000, lw=2, marker='.', markersize=10, label="ROE")
            f1_axes[2, 1].plot(complete['ROA-ReturnOnAssets']/10000, lw=2, marker='.', markersize=10, label="ROA")
            f1_axes[2, 1].plot(complete['ROI-ReturnOnInvestment']/10000, lw=2, marker='.', markersize=10, label="ROI")
            # D / E
            f1_axes[3, 1].plot(complete['Debt/EquityRatio']/10000, lw=2, marker='.', markersize=10, label="Debt/Equity Ratio")
            # Shares Outstanding
            f1_axes[4, 1].plot(complete['SharesOutstanding'], lw=2, marker='.', markersize=10, label="Shares Outstanding")
            
            f1_axes[0, 0].legend()
            f1_axes[1, 0].legend()
            f1_axes[2, 0].legend()
            f1_axes[3, 0].legend()
            f1_axes[4, 0].legend()
            f1_axes[0, 1].legend()
            f1_axes[1, 1].legend()
            f1_axes[2, 1].legend()
            f1_axes[3, 1].legend()
            f1_axes[4, 1].legend()
            #creating folder for data and images
            if not os.path.exists("STOCKUS/"+a):
                os.makedirs("STOCKUS/"+a)
            plt.savefig("STOCKUS/"+a+"/"+a+"data.png")
            complete.to_excel(os.path.join("STOCKUS/"+a, geturlsp[5]+".xlsx"),sheet_name=geturlsp[5])
            #confirmation message for ticker that exists and have data
            print("SUCCESS")
        #error message for ticker that exists but have no data
        else:
            driver.quit()
            print("EMPTY TICKER")
    #error message for ticker that doesn't exist
    else:
            print("INVALID TICKER")
#final message
print("FINISHED")
 
