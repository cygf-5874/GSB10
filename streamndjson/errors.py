"""异常定义。"""


class StreamError(Exception):
    """本模块所有异常的基类。"""


class StreamDecodeError(StreamError):
    """字节不是合法 UTF-8，或某一行不是合法 JSON 对象。"""
