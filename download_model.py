import urllib.request
import zipfile
import os

model_url = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
zip_path = "vosk-model-small-en-us-0.15.zip"

print(f"Downloading {model_url}...")
urllib.request.urlretrieve(model_url, zip_path)
print("Download complete. Extracting...")

with zipfile.ZipFile(zip_path, 'r') as zip_ref:
    zip_ref.extractall(".")

# Rename extracted folder to 'model' for easier access
if os.path.exists("vosk-model-small-en-us-0.15"):
    os.rename("vosk-model-small-en-us-0.15", "model")
    
os.remove(zip_path)
print("Model ready in 'model' directory.")
