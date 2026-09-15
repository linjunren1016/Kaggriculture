"""
抓取 Kaggle 为提交返回的「上传地址」，但不执行上传。

提交是三步：1) start_submission_upload 拿地址 → 2) PUT 文件到该地址 → 3) create_submission。
本机卡在第 2 步（该 PUT 没有设置 timeout，连不上就永久阻塞）。

这个脚本只做第 1 步，把地址打印出来，便于：
  - 确认上传目标域名（通常是 Google Cloud Storage）
  - 单独测试到该域名的连通性
  - 让能正常上传的机器照着这个地址验证

注意：第 1 步会为本次调用分配一个上传会话，但因为没有完成 PUT，
不会产生任何提交记录。
"""
import os
import socket
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

FILE = "submission.tar.gz"
out = []


def log(m):
    out.append(str(m))
    print(m)


try:
    from kaggle.api.kaggle_api_extended import KaggleApi
    from kagglesdk.competitions.types.competition_api_service import (
        ApiStartSubmissionUploadRequest,
    )
except Exception as exc:                                       # noqa: BLE001
    log(f"导入失败: {type(exc).__name__}: {exc}")
    raise SystemExit(1)

api = KaggleApi()
api.authenticate()
log("认证成功")

req = ApiStartSubmissionUploadRequest()
req.competition_name = "kaggriculture"
req.file_name = os.path.basename(FILE)
req.content_length = os.path.getsize(FILE)
req.last_modified_epoch_seconds = int(os.path.getmtime(FILE))
log(f"文件 {FILE}  大小 {req.content_length} 字节")

try:
    with api.build_kaggle_client() as kaggle:
        resp = kaggle.competitions.competition_api_client.start_submission_upload(req)
except Exception as exc:                                       # noqa: BLE001
    log(f"第1步失败: {type(exc).__name__}: {exc}")
    raise SystemExit(1)

log("")
log("=== 第1步成功，Kaggle 返回的上传信息 ===")
for attr in ("token", "create_url"):
    log(f"  {attr} = {getattr(resp, attr, None)}")

url = getattr(resp, "create_url", None)
if url:
    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname
    log("")
    log(f"上传目标域名: {host}")
    log(f"上传路径前缀: {parsed.path[:80]}...")
    log("")
    log("=== 到该域名的连通性测试 ===")
    try:
        t0 = __import__("time").time()
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
        ips = sorted({i[4][0] for i in infos})
        log(f"  DNS {host} -> {ips}  ({__import__('time').time()-t0:.2f}s)")
    except Exception as exc:                                   # noqa: BLE001
        log(f"  DNS 失败: {type(exc).__name__}: {exc}")
    try:
        t0 = __import__("time").time()
        s = socket.create_connection((host, 443), timeout=15)
        s.close()
        log(f"  TCP 443 连接成功  ({__import__('time').time()-t0:.2f}s)")
    except Exception as exc:                                   # noqa: BLE001
        log(f"  TCP 443 连接失败: {type(exc).__name__}: {exc}")

log("")
log("提示：第2步是 PUT 该地址，kaggle 库对它没有设置 timeout，所以连不上会永久阻塞。")

with open("_docx/upload_url.txt", "w", encoding="utf-8") as fh:
    fh.write("\n".join(out))
