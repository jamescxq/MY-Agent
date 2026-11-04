from dotenv import load_dotenv
import anthropic

load_dotenv()

client = anthropic.Anthropic()

response = client.messages.create(
    model = "claude-opus-5-5",
    max_tokens = 1024,
    messages =[{"role": "user" , "content": "用一句话介绍自己"}],
)

for b in response.content:
    if b.type == "text":
        print(b.text)