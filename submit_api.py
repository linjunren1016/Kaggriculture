"""用 Kaggle 官方 Python API 直接提交，以便看到真实错误与进度。

CLI 的 submit 在本机卡住无输出，这里改用 API 并打印每步结果，
便于区分「网络问题」「配额问题」「服务端问题」。

用法：
    python submit_api.py --dry-run     # 只检查凭据与列表，不提交
    python submit_api.py               # 真正提交
"""
import argparse
import sys
import traceback


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="submission.tar.gz")
    ap.add_argument("--message", default="crop economy v1")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    try:
        from kaggle.api.kaggle_api_extended import KaggleApi
    except Exception:
        traceback.print_exc()
        return 1

    api = KaggleApi()
    try:
        api.authenticate()
        print("认证成功")
    except Exception as exc:                                   # noqa: BLE001
        print(f"认证失败: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        return 1

    # 先列一次提交，确认凭据可用且看清当前状态
    try:
        subs = api.competition_submissions("kaggriculture")
        print(f"当前提交数: {len(subs)}")
        for s in subs[:5]:
            print(f"   ref={s.ref}  {s.date}  score={getattr(s, 'publicScore', None)}")
    except Exception as exc:                                   # noqa: BLE001
        print(f"读取提交列表失败: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        return 1

    if args.dry_run:
        print("\n--dry-run：不提交")
        return 0

    print(f"\n开始上传 {args.file} ...")
    sys.stdout.flush()
    try:
        api.competition_submit(args.file, args.message, "kaggriculture")
        print("提交调用返回成功")
    except Exception as exc:                                   # noqa: BLE001
        print(f"提交失败: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        return 1

    # 提交后确认
    try:
        subs = api.competition_submissions("kaggriculture")
        print(f"\n提交后列表（{len(subs)} 条）:")
        for s in subs[:5]:
            print(f"   ref={s.ref}  {s.date}  score={getattr(s, 'publicScore', None)} "
                  f"status={getattr(s, 'status', None)}")
    except Exception as exc:                                   # noqa: BLE001
        print(f"复查失败: {type(exc).__name__}: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
