from google import genai

client = genai.Client(api_key="AQ.Ab8RN6JUXYC2B8QL_cPaeZkeXgeD2wTsMTcjfFABD3R67_4NFw")
res = client.models.generate_content(
    model="gemini-3.8-flash",
    contents="Say hello to Dadi in one warm sentence."
)
print(res.text)