import json
from json import JSONDecodeError
from pathlib import Path
from datetime import datetime, timezone
from openai import OpenAI, AuthenticationError, APIConnectionError
from dict.stardict import stripword, StarDict, LemmaDB

# write to the log file
def append_entry(store_path: Path, text: str):
    record = { 
        "time": datetime.now(timezone.utc).isoformat(),
        "text": text
    }
    line = json.dumps(record) + "\n"
    with store_path.open("a", encoding="utf-8") as f:
        f.write(line)

# return the llm response
def ask_llm(query: str, client: OpenAI):
    user_content = (
        f'please translate {query} into chinese, '
        'the output must be of this json format: '
        '{"query": original / corrected query, "'
        ' "phonetic": word\'s phonetic, '
        ' "translation": word\'s / sentence\'s translation }'
        ' the following parts should NEVER in the output, they are just'
        ' extra EXPLANATION: here are several situation.'
        ' 1. if the input is not a meaningfull sentence/word at all, '
        '    the output "query" should be "meaningless",'
        '    the "phonetic" and "translation" should be "None".'
        ' 2. the input query might have incorrect format or mistakes:"'
        '    the output "query" should use the correct one'
        '    and should use the format like correct query [language].'
        '    for example: complex [英语],'
        '    notice the "query" should always in original language'
        '    notice the "query" should always contain [language]'
        ' 3. the "phonetic" should return "None" if input query is a sentence'
        ' 4. the "translation" should be of the following format: '
        '    if input query is a word, use the format like:'
        '    n. 综合体, 情结, 络合物\\n a. 复杂的, 组合的 '
        '    if input query is a sentence, use the format like:'
        '    one-line translation. for example: 这很好'
        '    if there is " in the sentence, please strictly use \\" '
        '    for example: "query": "these files use \\".zip\\" format". '
    )
    messages = [ 
        {"role": "system", "content": "You are a professional translator"}, 
        {"role": "user", "content": user_content}
    ]
    try:
        response = client.chat.completions.create(
            model="deepseek-v4-flash",
            messages=messages,
            stream=False,
            extra_body={"thinking": {"type": "disabled"}}
        )
        return response.choices[0].message.content
    except AuthenticationError:
        return "API key is invalid\nplease update the API key"
    except APIConnectionError:
        return ("the network connection is not stable\n" + 
               "please switch to the offline mode")

# return the output data
def translation(mode: str, query: str, db: StarDict, lemma: LemmaDB,
                client: OpenAI):
    if mode == "online" and len(query.split()) > 1:
        output = ask_llm(query, client)
        try: data = json.loads(output)
        except JSONDecodeError: return {0: output, 1:None, 2: None}
        translation = None
        if data["translation"] != "None": translation = data["translation"]
        return {0: data["query"], 1: None, 2: translation}
    if mode == "offline": query = stripword(query); 
    else: query = query.strip()
    resp = db.query(query)
    if not resp: 
        origin = lemma.word_stem(query)
        if origin: resp = db.query(origin[0])
    if not resp:
        if mode == "online":
            output = ask_llm(query, client)
            try: data = json.loads(output)
            except JSONDecodeError: return {0: output, 1:None, 2: None}
            phonetic = None; translation = None
            if data["phonetic"] != "None": phonetic = data["phonetic"]
            if data["translation"] != "None": translation = data["translation"]
            return {0: data["query"], 1: phonetic, 2: translation}
            return {0: query, 1: None, 2: data}
        match = db.match(query, limit=1)
        if match: 
            query = match[0][1]
            resp = db.query(query)
        else: return {0: query, 1: None, 2: "not result found"}
    return { 0: query, 1: resp["phonetic"], 2: resp["translation"]}

# parse input, print output, return the updated last_query and mode
def parse_input(store_path: Path, query: str, last_query: str,
                db: StarDict, lemma: LemmaDB, client: OpenAI,
                force_offline: bool, mode: str):
    if query.startswith("*"):   # storage
        if query[1:].strip() == "": 
            if last_query == "": 
                print("no previous query")
                return last_query, mode
            print(f'store "{last_query}" to the log file')
            append_entry(store_path, last_query)
        else: 
            print(f'store "{query[1:].strip()}" to the log file')
            append_entry(store_path, query[1:].strip())
        return last_query, mode

    if query.startswith("^"):
        records = [] 
        log_number = 10
        with store_path.open("r", encoding="utf-8") as f:
            for line in f: records.append(json.loads(line))

        query_tail = query[1:].strip()
        if query_tail.isdigit(): log_number = int(query_tail)
        elif query_tail == "p":
            print(f"the log file: {Path.cwd()/store_path}")
            return last_query, mode
        elif query_tail != "": 
            print("invalid input")
            return last_query, mode

        print(f"the lastest {log_number} logs:")
        index = 1
        log_number = min(len(records), log_number)
        while index <= log_number:
            log_utc_time = datetime.fromisoformat(records[0-index]["time"])
            log_text = records[0-index]["text"]
            log_local_time = log_utc_time.astimezone().strftime( "%Y-%m-%d")
            print(
                f"({index:{len(str(log_number))}}) {log_local_time} {log_text}"
            )
            index += 1
        return last_query, mode

    if query.startswith("`"):
        if query[1:].strip() != "": 
            print("invalid input")
            return last_query, mode
        if force_offline == 1: 
            print("force offline")
        else:
            if mode == "online": mode = "offline" 
            elif mode == "offline": mode = "online"
            print(f"{mode.upper()} MODE")
        return last_query, mode
    
    output = translation(mode, query, db, lemma, client) 
    if output[1]: print(f"{output[0]} [{output[1]}]")
    else: print(output[0])
    if output[2]: print(output[2])

    return query, mode

if __name__ == "__main__":
    last_query = ""
    force_offline = 0
    mode = "online"
    store_path = Path("log.txt")
    readme_path = Path("README")

    if not store_path.exists():
        store_path.touch()

    db = StarDict("dict/stardict.db")
    lemma = LemmaDB()
    lemma.load("dict/lemma.en.txt")

    api_path = Path("DEEPSEEK_API_KEY")
    if api_path.exists(): 
        with api_path.open("r", encoding="utf-8") as f:
            api_key = f.read().strip()
    else:
        print("no API key find, force offline")
        api_key = "NULL"
        mode = "offline"
        force_offline = 1

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com"
    )

    print(f"{mode.upper()} MODE")

    while 1: 
        try: query = input("> ").strip()
        except (KeyboardInterrupt, EOFError): raise SystemExit("")
        if query in ["q", "quit", "exit"]: break
        if query in ["h", "help"]:
            with readme_path.open("r", encoding="utf-8") as f:
                print(f.read(), end="")
            continue
        last_query, mode = parse_input(store_path, query, last_query, db, 
                                       lemma, client, force_offline, mode)

