import openai
r = openai.api_requestor.APIRequestor();
resp = r.request("GET", '/usage?date=2023-11-14'); 
resp_object = resp[0]
resp_object.data 