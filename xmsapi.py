#!/usr/bin/python3

import simplejson as json
import requests, time, sqlite3, ast
from argparse import ArgumentParser

##sqlite für zabbix vollen pfad /usr/lib/zabbix/externalscripts/
conn = sqlite3.connect('xmsapi.db')
xmscloudcredsurl = "https://api.cloud.xirrus.com/v1/oauth/token?grant_type=password&password=xxx&username=xxx"
xmscloudurl = "https://api.cloud.xirrus.com/v1/rest/api/"
requestinterval = 180


## args
parser = ArgumentParser()
parser.add_argument("-a", "--domUuid", dest="domUuid",
                    help="domain id one gets in the discovery, for item requests", metavar="DOMAIN_UUID")               
parser.add_argument("-j", "--jsonfile", dest="jsonFile",
                    help="the apis json file and optional dir like clients.json/statuses", metavar="JSONFILE")    
parser.add_argument("-k", "--key", dest="apikey",
                    help="api key to send", metavar="APIKEY")                    
parser.add_argument("-f", "--filter", dest="filterName", nargs='?',
                    help="filter the received json if multidimensional", metavar="FILTERNAME")
parser.add_argument("-F", "--secfilter", dest="secFilterName", nargs='?',
                    help="filter the received json with key names", metavar="SECFILTERNAME")                    
parser.add_argument("-n", "--number", dest="number",
                    help="which array/Profile (?) number", metavar="NUMBER 0 to x")   
parser.add_argument("-d", "--discovery", dest="discovery",
                    help="discovers uuid and name of existent domains", nargs='?')  
args = parser.parse_args()


#### should cache like this
## get request function json loads
def getReq(url,headers):
	timenow = int(time.time())
	#### time als key in db ? un vergleichen neustes mit timenow dann können requests so bleiben? aber die verschiedenen reuests? ahaja noch nach .json ordnen in der db? das läuft
	
	checkTime = conn.execute("SELECT timenow FROM api_data WHERE timenow = ( select max(timenow) from api_data ) GROUP BY jsonurl = (?);", (jsonUrl,)).fetchone() ###new table structure api_data: time(p) data jsonurl
	
	dataAge = timenow - checkTime[0]
	if dataAge > requestinterval:
		get_request = requests.get(url, headers=headers)
		request_result = json.loads(get_request.text)
		#print(request_result, type(request_result))
		query = [int(timenow), json.dumps(request_result), str(jsonUrl)]
		#print(str(query))
		conn.executemany("INSERT OR REPLACE INTO api_data (timenow, get_request, jsonurl) VALUES (?, (?), ?);", [query])
		conn.commit()
		### refilling the recent request from its db entry should fix type problems
		request_result = json.loads(json.dumps(conn.execute("SELECT get_request FROM api_data WHERE timenow = ( select max(timenow) from api_data ) GROUP BY jsonurl = (?);", (jsonUrl,)).fetchone()))
	else:
	
		request_result = json.loads(json.dumps(conn.execute("SELECT get_request FROM api_data WHERE timenow = ( select max(timenow) from api_data ) GROUP BY jsonurl = (?);", (jsonUrl,)).fetchone()))
	
	return request_result
	
		

	
## checking and getting the auth token
token_time = conn.execute("SELECT t_date_epoch FROM api_token where t_date_epoch = ( select max(t_date_epoch) from api_token );").fetchone()
#print(token_time[0])
token_age = int(time.time()) - token_time[0]
token_size_db = conn.execute("SELECT token FROM api_token where t_date_epoch = ( select max(t_date_epoch) from api_token );").fetchone()
#print(token_size_db)
token_size = len(token_size_db[0])

if token_age > 8400 or token_size < 35: # write token only when old or false
	auth_result = json.loads(str(requests.get(xmscloudcredsurl, {"Accept":"application/json", "x-api-key":args.apikey}).text))
	#print(auth_result)
	try:
		query_string = auth_result['access_token'], int(time.time())
	except:
		query_string = "Error:"+auth_result , int(time.time()) # trigger on this to know of token errors?
		print(query_string)
	conn.executemany("INSERT INTO api_token (token,t_date_epoch) VALUES (?, ?)", [query_string])
	token = conn.execute("SELECT token FROM api_token where t_date_epoch = ( select max(t_date_epoch) from api_token );").fetchone()
	conn.commit()
else:
	token = conn.execute("SELECT token FROM api_token where t_date_epoch = ( select max(t_date_epoch) from api_token );").fetchone()

##item requests
if args.jsonFile and not args.discovery:
	jsonUrl = args.jsonFile
	reqAll = getReq(xmscloudurl+args.jsonFile, {"Accept":"application/json", "x-api-key":args.apikey, "Authorization":"bearer "+token[0], "Domain-Id": args.domUuid})
	
##this is the shit actually working with all(?) requests
	filteredJson = json.loads(reqAll[0])#[args.filterName]#[int(args.number)]#[args.secFilterName]
	print(filteredJson, type(filteredJson))
	
	
elif args.domUuid and args.discovery: #item discovery, now we can build a master protype item
	jsonUrl = args.jsonFile
	reqAll = getReq(xmscloudurl+args.jsonFile, {"Accept":"application/json", "x-api-key":args.apikey, "Authorization":"bearer "+token[0], "Domain-Id": args.domUuid})
	allJson = json.loads(reqAll[0])[args.filterName]
		
	discoverList = []
	for listcount in range(len(allJson)):## zabbix macros domain uuid und name
		
		
		
		idDict = {} # creates dict with item data
		for key in allJson[listcount].keys():
			#print(key)
			idDict[key] = allJson[listcount][key] 	
		
		
		discoverList.append(idDict) # appends each dict to list
	discoverMacroList = [{k.replace(str(k), '{#'+str(k)+'}') : v for k, v in d.items()} for d in discoverList] ### BAEM finally dict key change replaces key(k) using dict comprehension within list comprehension in some magical way from stackoverflow. do less trying around.	
	
	#domList = []
	#reqUuidList = getReq(xmscloudurl+"domains.json", {"Content-Type":"application/json", "x-api-key":args.apikey, "Authorization":"bearer "+token[0]})
	
	print(json.dumps(discoverMacroList, indent=4)) #json dump tfooi
	#print(range(len(allJson)))
	
	
##discovery		
elif args.apikey:##get domain uuid's
	jsonUrl = "domains.json"
	joUrl = str(xmscloudurl+jsonUrl)
	reqUuid = getReq(joUrl, {"Content-Type":"application/json", "x-api-key":args.apikey, "Authorization":"bearer "+token[0]})
	discoverList = []
	domIdJson = json.loads(reqUuid[0])#['data']
	#print(domIdJson, type(domIdJson))
	for listcount in range(len(domIdJson)):## zabbix macros domain uuid und name
		idDict = {} # creates dict with uuid and domain name zabbix macros 
		apDict = {}
		for key in domIdJson[listcount].keys():
			idDict[key] = domIdJson[listcount][key] 	
		discoverList.append(idDict) # appends each dict to list
	discoverMacroList = [{k.replace(str(k), '{#'+str(k)+'}') : v for k, v in d.items()} for d in discoverList] ### BAEM finally dict key change replaces key(k) using dict comprehension within list comprehension in some magical way from stackoverflow. do less trying around.	
	print(json.dumps(discoverMacroList, indent=4)) #json dump tfooi
else:
	print('''
						    ||                       '||      '||       ||          
	... ... .. .. ..    ....   ....   ... ...  ...   /\  ......   ....    || ...   || ...  ...  ... ... 
	 '|..'   || || ||  ||. '  '' .||   ||'  ||  ||  (  ) '  .|'  '' .||   ||'  ||  ||'  ||  ||   '|..'  
	  .|.    || || ||  . '|.. .|' ||   ||    |  ||    //  .|'    .|' ||   ||    |  ||    |  ||    .|.   
	.|  ||. .|| || ||. |'..|' '|..'|'  ||...'  .||.  //  ||....| '|..'|'  '|...'   '|...'  .||. .|  ||. 
									   ||           /(                                                  
									  `````        {___                                                
								xmsapi.py --help for usage
	''')                                  
	
conn.close()






