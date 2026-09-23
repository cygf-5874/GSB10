# streamndjson

上游采集 agent 按固定大小分块推送 NDJSON（newline-delimited JSON）字节流，
这个库负责把字节流还原成一条条记录。用在日志采集和实时指标管道里。

零第三方依赖，Python 3.9 以上直接跑：

```bash
python3 -m unittest discover -s tests -v
python3 repro.py
```

## 公开 API

```python
from streamndjson import NDJSONReader, iter_chunks, StreamDecodeError

reader = NDJSONReader()
for chunk in iter_chunks("testdata/events.ndjson", 8192):
    for record in reader.feed(chunk):
        ...                      # 每次 feed 返回 0..N 条
for record in reader.close():
    ...                          # 收尾

reader.count                     # 已产出的记录条数
```

| 接口 | 说明 |
| --- | --- |
| `iter_chunks(source, size)` | `source` 接受路径或 `bytes`，按 `size` 字节切块。`size` 非正整数抛 `ValueError`。 |
| `NDJSONReader.feed(chunk)` | 喂入一段字节，返回**本次**能完整解析出的记录列表。只接受 `bytes` / `bytearray`。 |
| `NDJSONReader.close()` | 声明输入结束，返回剩余记录。可重复调用；`close()` 之后再 `feed()` 抛 `RuntimeError`。 |
| `NDJSONReader.count` | 已产出的记录条数。 |
| `StreamDecodeError` | 行不是合法 JSON、不是 JSON 对象，或不是合法 UTF-8 时抛出。 |

**分块边界不保证落在行边界上，也不保证落在字符边界上**，调用方不要对块内容做任何假设。

## 验收入口

`bench.py` 是判据脚本，**不要改**：

```bash
python3 bench.py --check    # 同一份数据按多种块大小读，结果必须逐条一致
python3 bench.py --bench    # 长记录 + 1 字节块，必须在 TIME_LIMIT 内读完
python3 repro.py            # 上游给的复现脚本，必须读出 7 条
```

`--bench` 的场景是上游真实会遇到的：agent 用小缓冲逐字节推送，而单条记录可能很大
（这里压到 1 MiB）。**小块吞吐和"结果正确"一样是硬要求**，`TIME_LIMIT` 见 `bench.py`
文件头。

## 输入约定

1. 编码 UTF-8，文件可以带 BOM。
2. 行分隔符是 `\n`，也要兼容 `\r\n`。
3. 最后一行可以没有结尾换行符。
4. 空行（含纯空白行）忽略，不计入 `count`。
5. JSON 字符串值里可能出现**未被转义**的 Unicode 行分隔类字符（`U+2028` 等），
   它们不是行分隔符，不能被当成分行依据。

## 目录

```
streamndjson/
  errors.py     异常层级
  reader.py     NDJSONReader
  source.py     iter_chunks
tests/          既有用例
testdata/       样例数据（中文、emoji、超长行、BOM）
bench.py        验收入口：--check 差分对拍 / --bench 小块吞吐
repro.py        上游给的复现脚本
tools/          手工观察用的小工具
```
