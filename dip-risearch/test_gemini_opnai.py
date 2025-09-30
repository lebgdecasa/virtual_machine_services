from openai import OpenAI

# Initialize the client to use Gemini
client = OpenAI(
  api_key="AIzaSyCE6AqkZYRCTXjjNpnihqpZT6UqIPW0ZYM",
  base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

# Use the chat completions endpoint as you would with OpenAI
response = client.chat.completions.create(
  model="gemini-2.5-flash", # Specify the Gemini model
  messages=[
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Explain how a large language model works."}
  ]
)

print(response.choices[0].message)
