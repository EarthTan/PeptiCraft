"""Write a progress page for the structure batch.

    python scripts/progress_dashboard.py \
        --manifest ../exports/PeptiCraft-OmegaFold-Pack-20261102/manifest.csv \
        --folds ~/pepticraft-structures \
        --state ~/.pepticraft-upload-state.json \
        --out ~/pepticraft-progress.html \
        --machine "宿舍 Ubuntu|ubuntu-tailscale|8:00–23:00|/home/a/p1.fasta,/home/a/p2.fasta|/home/a/folds/pdb" \
        --machine "工作站|dku-tailscale|7×24|/home/b/p1.fasta|/home/b/folds/pdb"

The batch runs for months, so "how far along is it" is not answerable by a percentage alone.
Two figures disagree and both are true: the count of finished structures, and the machine time
they cost. Short chains finish in seconds and long ones in twenty minutes, so the count runs
far ahead of the clock. The page states both and lets the reader see why they differ.

The totals come from the manifest, the staging directory and the upload record, all local, so
a rewrite costs nothing and cannot fail. The per-machine panel is different: only the machine
knows how far its own share has got, so each one is asked over a short ssh call. A machine
that does not answer is reported as out of reach rather than assumed idle, and the rest of the
page is written regardless.
"""

from __future__ import annotations

import argparse
import csv
import json
import shlex
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

FIT_A = 7.06e-05
FIT_B = 2.3467

PHASE_ONE_TIERS = (1, 2)


def seconds_for(length: int) -> float:
    """Machine time a chain of this length takes, from the fit over measured runs."""
    return FIT_A * (length**FIT_B)


def read_manifest(path: Path) -> dict[str, tuple[int, int]]:
    """structure_id -> (tier, fused length).

    A structure appears once per linker and scaffold path that reaches it, so the first row
    that mentions it assigns its tier; later rows repeat the same value.
    """
    tiers: dict[str, tuple[int, int]] = {}
    with path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            sid = row["structure_id"]
            if sid not in tiers:
                tiers[sid] = (int(row["tier"]), int(row["fused_length"]))
    return tiers


def count_folded(directory: Path) -> set[str]:
    if not directory.is_dir():
        return set()
    return {entry.stem for entry in directory.glob("*.pdb")}


def count_published(state: Path) -> int:
    if not state.is_file():
        return 0
    try:
        return len(json.loads(state.read_text()))
    except (json.JSONDecodeError, TypeError):
        return 0


def summarise(tiers, folded) -> dict:
    per_tier = {}
    for tier in (1, 2, 3):
        ids = [sid for sid, (t, _) in tiers.items() if t == tier]
        done = [sid for sid in ids if sid in folded]
        left = [sid for sid in ids if sid not in folded]
        per_tier[tier] = {
            "total": len(ids),
            "done": len(done),
            "hours_done": sum(seconds_for(tiers[s][1]) for s in done) / 3600,
            "hours_left": sum(seconds_for(tiers[s][1]) for s in left) / 3600,
        }

    phase_one_left = sum(per_tier[t]["hours_left"] for t in PHASE_ONE_TIERS)
    total_left = phase_one_left + per_tier[3]["hours_left"]
    return {
        "per_tier": per_tier,
        "done": len(folded & tiers.keys()),
        "total": len(tiers),
        "hours_done": sum(v["hours_done"] for v in per_tier.values()),
        "hours_left": total_left,
        "phase_one": {
            "done": sum(per_tier[t]["done"] for t in PHASE_ONE_TIERS),
            "total": sum(per_tier[t]["total"] for t in PHASE_ONE_TIERS),
            "hours_left": phase_one_left,
        },
    }


PROBE = """
pdb=%(pdb)s
have=/tmp/pc_have.$$
ls "$pdb" 2>/dev/null | sed 's/\\.pdb$//' | sort -u > "$have"
total=0
done=0
for f in %(fastas)s; do
  n=$(grep -c '^>' "$f" 2>/dev/null)
  [ -z "$n" ] && n=0
  d=$(grep '^>' "$f" 2>/dev/null | cut -c2- | cut -d' ' -f1 | sort -u | comm -12 - "$have" | wc -l)
  total=$((total + n))
  done=$((done + d))
done
recent=$(find "$pdb" -name '*.pdb' -newermt '-1 hour' 2>/dev/null | wc -l)
gpu=$(nvidia-smi --query-gpu=name,utilization.gpu --format=csv,noheader,nounits 2>/dev/null | head -1)
up=$(docker ps --format '{{.Names}}' 2>/dev/null | tr '\\n' ',')
rm -f "$have"
echo "total=$total"
echo "done=$done"
echo "recent=$recent"
echo "gpu=$gpu"
echo "up=$up"
"""


def parse_machine(spec: str) -> dict:
    """`name|host|window|fasta,fasta|pdb dir` -> the fields the page needs.

    The share each machine was given is fixed when the work is split, so the page reads that
    split from the command line rather than inferring it. A machine's progress is then just
    how much of its own list it has written.
    """
    parts = spec.split("|")
    if len(parts) != 5:
        raise ValueError(
            f"a machine reads name|host|window|fastas|pdb, not {spec!r}"
        )
    name, host, window, fastas, pdb = parts
    return {
        "name": name.strip(),
        "host": host.strip(),
        "window": window.strip(),
        "fastas": [part.strip() for part in fastas.split(",") if part.strip()],
        "pdb": pdb.strip(),
    }


def probe_machine(machine: dict, timeout: float = 90.0) -> dict:
    """Ask one machine how far its share has got. A machine that cannot answer says so."""
    script = PROBE % {
        "pdb": shlex.quote(machine["pdb"]),
        "fastas": " ".join(shlex.quote(path) for path in machine["fastas"]),
    }
    status = dict(machine, reachable=False, total=0, done=0, recent=0, gpu="", running=False)

    try:
        finished = subprocess.run(
            [
                "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
                "-o", "ServerAliveInterval=5",
                machine["host"], "bash -s",
            ],
            input=script, capture_output=True, text=True, timeout=timeout,
        )
    except (subprocess.SubprocessError, OSError):
        return status

    if finished.returncode != 0:
        return status

    status["reachable"] = True
    for line in finished.stdout.splitlines():
        key, _, value = line.strip().partition("=")
        if key in ("total", "done", "recent"):
            status[key] = int(value) if value.isdigit() else 0
        elif key == "gpu":
            status["gpu"] = value.strip()
        elif key == "up":
            # The batch runner is the container that means work is happening. The prediction
            # service sits loaded and idle between batches, so its presence says nothing.
            status["running"] = "runner" in value

    return status


def short_gpu(label: str) -> str:
    """`NVIDIA GeForce RTX 5060 Laptop GPU, 100` -> `RTX 5060 Laptop GPU`.

    The vendor prefix and the utilisation are said once each elsewhere; the card only needs
    enough to identify the hardware.
    """
    name = label.rsplit(",", 1)[0].strip()
    for prefix in ("NVIDIA GeForce ", "NVIDIA "):
        if name.startswith(prefix):
            return name[len(prefix):]
    return name


def render_machines(machines: list[dict]) -> str:
    """One card per machine: what it was given, how much of it is done, whether it is awake."""
    if not machines:
        return ""

    cards = []
    for machine in machines:
        share = machine["done"] / machine["total"] if machine["total"] else 0.0
        colour = "var(--teal)" if machine["running"] else "var(--faint)"
        state = "运行中" if machine["running"] else "已停"
        state_class = "on" if machine["running"] else "off"

        if not machine["reachable"]:
            state, state_class, colour = "失联", "off", "var(--faint)"
            foot_left = "无法连接"
            foot_right = ""
        else:
            foot_left = f'{machine["done"]:,} / {machine["total"]:,} 条 · {share * 100:.1f}%'
            foot_right = f'近一小时 {machine["recent"]:,} 条'

        subtitles = [machine["window"]]
        if machine["gpu"]:
            subtitles.append(short_gpu(machine["gpu"]))

        cards.append(
            f"""<div class="machine">
      <div class="machine-head">
        <span class="machine-name">{machine["name"]}</span>
        <span class="state {state_class}">{state}</span>
      </div>
      <div class="machine-sub">{" · ".join(subtitles)}</div>
      <div class="track thin"><div class="fill thin" style="width:{share * 100:.2f}%;background:{colour}"></div></div>
      <div class="machine-foot"><span>{foot_left}</span><span>{foot_right}</span></div>
    </div>"""
        )

    return f"""  <h2>两台机器</h2>
  <div class="machines">
    {"".join(cards)}
  </div>
"""


def bar(fraction: float, colour: str, minimum: int = 0) -> str:
    width = max(fraction * 100, 0.0)
    floor = f"min-width:{minimum}px;" if minimum and width < 100 else ""
    return (
        f'<div class="track"><div class="fill" '
        f'style="width:{width:.2f}%;{floor}background:{colour}"></div></div>'
    )


def card(label: str, value: str, note: str) -> str:
    return (
        f'<div class="metric"><div class="metric-label">{label}</div>'
        f'<div class="metric-value">{value}</div>'
        f'<div class="metric-note">{note}</div></div>'
    )


def render(stats: dict, published: int, generated: datetime, machines: list[dict] | None = None,
           hours_per_day: float = 24.0) -> str:
    machines = machines or []
    per_tier = stats["per_tier"]
    count_share = stats["done"] / stats["total"] if stats["total"] else 0.0
    total_hours = stats["hours_done"] + stats["hours_left"]
    clock_share = stats["hours_done"] / total_hours if total_hours else 0.0

    phase_one = stats["phase_one"]
    phase_one_share = phase_one["done"] / phase_one["total"] if phase_one["total"] else 0.0
    tier3 = per_tier[3]
    tier3_share = tier3["done"] / tier3["total"] if tier3["total"] else 0.0

    phase_one_days = phase_one["hours_left"] / hours_per_day
    total_days = stats["hours_left"] / hours_per_day
    phase_one_date = generated + timedelta(days=phase_one_days)
    total_date = generated + timedelta(days=total_days)
    machine_panel = render_machines(machines)

    def num(value: int) -> str:
        return f"{value:,}"

    def day(moment: datetime) -> str:
        return f"{moment.month} 月 {moment.day} 日"

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>结构预测进度</title>
<style>
:root {{
  --bg:#ffffff; --surface:#f4f3ef; --text:#1b1b19; --muted:#6b6b66;
  --faint:#99988f; --line:rgba(0,0,0,.13);
  --teal:#1D9E75; --blue:#378ADD; --coral:#D85A30;
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --bg:#151518; --surface:#212127; --text:#f1f0ec; --muted:#a5a49d;
    --faint:#7b7a74; --line:rgba(255,255,255,.14);
    --teal:#5DCAA5; --blue:#85B7EB; --coral:#F0997B;
  }}
}}
* {{ box-sizing:border-box; }}
body {{
  margin:0; background:var(--bg); color:var(--text);
  font-family:system-ui,-apple-system,"Helvetica Neue","PingFang SC","Microsoft YaHei",sans-serif;
  font-size:14px; line-height:1.6; -webkit-font-smoothing:antialiased;
}}
main {{ max-width:760px; margin:0 auto; padding:40px 24px 56px; }}
h1 {{ font-size:17px; font-weight:500; margin:0 0 4px; }}
.stamp {{ font-size:12px; color:var(--faint); margin:0 0 32px; }}
h2 {{ font-size:14px; font-weight:500; margin:32px 0 12px; }}
.metrics {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(148px,1fr)); gap:12px; }}
.metric {{ background:var(--surface); border-radius:8px; padding:14px 16px; }}
.metric-label {{ font-size:13px; color:var(--muted); margin-bottom:6px; }}
.metric-value {{ font-size:24px; font-weight:500; line-height:1.2; letter-spacing:-.01em; }}
.metric-note {{ font-size:12px; color:var(--faint); margin-top:4px; }}
.row {{ margin-bottom:18px; }}
.row-head {{ display:flex; justify-content:space-between; gap:16px; font-size:13px; margin-bottom:7px; }}
.row-head .value {{ color:var(--muted); white-space:nowrap; }}
.track {{ height:10px; background:var(--surface); border-radius:5px; overflow:hidden; }}
.fill {{ height:100%; border-radius:5px; }}
.track.thin {{ height:8px; border-radius:4px; }}
.fill.thin {{ border-radius:4px; }}
.note {{ font-size:13px; color:var(--muted); margin:0 0 18px; }}
.phase {{ border:0.5px solid var(--line); border-radius:10px; padding:16px 18px; margin-bottom:12px; }}
.phase-head {{ display:flex; justify-content:space-between; align-items:baseline; gap:16px; margin-bottom:12px; }}
.phase-title {{ font-size:13px; font-weight:500; }}
.phase-date {{ font-size:12px; color:var(--muted); white-space:nowrap; }}
.phase-meta {{ display:flex; gap:28px; font-size:12px; color:var(--muted); margin-top:12px; }}
.machines {{ display:grid; gap:10px; }}
.machine {{ border:0.5px solid var(--line); border-radius:10px; padding:15px 18px; }}
.machine-head {{ display:flex; justify-content:space-between; align-items:baseline; gap:16px; }}
.machine-name {{ font-size:13px; font-weight:500; }}
.machine-sub {{ font-size:12px; color:var(--faint); margin:2px 0 11px; }}
.machine-foot {{ display:flex; justify-content:space-between; gap:16px; font-size:12px; color:var(--muted); margin-top:8px; }}
.state {{ font-size:11px; padding:1px 7px; border-radius:9px; white-space:nowrap; }}
.state.on {{ color:var(--teal); background:rgba(29,158,117,.12); }}
.state.off {{ color:var(--faint); background:rgba(0,0,0,.055); }}
@media (prefers-color-scheme: dark) {{
  .state.off {{ background:rgba(255,255,255,.08); }}
}}
footer {{ margin-top:32px; font-size:12px; color:var(--faint); line-height:1.7; }}
</style>
</head>
<body>
<main>
  <h1>结构预测进度</h1>
  <p class="stamp">更新于 {generated:%Y-%m-%d %H:%M}</p>

  <div class="metrics">
    {card("已完成结构", num(stats["done"]), f'共 {num(stats["total"])} 条')}
    {card("已用机时", f'{stats["hours_done"]:.1f} 小时', f"全程约 {num(round(total_hours))} 小时")}
    {card("剩余机时", num(round(stats["hours_left"])) + " 小时", f"约 {total_days:.0f} 天")}
    {card("全部完成", day(total_date), f'{len(machines)} 台机器并行' if machines else "单机")}
  </div>

  <h2>两条进度条</h2>
  <p class="note">按条数走得像很快，按机器时间走得很慢。已完成的都是短序列，单条几秒；剩下的是长序列与长骨架，单条几十分钟。</p>

  <div class="row">
    <div class="row-head"><span>按结构条数</span><span class="value">{num(stats["done"])} / {num(stats["total"])} · {count_share * 100:.1f}%</span></div>
    {bar(count_share, "var(--teal)")}
  </div>

  <div class="row">
    <div class="row-head"><span>按实际机时</span><span class="value">{stats["hours_done"]:.1f} / {num(round(total_hours))} 小时 · {clock_share * 100:.1f}%</span></div>
    {bar(clock_share, "var(--coral)", minimum=3)}
  </div>

  <h2>两个阶段</h2>

  <div class="phase">
    <div class="phase-head">
      <span class="phase-title">阶段一 · 推荐与次推荐连接片段，不论长短</span>
      <span class="phase-date">{day(phase_one_date)}</span>
    </div>
    <div class="row-head" style="margin-bottom:7px">
      <span style="color:var(--muted)">{num(phase_one["done"])} / {num(phase_one["total"])} 条</span>
      <span class="value">还剩 {phase_one_days:.1f} 天</span>
    </div>
    <div class="track thin"><div class="fill thin" style="width:{phase_one_share * 100:.2f}%;background:var(--teal)"></div></div>
    <div class="phase-meta">
      <span>推荐 1 {num(per_tier[1]["done"])} / {num(per_tier[1]["total"])}</span>
      <span>推荐 2 {num(per_tier[2]["done"])} / {num(per_tier[2]["total"])}</span>
    </div>
  </div>

  <div class="phase">
    <div class="phase-head">
      <span class="phase-title">阶段二 · 其余连接片段，长度升序</span>
      <span class="phase-date">{day(total_date)}</span>
    </div>
    <div class="row-head" style="margin-bottom:7px">
      <span style="color:var(--muted)">{num(tier3["done"])} / {num(tier3["total"])} 条</span>
      <span class="value">还剩 {tier3["hours_left"] / hours_per_day:.1f} 天</span>
    </div>
    <div class="track thin"><div class="fill thin" style="width:{tier3_share * 100:.2f}%;background:var(--blue)"></div></div>
  </div>

{machine_panel}
  <footer>
    机时由实测点拟合的长度幂律估算，单条误差中位约 9%，累计预计日期随进度滚动。<br>
    云端结构桶已发布 {num(published)} 条，每半小时与本地同步一次。条数以本机为准。
  </footer>
</main>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--folds", required=True, type=Path)
    parser.add_argument("--state", type=Path, default=None)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--machine", action="append", default=[], metavar="SPEC",
                        help="name|host|window|fastas|pdb — one per folding machine, repeated. "
                             "The window is free text (\"8:00–23:00\") because it is a promise "
                             "about the room rather than something to compute from.")
    parser.add_argument("--hours-per-day", type=float, default=24.0,
                        help="machine time the batch actually gets per day; two machines "
                             "that share the work and one that only runs in the daytime "
                             "both come out as a single figure here")
    args = parser.parse_args()

    tiers = read_manifest(args.manifest)
    folded = count_folded(args.folds)
    published = count_published(args.state) if args.state else len(folded)
    machines = [probe_machine(parse_machine(spec)) for spec in args.machine]

    stats = summarise(tiers, folded)
    page = render(stats, published, datetime.now(),
                  machines=machines, hours_per_day=args.hours_per_day)
    args.out.write_text(page, encoding="utf-8")

    print(
        f"{stats['done']:,} / {stats['total']:,} folded, "
        f"{stats['hours_done']:.1f} of {stats['hours_done'] + stats['hours_left']:,.0f} hours spent, "
        f"{published:,} published -> {args.out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
