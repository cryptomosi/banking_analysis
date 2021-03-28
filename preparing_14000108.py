# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# import library
import pandas as pd
import numpy as np
import pickle
from dateutil.relativedelta import relativedelta

from corr.func_corr import associations


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# import data
position_data = pd.read_excel('Study Case - Data Scientist Role.xlsx',sheet_name='Position Data')
rates_data = pd.read_excel('Study Case - Data Scientist Role.xlsx',sheet_name='Rates Data')
activity_data = pd.read_excel('Study Case - Data Scientist Role.xlsx',sheet_name='Activity Data')


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# check data
data = pd.merge(activity_data, position_data, left_on=activity_data['No'], right_on=position_data['No.'], how='inner')
check_not_on_activity = len(activity_data)-len(data)
check_not_on_position = len(position_data)-len(data)
check_IssueDate = sum(data['Issue Date_x']!=data['Issue Date_y'])
check_InterestDate = sum(data['Interest Date_x']!=data['Interest Date_y'])
check_MaturityDate = sum(data['Maturity Date_x']!=data['Maturity Date_y'])
check_Rate = sum(data['Rate_x']!=data['Rate_y'])
check_Counterparty = sum(data['Counterparty_x']!=data['Counterparty_y'])
check_PrincipalAmount = sum(data['Principal Amount_x']!=data['Principal Amount_y'])
del data


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
data = pd.merge(position_data, activity_data[['TYPE', 'Principal Amount', 'No']], left_on=position_data['No.'], right_on=activity_data['No'], how='inner')
data = data.drop(['key_0', 'No'], axis=1)
data= data.rename(columns={'Principal Amount_x': 'Principal Amount_position',
						   'Principal Amount_y': 'Principal Amount_activity'})

data['Term Type Days'] = data['Maturity Date'] - data['Issue Date']
data['Investment Tenure Days'] = data['Position Date'] - data['Issue Date']
data['Term Type Year'] = 0
data['Term Type Month'] = 0
data['Investment Tenure Year'] = 0
data['Investment Tenure Month'] = 0
for i in range(len(data)):
	data['Term Type Year'][i] = relativedelta(data['Maturity Date'][i],data['Issue Date'][i]).years
	data['Term Type Month'][i] = (relativedelta(data['Maturity Date'][i],data['Issue Date'][i]).years*12)+(relativedelta(data['Maturity Date'][i],data['Issue Date'][i]).months)
	data['Investment Tenure Year'][i] = relativedelta(data['Position Date'][i],data['Issue Date'][i]).years
	data['Investment Tenure Month'][i] = (relativedelta(data['Position Date'][i],data['Issue Date'][i]).years*12)+(relativedelta(data['Position Date'][i],data['Issue Date'][i]).months)

data['Principal Amount_position_modified'] = data['Principal Amount_activity']+(data['Principal Amount_activity']*data['Rate'])*data['Investment Tenure Month']/12

temp_rate = pd.merge(data[['Issue Date']], rates_data, left_on=data['Issue Date'], right_on=rates_data['Date'], how='left')

data['Market Rate'] = 0.0
for i in range(len(data)):
	if data['Term Type Year'][i]==0:
		data['Market Rate'][i] = temp_rate['1M Rate'][i]*data['Term Type Month'][i]/12
	else:
		data['Market Rate'][i] = temp_rate['%sYr Rate'%data['Term Type Year'][i]][i]

data.to_csv('result/data.csv', sep=';', index=False)
pickle.dump( data, open("result/data.p", "wb" ) )


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
corr_data= data.copy()
# corr_data['Position Date'] = corr_data['Position Date'].dt.strftime('%Y-%m-%d')
corr_data['Issue Date'] = corr_data['Issue Date'].dt.strftime('%Y-%m-%d')
corr_data['Interest Date'] = corr_data['Interest Date'].dt.strftime('%Y-%m-%d')
corr_data['Maturity Date'] = corr_data['Maturity Date'].dt.strftime('%Y-%m-%d')
corr_data = corr_data.drop(['Position Date', 'No.', 'Term Type Days', 'Investment Tenure Days'], axis=1)

param_corr= associations(corr_data, 'result/', theil_u=True, plot=False, nan_strategy='drop_samples')
param_corr= param_corr['corr']
# Correlation= param_corr.copy()
param_corr= round(param_corr*100)/100
# Correlation= Correlation.reset_index()
param_corr.reset_index().to_csv('result/correlation.csv', sep=';', index=False)


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~



# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~





