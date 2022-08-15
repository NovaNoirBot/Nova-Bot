"""
安全性相关的模块
- 对于数据库泄漏的情形, 提供了 `AES` 和 `RSA` 加密, 可以有效阻止敏感信息泄漏.
    Warning: 对于被拿 Shell 或者可以 RCE 的情形, 加密的作用微乎其微.
- 对于需要身份验证的情形, 提供了 `SCrypt` 哈希算法

默认情况下, 以 `QQ_ID` 为单位进行 `SECRET` / `IV` 的生成, 意即每个 `QQ_ID` 使用相同的 `SECRET` 和 `IV`, 可以通过传入适当的参数更改
默认情况下, 在 `$HOME/.secret/Nova-Bot/` 目录下生成盐文件, 可以通过传入适当的参数更改
"""

import base64
import random
import string
from pathlib import Path
from typing import Union, Optional, Tuple

from Crypto.Cipher import AES
from Crypto.Protocol.KDF import scrypt
from Crypto.Random import get_random_bytes


def get_salt(path: Optional[Union[str, Path]] = None,
             *,
             length: Optional[int] = 32,
             force: Optional[bool] = False) -> str:
    """
    获取盐值, 默认情况下, 在 `$HOME/.secret/Nova-Bot/salt` 文件里写入一个 32bits 的盐
    :param force: 是否强制生成新的 `salt`, 默认为 `否`
    :param path: 盐文件的完整路径
    :param length: 生成盐的长度 [bit(s)], 默认为 `32`, 在盐文件存在且 `force == False` 的情况下无作用
    :return: 盐
    """
    if not path:
        path = Path("~/.secret/Nova-Bot/salt").expanduser()
    if isinstance(path, str):
        path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Generate New Salt
    if not path.exists() or force:
        with open(path, 'w') as f:
            salt = "".join(random.choices(string.digits + string.ascii_letters + string.punctuation, k=length))
            f.write(salt)
        path.chmod(0o600)
    else:
        with open(path, 'r') as f:
            salt = f.read()
    return salt


def SCrypt(content: str,
           salt: Optional[str] = None,
           *,
           key_len: Optional[int] = 32,
           N: Optional[int] = 8192,
           r: Optional[int] = 8,
           p: Optional[int] = 1,
           base64_: Optional[bool] = True) -> Union[bytes, Tuple[bytes, ...]]:
    """
    SCrypt 哈希方式, 默认情况采用 8 个块, 8192 次迭代, 32 位哈希长度并返回 base64 编码的字节串
    :param base64_: 是否使用 base64 编码结果, 默认为 `是`
    :param content: 要加密的内容
    :param salt: 盐, 默认为 `get_salt()`
    :param key_len:
    :param N:
    :param r:
    :param p:
    :return:
    """
    if not salt:
        salt = get_salt()
    return base64.b64encode(scrypt(content, salt, key_len, N, r, p)) if base64_ \
        else scrypt(content, salt, key_len, N, r, p)


def __get_qq_secret_and_iv(qq: Union[int, str],
                           path: Optional[Union[str, Path]] = None,
                           *,
                           secret: Optional[bytes] = None,
                           iv: Optional[bytes] = None,
                           force: Optional[bool] = False) -> Tuple[bytes, bytes]:
    """
    获取 `QQ_ID` 对应的 `SECRET` 和 `IV`, 在文件不存在的情况下, 生成新的 `SECRET` 和 `IV`, 可被指定特定内容
    否则 `SECRET` 为 32 位随机字节, `IV` 为 16 位随机字节
    :param qq: QQ 号
    :param path: 文件所在的目录路径, 默认为 `Nova-Bot/data/crypto/`
    :param secret: 仅在 `文件不存在` 或 `force == True` 的情况下作用, 指定文件的 `SECRET` 值 32 bits
    :param iv: 仅在 `文件不存在` 或 `force == True` 的情况下作用, 指定文件的 `IV` 值 16 bits
    :param force: 是否强制更新文件, 默认为 `否`
    :return: 包含 `SECRET` 与 `IV` 的元组
    """
    if isinstance(qq, int):
        qq = str(qq)
    if not path:
        path = Path.cwd() / "data" / "crypto"
    if isinstance(path, str):
        path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    path = path / qq
    if not path.exists() or force:
        with open(path, 'wb') as f:
            results = (secret or get_random_bytes(32),
                       iv or get_random_bytes(16))
            f.write(b"\r\n".join(results))
        path.chmod(0o600)
    else:
        with open(path, 'rb') as f:
            results = f.readlines()
            results = tuple(map(lambda x: x.replace(b"\r\n", b""), results))
        if len(results) != 2:  # Re-generate secret and iv for corrupted file
            __get_qq_secret_and_iv(qq, path, secret=secret, iv=iv, force=force)
    return results


def QQ_AES(qq: Union[int, str],
           *,
           path: Optional[Union[str, Path]] = None,
           mode: Optional[int] = AES.MODE_CFB,
           secret: Optional[bytes] = None,
           iv: Optional[bytes] = None,
           temp: Optional[bool] = False,
           force: Optional[bool] = False) -> AES:
    """
    获取 `QQ_ID` 对应的 AES
    - 若 `temp == false`, 将会从文件中读取 (若不存在或 `force == True` 则会新生成) `SECRET` 和 `IV`
        -- 若指定了 `SECRET` 和 `IV`, 在新生成的过程中会写入指定值, 否则 `SECRET` 为 32 位随机字节, `IV` 为 16 位随机字节
    :param qq: QQ 号
    :param path: 文件所在的目录路径, 默认为 `Nova-Bot/data/crypto/`
    :param mode: AES 加密模式, 默认为 CFB
    :param secret: 强制指定 AES 使用的 `SECRET`, 在 `temp == False` 的情况下还会将其传入 `__get_qq_secret_and_iv` 作为初始参数
    :param iv: 强制指定 AES 使用的 `IV`, 在 `temp == False` 的情况下还会将其传入 `__get_qq_secret_and_iv` 作为初始参数
    :param temp: 是否为临时 AES , 意即不保存到文件中, 默认为 `否`
    :param force: 是否强制刷新 `QQ_ID` 对应的 `SECRET` 和 `IV` 文件, 默认为 `否`
    :return: 对应的 AES
    """
    if temp:
        secret = secret or get_random_bytes(32)
        iv = iv or get_random_bytes(16)
    else:
        _temp_secret, _temp_iv = __get_qq_secret_and_iv(qq,
                                                        path,
                                                        secret=secret,
                                                        iv=iv,
                                                        force=force)
        secret = secret or _temp_secret
        iv = iv or _temp_iv
    return AES.new(secret, mode, iv)


__all__ = ["get_salt",
           "QQ_AES",
           "SCrypt"]
