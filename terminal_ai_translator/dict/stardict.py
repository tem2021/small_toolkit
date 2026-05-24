# minimal ECDICT-compatible reader for offline lookup.
# full upstream: https://github.com/skywind3000/ECDICT/

from __future__ import annotations

import json
import sqlite3
import sys
from typing import Any, Iterable, List, Optional, Sequence, Tuple, Union

# Python 2-style names used internally by ECDICT query paths
if sys.version_info[0] >= 3:
    long = int
    unicode = str

Key = Union[int, str, unicode]


def stripword(word: str) -> str:
    """Strip non-alphanumeric chars and lower-case (ECDICT `sw` key)."""
    return "".join(ch for ch in word if ch.isalnum()).lower()


class StarDict(object):
    """Read-only ECDICT SQLite (table `stardict`). Opens existing DB paths only."""

    def __init__(self, filename: str, verbose: bool = False):
        self._dbname = filename
        self._conn: Optional[sqlite3.Connection] = None
        self._verbose = verbose
        fields = (
            "id",
            "word",
            "sw",
            "phonetic",
            "definition",
            "translation",
            "pos",
            "collins",
            "oxford",
            "tag",
            "bnc",
            "frq",
            "exchange",
            "detail",
            "audio",
        )
        self._fields: Tuple[Tuple[str, int], ...] = tuple(
            (fields[i], i) for i in range(len(fields))
        )
        self._open()

    def _open(self) -> None:
        sql_init = '''
        CREATE TABLE IF NOT EXISTS "stardict" (
            "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL UNIQUE,
            "word" VARCHAR(64) COLLATE NOCASE NOT NULL UNIQUE,
            "sw" VARCHAR(64) COLLATE NOCASE NOT NULL,
            "phonetic" VARCHAR(64),
            "definition" TEXT,
            "translation" TEXT,
            "pos" VARCHAR(16),
            "collins" INTEGER DEFAULT(0),
            "oxford" INTEGER DEFAULT(0),
            "tag" VARCHAR(64),
            "bnc" INTEGER DEFAULT(NULL),
            "frq" INTEGER DEFAULT(NULL),
            "exchange" TEXT,
            "detail" TEXT,
            "audio" TEXT
        );
        CREATE UNIQUE INDEX IF NOT EXISTS "stardict_1" ON stardict (id);
        CREATE UNIQUE INDEX IF NOT EXISTS "stardict_2" ON stardict (word);
        CREATE INDEX IF NOT EXISTS "stardict_3" ON stardict (sw, word collate nocase);
        CREATE INDEX IF NOT EXISTS "sd_1" ON stardict (word collate nocase);
        '''
        self._conn = sqlite3.connect(self._dbname, isolation_level="IMMEDIATE")
        sql_init = "\n".join(line.strip("\t") for line in sql_init.split("\n")).strip("\n")
        self._conn.executescript(sql_init)
        self._conn.commit()

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def __del__(self) -> None:
        self.close()

    def _record2obj(self, record: Optional[Sequence[Any]]) -> Optional[dict]:
        if record is None:
            return None
        word: dict[str, Any] = {}
        for name, idx in self._fields:
            word[name] = record[idx]
        if word["detail"]:
            try:
                word["detail"] = json.loads(word["detail"])
            except Exception:
                word["detail"] = None
        return word

    def query(self, key: Key) -> Optional[dict]:
        cur = self._conn.cursor()
        if isinstance(key, int) or isinstance(key, long):
            cur.execute("SELECT * FROM stardict WHERE id = ?", (key,))
        elif isinstance(key, str) or isinstance(key, unicode):
            cur.execute("SELECT * FROM stardict WHERE word = ?", (key,))
        else:
            return None
        return self._record2obj(cur.fetchone())

    def match(self, word: str, limit: int = 10, strip: bool = False) -> List[Tuple[int, str]]:
        cur = self._conn.cursor()
        if not strip:
            cur.execute(
                "SELECT id, word FROM stardict WHERE word >= ? "
                "ORDER BY word COLLATE NOCASE LIMIT ?",
                (word, limit),
            )
        else:
            cur.execute(
                "SELECT id, word FROM stardict WHERE sw >= ? "
                "ORDER BY sw, word COLLATE NOCASE LIMIT ?",
                (stripword(word), limit),
            )
        return [tuple(row) for row in cur.fetchall()]

    def query_batch(self, keys: Optional[Sequence[Key]]) -> Any:
        if keys is None:
            return None
        if not keys:
            return []
        parts = []
        for key in keys:
            if isinstance(key, int) or isinstance(key, long):
                parts.append("id = ?")
            elif key is not None:
                parts.append("word = ?")
        sql = "SELECT * FROM stardict WHERE " + " OR ".join(parts) + ";"
        query_word = {}
        query_id = {}
        cur = self._conn.cursor()
        cur.execute(sql, tuple(keys))
        for row in cur:
            obj = self._record2obj(row)
            query_word[obj["word"].lower()] = obj
            query_id[obj["id"]] = obj
        results = []
        for key in keys:
            if isinstance(key, int) or isinstance(key, long):
                results.append(query_id.get(key, None))
            elif key is not None:
                results.append(query_word.get(key.lower(), None))
            else:
                results.append(None)
        return tuple(results)

    def count(self) -> int:
        cur = self._conn.cursor()
        cur.execute("SELECT COUNT(*) FROM stardict;")
        return cur.fetchone()[0]

    def __iter__(self) -> Iterable[Tuple[int, str]]:
        cur = self._conn.cursor()
        cur.execute(
            'SELECT "id", "word" FROM "stardict" ORDER BY "word" COLLATE NOCASE;'
        )
        return iter(cur)

    def __len__(self) -> int:
        return self.count()

    def __contains__(self, key: Key) -> bool:
        return self.query(key) is not None

    def __getitem__(self, key: Key) -> Optional[dict]:
        return self.query(key)

    def dumps(self) -> List[str]:
        return [word for _, word in self]


class LemmaDB(object):
    """
    Lemma / variant lookup (BNC-derived `lemma.en.txt` from ECDICT releases).
    Line format: stem -> w1,w2,...  (optional stem/freq prefix).
    """

    def __init__(self):
        self._stems = {}
        self._words = {}
        self._frqs = {}

    def load(self, filename: str, encoding: Optional[str] = None) -> bool:
        with open(filename, "rb") as fp:
            content = fp.read()
        if content[:3] == b"\xef\xbb\xbf":
            text = content[3:].decode("utf-8", "ignore")
        elif encoding is not None:
            text = content.decode(encoding, "ignore")
        else:
            text = None
            for enc in (
                "utf-8",
                sys.getdefaultencoding(),
                "ascii",
                "gbk",
                "latin1",
            ):
                try:
                    text = content.decode(enc)
                    break
                except Exception:
                    continue
            if text is None:
                text = content.decode("utf-8", "ignore")

        for line in text.split("\n"):
            line = line.strip("\r\n ")
            if not line or line.startswith(";"):
                continue
            pos = line.find("->")
            if pos <= 0:
                continue
            stem = line[:pos].strip()
            slash = stem.find("/")
            frq = 0
            if slash >= 0:
                try:
                    frq = int(stem[slash + 1 :].strip())
                except ValueError:
                    frq = 0
                stem = stem[:slash].strip()
            if not stem:
                continue
            if frq > 0:
                self._frqs[stem] = frq
            for raw in line[pos + 2 :].strip().split(","):
                w = raw.strip()
                p1 = w.find("/")
                if p1 >= 0:
                    w = w[:p1].strip()
                if w:
                    self.add(stem, w)
        return True

    def add(self, stem: str, word: str) -> bool:
        self._stems.setdefault(stem, {})
        if word not in self._stems[stem]:
            self._stems[stem][word] = len(self._stems[stem])
        self._words.setdefault(word, {})
        if stem not in self._words[word]:
            self._words[word][stem] = len(self._words[word])
        return True

    def reset(self) -> None:
        self._stems = {}
        self._words = {}
        self._frqs = {}

    def get(self, word: str, reverse: bool = False) -> Optional[List[str]]:
        if not reverse:
            if word not in self._stems:
                return [word] if word in self._words else None
            seq = [(v, k) for k, v in self._stems[word].items()]
        else:
            if word not in self._words:
                return [word] if word in self._stems else None
            seq = [(v, k) for k, v in self._words[word].items()]
        seq.sort()
        return [k for (_, k) in seq]

    def word_stem(self, word: str) -> Optional[List[str]]:
        """Inflected surface form -> lemma list (may contain multiple stems)."""
        return self.get(word, reverse=True)

    def stem_size(self) -> int:
        return len(self._stems)

    def word_size(self) -> int:
        return len(self._words)

    def __len__(self) -> int:
        return len(self._stems)

    def __getitem__(self, stem: str) -> Optional[List[str]]:
        return self.get(stem)

    def __contains__(self, stem: str) -> bool:
        return stem in self._stems

    def __iter__(self):
        return iter(self._stems)

