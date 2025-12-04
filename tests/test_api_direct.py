import requests

story_id = '36735'  # The Perfect Run
url = f'https://www.wattpad.com/api/v3/stories/{story_id}'
params = {'fields': 'id,title,numParts'}

r = requests.get(url, params=params, timeout=10)
print(f'Status: {r.status_code}')

if r.ok:
    data = r.json()
    print(f'Title: {data.get("title")}')
    print(f'Parts: {data.get("numParts")}')
else:
    print(f'Error: {r.text[:200]}')
