import base64
with open(r"C:\Users\jmkjm\Documents\2026년_정민규_활동자료\FOLDING_JIMIJIMI\LLMWiki\main.b64", "r", encoding="utf-8") as f:
    data = f.read()
out_path = r"C:\Users\jmkjm\Documents\2026년_정민규_활동자료\FOLDING_JIMIJIMI\LLMWiki\LLMWiki.tex"
with open(out_path, "w", encoding="utf-8") as f:
    f.write(base64.b64decode(data).decode("utf-8"))
print("Decoded and written!")
