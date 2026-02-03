from google import genai

client = genai.Client(api_key="AIzaSyD0YsAOP6d3lRjN4TBp8OdUOx0dTy3eTEQ")

print("Available models:")
for model in client.models.list():
    print(f"  - {model.name}")