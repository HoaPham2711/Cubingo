#!/usr/bin/env python3
"""Mỗi worktree một simulator riêng, tự dọn — để các phiên song song không cài đè app của nhau.

    python3 tools/dev/sim_pool.py ensure            # in UDID sim của worktree hiện tại (tạo + boot nếu cần)
    python3 tools/dev/sim_pool.py list              # các sim `factory-*` + worktree + lần dùng cuối
    python3 tools/dev/sim_pool.py gc [--idle-hours 24] [--max-booted 4] [--dry-run]
    python3 tools/dev/sim_pool.py rm [--repo <đường dẫn worktree>]

Vì sao: `run_tests.py` cũ lấy iPhone ĐANG BOOT ⇒ hai phiên ở hai worktree cùng cài app bundle id nội bộ lên
một sim, test văng/chạy nhầm binary của worktree kia.

- Tên sim: `factory-<tên thư mục worktree>-<băm 6 ký tự của đường dẫn>` — ổn định, dùng lại giữa các lượt
  (đỡ 20–30 s boot mỗi lần), không đụng sim người dùng tạo tay.
- Sổ đăng ký: MỘT sổ cố định toàn máy `~/Library/Caches/ios-app-factory/sims.json` {tên: {udid, repo, last_used}}
  (biến môi trường `FACTORY_SIM_REGISTRY` ghi đè — để test). Không theo slug app: trần `--max-booted` phải tính
  TOÀN MÁY khi có nhiều app sinh từ template; tên sim đã mang băm đường dẫn nên không đụng nhau; và module không
  phụ thuộc cấu hình app lúc import (cấu hình hỏng không làm hỏng việc dọn sim).
- `gc`: xoá sim của worktree không còn tồn tại; xoá sim không dùng quá `--idle-hours`; nếu số sim `factory-*`
  đang boot vượt `--max-booted` thì tắt bớt cái dùng lâu nhất (RAM: mỗi sim iOS ~1,5–2 GB).
  Chạy tự động ở hook SessionStart/WorktreeRemove (`.claude/hooks/sim_gc.py`).
- Chỉ đụng sim có tên bắt đầu `factory-` và có trong sổ đăng ký.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

PREFIX = "factory-"
PREFERRED_TYPES = ("iPhone 16 Pro", "iPhone 17 Pro")
REGISTRY = Path(os.environ.get("FACTORY_SIM_REGISTRY")
                or Path.home() / "Library" / "Caches" / "ios-app-factory" / "sims.json")


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(list(args), capture_output=True, text=True)


class Simctl:
    """Vỏ mỏng quanh `xcrun simctl` — test thay bằng bản giả."""

    def devices(self) -> list[dict]:
        out = json.loads(run("xcrun", "simctl", "list", "devices", "-j").stdout or "{}").get("devices", {})
        return [dict(d, runtime=rt) for rt, ds in out.items() for d in ds]

    def device_types(self) -> list[dict]:
        return json.loads(run("xcrun", "simctl", "list", "devicetypes", "-j").stdout or "{}").get("devicetypes", [])

    def runtimes(self) -> list[dict]:
        return json.loads(run("xcrun", "simctl", "list", "runtimes", "-j").stdout or "{}").get("runtimes", [])

    def create(self, name: str, type_id: str, runtime_id: str) -> str:
        r = run("xcrun", "simctl", "create", name, type_id, runtime_id)
        if r.returncode != 0:
            raise RuntimeError(f"simctl create lỗi: {r.stderr.strip()}")
        return r.stdout.strip()

    def boot(self, udid: str) -> None:
        run("xcrun", "simctl", "boot", udid)  # đã boot thì lỗi vô hại
        run("xcrun", "simctl", "bootstatus", udid, "-b")

    def shutdown(self, udid: str) -> None:
        run("xcrun", "simctl", "shutdown", udid)

    def delete(self, udid: str) -> None:
        run("xcrun", "simctl", "delete", udid)


def sim_name(repo: str) -> str:
    p = os.path.realpath(repo)
    base = re.sub(r"[^A-Za-z0-9-]+", "-", os.path.basename(p)).strip("-")[:40] or "repo"
    return f"{PREFIX}{base}-{hashlib.sha1(p.encode()).hexdigest()[:6]}"


class Registry:
    def __init__(self, path: Path = None):
        self.path = Path(path or REGISTRY)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = open(str(self.path) + ".lock", "a+")

    def __enter__(self):
        fcntl.flock(self._lock, fcntl.LOCK_EX)
        try:
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self.data = {}
        return self

    def __exit__(self, *exc):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=1, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.path)
        fcntl.flock(self._lock, fcntl.LOCK_UN)


def _pick_type_runtime(sc: Simctl) -> tuple[str, str]:
    types = sc.device_types()
    rts = [r for r in sc.runtimes() if r.get("isAvailable", True) and "iOS" in r.get("name", "")]
    if not rts:
        raise RuntimeError("không có runtime iOS nào")
    rt = sorted(rts, key=lambda r: [int(x) for x in re.findall(r"\d+", r.get("version", "0"))])[-1]
    supported = {t.get("identifier") for t in rt.get("supportedDeviceTypes", [])} or None
    cands = [t for name in PREFERRED_TYPES for t in types if t.get("name") == name]
    cands += [t for t in types if t.get("name", "").startswith("iPhone")]
    for t in cands:
        if supported is None or t["identifier"] in supported:
            return t["identifier"], rt["identifier"]
    raise RuntimeError("không có loại iPhone nào hợp runtime " + rt.get("name", "?"))


def ensure(repo: str, sc: Simctl = None, now: float = None, reg_path: Path = None) -> str:
    """UDID sim của worktree `repo`; tạo nếu chưa có, boot nếu đang tắt, ghi last_used."""
    sc = sc or Simctl()
    now = time.time() if now is None else now
    name = sim_name(repo)
    with Registry(reg_path) as reg:
        devs = {d["name"]: d for d in sc.devices() if d.get("isAvailable", True)}
        d = devs.get(name)
        if d is None:
            type_id, rt_id = _pick_type_runtime(sc)
            udid = sc.create(name, type_id, rt_id)
            state = "Shutdown"
        else:
            udid, state = d["udid"], d.get("state")
        if state != "Booted":
            sc.boot(udid)
        reg.data[name] = {"udid": udid, "repo": os.path.realpath(repo), "last_used": now}
    return udid


def gc(sc: Simctl = None, now: float = None, idle_hours: float = 24, max_booted: int = 4,
       keep: str | None = None, dry_run: bool = False, reg_path: Path = None,
       min_idle_minutes: float = 30) -> list[str]:
    """Dọn sim `factory-*`. Trả danh sách hành động (để in/test). `keep` = tên sim không được đụng."""
    sc = sc or Simctl()
    now = time.time() if now is None else now
    acts = []
    with Registry(reg_path) as reg:
        devs = {d["name"]: d for d in sc.devices()}
        for name in list(reg.data):
            info = reg.data[name]
            d = devs.get(name)
            if d is None:  # đã bị xoá tay
                del reg.data[name]
                acts.append(f"quên {name} (không còn sim)")
                continue
            if name == keep:
                continue
            gone = not os.path.isdir(info.get("repo", ""))
            idle = now - info.get("last_used", 0) > idle_hours * 3600
            if gone or idle:
                acts.append(f"xoá {name} ({'worktree đã xoá' if gone else f'không dùng > {idle_hours:g} giờ'})")
                if not dry_run:
                    sc.shutdown(d["udid"])
                    sc.delete(d["udid"])
                    del reg.data[name]
        all_booted = [n for n in reg.data if devs.get(n, {}).get("state") == "Booted"]
        n_booted = len(all_booted)
        # Chỉ tắt sim đã nhàn ≥ min_idle_minutes: last_used chỉ ghi lúc BẮT ĐẦU một lượt test, nên sim vừa
        # dùng có thể đang chạy L2 dài của phiên khác — tắt nó là làm văng test người ta.
        idle_booted = sorted((reg.data[n]["last_used"], n) for n in all_booted
                             if n != keep and now - reg.data[n]["last_used"] >= min_idle_minutes * 60)
        for _, name in idle_booted[: max(0, n_booted - max_booted)]:
            acts.append(f"tắt {name} (đang boot {n_booted} > {max_booted})")
            if not dry_run:
                sc.shutdown(devs[name]["udid"])
    return acts


def remove(repo: str, sc: Simctl = None, reg_path: Path = None) -> list[str]:
    sc = sc or Simctl()
    name = sim_name(repo)
    acts = []
    with Registry(reg_path) as reg:
        for d in sc.devices():
            if d["name"] == name:
                sc.shutdown(d["udid"])
                sc.delete(d["udid"])
                acts.append(f"xoá {name}")
        reg.data.pop(name, None)
    return acts


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("ensure")
    p.add_argument("--repo", default=os.getcwd())
    sub.add_parser("list")
    p = sub.add_parser("gc")
    p.add_argument("--idle-hours", type=float, default=24)
    p.add_argument("--max-booted", type=int, default=4)
    p.add_argument("--keep-repo")
    p.add_argument("--dry-run", action="store_true")
    p = sub.add_parser("rm")
    p.add_argument("--repo", default=os.getcwd())
    a = ap.parse_args(argv)
    if a.cmd == "ensure":
        print(ensure(a.repo))
    elif a.cmd == "list":
        with Registry() as reg:
            for n, i in sorted(reg.data.items()):
                age = (time.time() - i.get("last_used", 0)) / 3600
                print(f"{n}  {i['udid']}  {age:.1f} giờ trước  {i.get('repo')}")
    elif a.cmd == "gc":
        for x in gc(idle_hours=a.idle_hours, max_booted=a.max_booted,
                    keep=sim_name(a.keep_repo) if a.keep_repo else None, dry_run=a.dry_run):
            print(x)
    elif a.cmd == "rm":
        for x in remove(a.repo):
            print(x)
    return 0


if __name__ == "__main__":
    sys.exit(main())
