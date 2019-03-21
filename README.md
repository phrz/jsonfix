# jsonfix
Rough port of adhocore/php-json-fixer to Python 3
Tested with Python 3.7.2

This program can take JSON that is malformed due to being truncated and fix it.

## Usage
Where `jsonfix` refers to the repository folder in your working directory,
```bash
python3 -m jsonfix file.json # filename(s)
cat file.json | python3 -m jsonfix - # stdin
```
