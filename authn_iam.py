import boto3
import requests
import json
import urllib.parse

session = boto3.Session()
credentials = session.get_credentials().get_frozen_credentials()

from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

host_id = "host/aws-demo-host"
conjur_url = "http://conjur-nhi-demo-conjur-1"
service_id = "prod"
account = "dev"

body = "Action=GetCallerIdentity&Version=2011-06-15"

request = AWSRequest(
    method="POST",
    url="https://sts.amazonaws.com/",
    data=body,
    headers={"Host": "sts.amazonaws.com"}
)
SigV4Auth(credentials, "sts", "us-east-1").add_auth(request)

headers_dict = {}
for k, v in request.headers.items():
    if isinstance(v, bytes):
        v = v.decode("utf-8")
    headers_dict[k] = v

print("DEBUG headers:", json.dumps(headers_dict, indent=2))
print("DEBUG body:", repr(body))

encoded_host_id = urllib.parse.quote(host_id, safe="")
authn_url = f"{conjur_url}/authn-iam/{service_id}/{account}/{encoded_host_id}/authenticate"

response = requests.post(
    authn_url,
    headers={"Content-Type": "application/json"},
    data=json.dumps(headers_dict)
)

print("Status:", response.status_code)
print("Response:", response.text[:500])
