import os
import json
import base64
import asyncio
import websockets
from audio_stream import input_queue, play_audio, interrupt_playback, set_recording

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()

system_instruction = (
    "You are J.A.R.V.I.S., a highly advanced AI assistant created to serve the user. "
    "You speak in a British accent. You are polite, casual, and employ dry wit when appropriate. "
    "Always address the user as 'sir'. If the 'toggle_group_mode' tool has been enabled, you will hear "
    "other voices from a Discord call mixed with the user's microphone. Address them as 'everyone' or 'you guys' instead of just 'sir' when responding to the group. "
    "Keep all responses extremely brief and straight to the point."
)

import inspect
import tools
import memory

_tools = []
for name, func in inspect.getmembers(tools, inspect.isfunction):
    # Only register public functions defined in the tools module (or imported explicitly)
    if not name.startswith("_") and func.__module__ in ["tools", "memory"]:
        doc = inspect.getdoc(func) or f"Executes the {name} tool."
        sig = inspect.signature(func)
        properties = {}
        required = []
        for param_name, param in sig.parameters.items():
            param_type = "string"
            if param.annotation == int: param_type = "integer"
            elif param.annotation == bool: param_type = "boolean"
            elif param.annotation == float: param_type = "number"
            
            properties[param_name] = {"type": param_type}
            if param.default == inspect.Parameter.empty:
                required.append(param_name)
                
        tool_def = {
            "type": "function",
            "name": name,
            "description": doc,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required
            }
        }
        _tools.append(tool_def)


class JarvisRealtimeClient:
    def __init__(self, ui_set_state_cb=None):
        self.ws = None
        self.ui_set_state_cb = ui_set_state_cb
        
    async def connect(self):
        url = "wss://api.openai.com/v1/realtime?model=gpt-realtime"
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}"
        }
        self.ws = await websockets.connect(url, additional_headers=headers)
        
        # Configure session
        import memory
        memories = memory.get_all_memories()
        session_instructions = system_instruction
        if memories:
            session_instructions += "\n\nUser Profile & Memories:\n" + "\n".join(f"- {m}" for m in memories)
            
        await self.ws.send(json.dumps({
            "type": "session.update",
            "session": {
                "type": "realtime",
                "output_modalities": ["audio"],
                "instructions": session_instructions,
                "audio": {
                    "input": {
                        "format": {"type": "audio/pcm", "rate": 24000},
                        "transcription": {"model": "whisper-1"},
                        "turn_detection": {
                            "type": "server_vad",
                            "threshold": 0.8,
                            "prefix_padding_ms": 300,
                            "silence_duration_ms": 800
                        }
                    },
                    "output": {
                        "format": {"type": "audio/pcm", "rate": 24000},
                        "voice": "marin"
                    }
                },
                "tools": _tools
            }
        }))
        print("[LLM] Connected to OpenAI Realtime API.")

    async def mic_audio_loop(self):
        """Continuously capture audio from mic and send it to the Realtime API."""
        import base64
        try:
            set_recording(True)
            while True:
                chunk = await asyncio.to_thread(input_queue.get)
                if chunk and self.ws:
                    encoded = base64.b64encode(chunk).decode("utf-8")
                    await self.ws.send(json.dumps({
                        "type": "input_audio_buffer.append",
                        "audio": encoded
                    }))
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[Mic Audio Loop Error] {e}")

    async def reminders_loop(self):
        """Checks for scheduled reminders and triggers them by injecting messages into the conversation."""
        import json
        import os
        import time
        
        reminders_file = os.path.join(os.path.dirname(__file__), "reminders.json")
        while True:
            await asyncio.sleep(5)
            if not self.ws:
                continue
                
            if not os.path.exists(reminders_file): 
                continue
                
            try:
                with open(reminders_file, "r") as f:
                    data = json.load(f)
                changed = False
                now = time.time()
                for r in data:
                    if not r.get("done") and now >= r.get("trigger_time"):
                        r["done"] = True
                        changed = True
                        print(f"\n[Reminders] Triggering reminder: {r['text']}")
                        # Inject hidden prompt to OpenAI
                        msg = f"SYSTEM_ALERT: The reminder for '{r['text']}' has just triggered! Verbally announce this to the user immediately."
                        await self.ws.send(json.dumps({
                            "type": "conversation.item.create",
                            "item": {
                                "type": "message",
                                "role": "user",
                                "content": [{"type": "input_text", "text": msg}]
                            }
                        }))
                        await self.ws.send(json.dumps({"type": "response.create"}))
                if changed:
                    with open(reminders_file, "w") as f:
                        json.dump(data, f, indent=4)
            except Exception as e:
                print(f"[Reminders] Error: {e}")

    async def receive_events_loop(self):
        import tools
        async for message in self.ws:
            event = json.loads(message)
            evt_type = event.get("type")
            
            if evt_type == "input_audio_buffer.speech_started":
                print("[LLM] User speaking...")
                if self.ui_set_state_cb:
                    self.ui_set_state_cb("listening")
                interrupt_playback()
                
            elif evt_type == "input_audio_buffer.speech_stopped":
                print("[LLM] User stopped speaking. Processing...")
                if self.ui_set_state_cb:
                    self.ui_set_state_cb("thinking")
                    
            elif evt_type == "response.output_audio.delta":
                if self.ui_set_state_cb:
                    self.ui_set_state_cb("speaking")
                pcm_bytes = base64.b64decode(event["delta"])
                play_audio(pcm_bytes)
                
            elif evt_type == "error":
                print(f"[LLM Error] {event}")
                
            elif evt_type in ["response.text.delta", "response.output_audio_transcript.delta"]:
                print(event.get("delta", ""), end="", flush=True)
                
            elif evt_type == "response.done":
                print("\n[LLM] Response done.")
                if self.ui_set_state_cb:
                    self.ui_set_state_cb("idle")
                
            elif evt_type == "response.function_call_arguments.done":
                name = event.get("name")
                call_id = event.get("call_id")
                args = json.loads(event.get("arguments", "{}"))
                print(f"[Tool Call] {name}({args})")
                
                # Execute tool
                # Execute tool dynamically
                result_str = ""
                try:
                    if hasattr(tools, name):
                        func = getattr(tools, name)
                        print(f"[LLM] Executing {name}...")
                        result_str = str(func(**args))
                    else:
                        result_str = f"Tool {name} not found."
                except Exception as e:
                    result_str = f"Error executing {name}: {e}"
                    
                print(f"[Tool Result] {result_str}")
                
                # Send result back
                await self.ws.send(json.dumps({
                    "type": "conversation.item.create",
                    "item": {
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": result_str
                    }
                }))
                
                await self.ws.send(json.dumps({"type": "response.create"}))

    async def run(self):
        self._loop = asyncio.get_running_loop()
        self._stop_event = asyncio.Event()
        
        await self.connect()
        
        send_task = asyncio.create_task(self.mic_audio_loop())
        recv_task = asyncio.create_task(self.receive_events_loop())
        reminders_task = asyncio.create_task(self.reminders_loop())
        
        await self._stop_event.wait()
        
        send_task.cancel()
        recv_task.cancel()
        reminders_task.cancel()
        if self.ws:
            await self.ws.close()
            self.ws = None

    def disconnect(self):
        if hasattr(self, '_stop_event') and self._stop_event and hasattr(self, '_loop'):
            self._loop.call_soon_threadsafe(self._stop_event.set)

def start_realtime_loop(ui_set_state_cb=None):
    client = JarvisRealtimeClient(ui_set_state_cb)
    try:
        asyncio.run(client.run())
    except KeyboardInterrupt:
        pass
