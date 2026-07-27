from google import genai
from dotenv import load_dotenv
import os
from pathlib import Path
from google.genai import types

load_dotenv()

folder_struct_input = []

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

folder = input("Enter the folder path: ")

root_dir = Path(folder)

for path in root_dir.rglob('*'):
    if path.is_dir():
        
        
    elif path.is_file():
        pass
    
prompt = f"""
You are an expert code classifier.

Analyze this source file.

Return ONLY valid JSON.

{{
    "language": "",
    "category": "",
    "topic": "",
    "summary": "",
    "keywords": []
}}

Filename:
{file.name}

Content:
{content}
"""

response = client.models.generate_content(
    model="gemini-3.1-flash-lite",
    contents=prompt,
    config=types.GenerateContentConfig(
        response_mime_type="application/json"
    )
)

print(response.text)