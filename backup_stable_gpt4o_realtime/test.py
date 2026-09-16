import asyncio
import websockets
import os
import json
from dotenv import load_dotenv

load_dotenv()

async def test():
    key = os.environ.get('OPENAI_API_KEY').strip()
    url = 'wss://api.openai.com/v1/realtime?model=gpt-realtime'
    headers = {
        'Authorization': f'Bearer {key}'
    }
    
    try:
        async with websockets.connect(url, additional_headers=headers) as ws:
            # We don't send session.update to avoid errors. We just trigger a response.
            await ws.send(json.dumps({
                'type': 'response.create',
                'response': {
                    'instructions': 'Say the exact words: Hello World'
                }
            }))
            print("Requested response.")
            for _ in range(20):
                res = await ws.recv()
                evt = json.loads(res)
                print(evt['type'])
                if evt['type'] == 'error':
                    print(res)
                if evt['type'] == 'response.done':
                    print("Response done. Token usage:", evt.get('response', {}).get('usage'))
                    break
    except Exception as e:
        print("Error:", repr(e))

asyncio.run(test())
