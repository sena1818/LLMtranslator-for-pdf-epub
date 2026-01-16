import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

print("正在查询可用模型...")
for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        print(f"- {m.name}")