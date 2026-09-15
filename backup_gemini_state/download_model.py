import urllib.request
import os

print("Downloading High-Quality Jarvis Piper model...")
onnx_url = "https://huggingface.co/jgkawell/jarvis/resolve/main/en/en_GB/jarvis/high/jarvis-high.onnx"
json_url = "https://huggingface.co/jgkawell/jarvis/resolve/main/en/en_GB/jarvis/high/jarvis-high.onnx.json"

os.makedirs("model", exist_ok=True)

print("Downloading jarvis-high.onnx (this is larger, may take a minute)...")
urllib.request.urlretrieve(onnx_url, "model/jarvis.onnx")

print("Downloading jarvis-high.onnx.json...")
urllib.request.urlretrieve(json_url, "model/jarvis.onnx.json")

print("Done! High quality model installed.")
