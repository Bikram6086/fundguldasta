import requests
r = requests.get("https://www.amfiindia.com/spages/NAVAll.txt", timeout=30)
for line in r.text.split("\n"):
    if any(code in line for code in ["118825", "118834", "120152", "119071"]):
        print(repr(line[:150]))
