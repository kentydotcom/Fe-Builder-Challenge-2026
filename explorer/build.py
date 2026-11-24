#!/usr/bin/env python3
"""Generate the Checkable Coordinator Judge Tour explorer from the project tree."""
from __future__ import annotations

import html
import re
import shutil
import zipfile
from pathlib import Path

import markdown

# Repo root is the parent of this explorer/ directory.
ROOT = Path(__file__).resolve().parent.parent
SITE = Path(__file__).resolve().parent / "public"
TREE = SITE / "tree"
ZIP_NAME = "fe-fl-judge-tour.zip"

SOURCE_FILES = [
    "README.md",
    "SUBMISSION.md",
    "WALKTHROUGH.md",
    "RECONSTRUCTION.md",
    "LICENSE",
    "fe.toml",
    ".gitignore",
    "scripts/e2e.sh",
    "scripts/anvil_tour.sh",
    "src/lib.fe",
    "src/ledger.fe",
    "src/agg.fe",
    "src/slash.fe",
    "src/agent.fe",
    "src/events.fe",
    "src/errors.fe",
    "src/tests.fe",
]

GROUPS = [
    ("Root", [p for p in SOURCE_FILES if "/" not in p]),
    ("Scripts", [p for p in SOURCE_FILES if p.startswith("scripts/")]),
    ("Source", [p for p in SOURCE_FILES if p.startswith("src/")]),
]




_svg_seq = 0


def inline_svg(rel: str) -> str:
    global _svg_seq
    _svg_seq += 1
    text = (SITE / rel).read_text(encoding="utf-8")
    if text.startswith("<?xml"):
        text = text.split("?>", 1)[-1].strip()
    prefix = Path(rel).stem.replace("-", "_") + f"_{_svg_seq}_"
    text = re.sub(r'\bid="([^"]+)"', lambda m: f'id="{prefix}{m.group(1)}"', text)
    text = re.sub(r'url\(#([^)]+)\)', lambda m: f'url(#{prefix}{m.group(1)})', text)
    text = re.sub(r'\bhref="#([^"]+)"', lambda m: f'href="#{prefix}{m.group(1)}"', text)
    text = re.sub(r'\bxlink:href="#([^"]+)"', lambda m: f'xlink:href="#{prefix}{m.group(1)}"', text)
    return text


def figure(rel: str) -> str:
    return f'<figure class="diagram">{inline_svg(rel)}</figure>'


def step_icon(name: str) -> str:
    return f'<span class="step-icon" aria-hidden="true">{inline_svg(f"assets/icons/{name}.svg")}</span>'


def sb_frame(num: int, title: str, rel: str, kind: str) -> str:
    return f"""<figure class="sb-frame">
  <div class="sb-head"><span class="sb-num">{num}</span><p class="sb-title">{html.escape(title)}</p></div>
  {inline_svg(rel)}
</figure>"""


def sb_board() -> str:
    pain = [
        (1, "Clients train a shared model. Raw data stays put.", "assets/diagrams/sb-01.svg"),
        (2, "One middleman publishes an average nobody can check.", "assets/diagrams/sb-02.svg"),
        (3, "No receipt. Poison skews it. A false charge is free.", "assets/diagrams/sb-03.svg"),
    ]
    fix = [
        (4, "Each client stakes a hash receipt. Updates stay off-chain.", "assets/diagrams/sb-04.svg"),
        (5, "Anyone checks the average against those receipts.", "assets/diagrams/sb-05.svg"),
        (6, "Bond a charge, slash the outlier, revise the average.", "assets/diagrams/sb-06.svg"),
    ]
    pain_html = "\n".join(sb_frame(*row, "pain") for row in pain)
    fix_html = "\n".join(sb_frame(*row, "fix") for row in fix)
    return f"""<div class="storyboard" aria-label="A federated-learning round, before and after">
  <div class="sb-act sb-pain">
    <p class="kicker">Today</p>
    <div class="sb-row">
      {pain_html}
    </div>
  </div>
  <div class="sb-act sb-fix">
    <p class="kicker">What this coordinator does</p>
    <div class="sb-row">
      {fix_html}
    </div>
  </div>
</div>"""


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def excerpt(path: str, start: int, end: int) -> str:
    lines = read(path).splitlines()
    chunk = lines[start - 1 : end]
    return "\n".join(chunk)


def excerpt_block(path: str, start: int, end: int, title: str | None = None) -> str:
    code = html.escape(excerpt(path, start, end))
    label = html.escape(f"{path}:{start}–{end}")
    cap = html.escape(title) if title else label
    lang = "fe" if path.endswith(".fe") else "plain"
    return f"""
<figure class="excerpt">
  <header>
    <span class="path">{cap}</span>
    <a href="#source/{html.escape(path)}" data-open-source="{html.escape(path)}">Open in Source</a>
  </header>
  <pre data-lang="{lang}" data-start="{start}"><code>{code}</code></pre>
</figure>
"""


def md_walkthrough() -> str:
    src = read("WALKTHROUGH.md")
    md = markdown.Markdown(
        extensions=["fenced_code", "tables", "sane_lists", "toc"],
        extension_configs={"toc": {"permalink": False}},
    )
    return md.convert(src)


def copy_tree() -> None:
    if TREE.exists():
        shutil.rmtree(TREE)
    TREE.mkdir(parents=True)
    for rel in SOURCE_FILES:
        dest = TREE / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, dest)


def write_zip() -> None:
    zpath = SITE / ZIP_NAME
    if zpath.exists():
        zpath.unlink()
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in SOURCE_FILES:
            zf.write(ROOT / rel, arcname=f"fe-fl-judge-tour/{rel}")


def source_nav() -> str:
    parts = ['<nav class="source-nav" id="source-list" aria-label="Source files">']
    for group, files in GROUPS:
        parts.append(f'<div class="group">{html.escape(group)}</div>')
        for f in files:
            parts.append(
                f'<button type="button" data-path="{html.escape(f)}">{html.escape(f)}</button>'
            )
    parts.append("</nav>")
    return "\n".join(parts)



STAGES = [
    ("1", "toolchain", "Fe 26.5.0 and Foundry on PATH", "fe"),
    ("2", "build", "fe build --out-dir out", "source"),
    ("3", "unit", "pure FedAvg, hash, and slash tests", "hash"),
    ("4", "chapter 1", "register, open round, submit receipts", "receipt"),
    ("5", "chapter 2", "FedAvg attestation", "attest"),
    ("6", "chapter 3", "poison vote, slash, revise", "slash"),
    ("7", "tour", "in-EVM tour plus Anvil deployment", "anvil"),
    ("8", "teardown", "stop leftover Anvil; keep logs", "teardown"),
]


def stage_deck() -> str:
    cards = []
    for n, ident, title, icon in STAGES:
        cmd = f"./scripts/e2e.sh --stage {n}"
        cards.append(
            f"""<article class="stage-card">
  <div class="stage-card-head">{step_icon(icon)}<span class="stage-num">{html.escape(n)}</span><h3>{html.escape(ident)}</h3></div>
  <p class="stage-title">{html.escape(title)}</p>
  <div class="actions">
    <button type="button" class="btn" data-stage="{html.escape(n)}">Run stage {html.escape(n)}</button>
    <button type="button" class="btn secondary" data-copy="{html.escape(cmd)}">Copy command</button>
  </div>
</article>"""
        )
    return f"""<div class="stage-deck" id="stage-deck">
  <div class="actions">
    <button type="button" class="btn" data-run-all>Run all 8 stages</button>
    <button type="button" class="btn secondary" data-copy="./scripts/e2e.sh --ci">Copy --ci command</button>
  </div>
  <div class="stage-grid">
    {"".join(cards)}
  </div>
  <div class="stage-console" id="stage-console" hidden>
    <header>
      <span class="path" id="stage-meta">Recorded log</span>
      <span class="stage-pill">Recorded PASS</span>
    </header>
    <pre><code id="stage-log"></code></pre>
  </div>
</div>"""


def page() -> str:
    wt = md_walkthrough()
    files_js = ", ".join(f'"{f}"' for f in SOURCE_FILES)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="theme-color" content="#120e0c">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-title" content="Coordinator">
  <meta name="robots" content="noindex, nofollow">
  <title>Checkable Coordinator — Judge Tour</title>
  <link rel="icon" href="assets/brand/checkable-coordinator-mark.svg" type="image/svg+xml">
  <link rel="apple-touch-icon" href="assets/brand/apple-touch-icon.png">
  <link rel="manifest" href="manifest.webmanifest">
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <a class="skip" href="#panel-overview">Skip to content</a>
  <div class="haze" aria-hidden="true"></div>
  <header class="site-header">
    <div class="header-inner">
      <a class="brand" href="#overview"><img class="brand-mark" src="assets/brand/checkable-coordinator-mark.svg" alt="Checkable Coordinator">Checkable Coordinator <span>Judge Tour</span></a>
      <p class="header-meta meta">Judge Tour explorer · Fe 26.5.0</p>
    </div>
    <div class="tabs-wrap">
    <div class="tabs" role="tablist" aria-label="Tour chapters">
      <button type="button" role="tab" id="tab-overview" data-tab="overview" aria-controls="panel-overview" aria-selected="true">Overview</button>
      <button type="button" role="tab" id="tab-problem" data-tab="problem" aria-controls="panel-problem" aria-selected="false">Problem</button>
      <button type="button" role="tab" id="tab-receipts" data-tab="receipts" aria-controls="panel-receipts" aria-selected="false">Receipts</button>
      <button type="button" role="tab" id="tab-fedavg" data-tab="fedavg" aria-controls="panel-fedavg" aria-selected="false">FedAvg attest</button>
      <button type="button" role="tab" id="tab-slash" data-tab="slash" aria-controls="panel-slash" aria-selected="false">Poison / slash</button>
      <button type="button" role="tab" id="tab-run" data-tab="run" aria-controls="panel-run" aria-selected="false">Run the tour</button>
      <button type="button" role="tab" id="tab-walkthrough" data-tab="walkthrough" aria-controls="panel-walkthrough" aria-selected="false">Walkthrough</button>
      <button type="button" role="tab" id="tab-source" data-tab="source" aria-controls="panel-source" aria-selected="false">Source</button>
    </div>
    <div class="tabs-fade" aria-hidden="true"></div>
    </div>
  </header>

  <main>
    <section class="panel active" role="tabpanel" id="panel-overview" aria-labelledby="tab-overview">
      <p class="kicker">Fe Builders Challenge prototype</p>
      <h1>Hash receipts, a checkable FedAvg, and a bonded slash</h1>
      {figure("assets/diagrams/overview-round.svg")}
      <ol class="steps">
        <li>{step_icon("receipt")}<div><strong>Receipts.</strong> Stake, then file <code>keccak256</code> of the update plus its L1 norm. The vector stays off-chain.</div></li>
        <li>{step_icon("attest")}<div><strong>FedAvg attest.</strong> Anyone opens the vectors in calldata. The contract checks each hash and stores the average. No aggregator key.</div></li>
        <li>{step_icon("slash")}<div><strong>Poison vote.</strong> Bond, vote, slash an outlier, then revise. A false charge costs the accuser.</div></li>
      </ol>
      <ul class="summary">
        <li>Protocol in Fe 26.5.0 (<code>3dab95f</code>), ingot <code>fl_coord</code> 0.1.0.</li>
        <li>Bash and Foundry only drive the judge tour.</li>
        <li>No model training, no GPU, no mainnet deploy.</li>
        <li>MIT License, Copyright 2026 Kent G Lau, PhD.</li>
        <li>Source: <a href="https://github.com/kentydotcom/Fe-Builder-Challenge-2026">github.com/kentydotcom/Fe-Builder-Challenge-2026</a>.</li>
      </ul>

      <h2>This tree is preparatory, not a judged-window protocol delta</h2>
      <ul class="summary">
        <li>Written 28 October 2026, before the 3–24 November 2026 window.</li>
        <li>No new Fe protocol features after that scaffold.</li>
        <li>Reconstructed 11 November 2026 from cloud agent <code>bc-12e4d95b-18fd-5153-9343-4b92563a04ed</code>.</li>
        <li>See <a href="#source/RECONSTRUCTION.md" data-open-source="RECONSTRUCTION.md">RECONSTRUCTION.md</a>.</li>
      </ul>

      <div class="callout ok">
        <p class="kicker">Documented results</p>
        <ul class="summary">
          <li>24 November 2026 (Asia/Hong_Kong): <code>fe test --jobs 1</code> was <strong>20 passed, 0 failed</strong>; <code>./scripts/e2e.sh --ci</code> was <strong>8 stages passed, 0 failed</strong>, teardown last. Fe 26.5.0, Foundry 1.8.4.</li>
          <li>28 October and 11 November 2026: 20/20 and 7/7, before teardown was stage 8.</li>
        </ul>
      </div>

      <h2>Fe types keep stake and gradients from mixing</h2>
      {excerpt_block("src/lib.fe", 127, 139, "src/lib.fe — FlRegistry effects")}
      <ul class="summary">
        <li>Stake is <code>Wei</code>; a coordinate is <code>i64</code>; those types do not add.</li>
        <li>Handlers name the effects they use. <code>Ledger</code> cannot log or send ETH unless the handler passes <code>log</code> and <code>call</code>.</li>
      </ul>

      <h2>What this is not</h2>
      <ul class="summary">
        <li>Fe 26.x is not production-ready.</li>
        <li>This is a demo with tests, not a system to deploy with real money.</li>
        <li>No mainnet or testnet deploy.</li>
        <li>Four-client cap; the L1 norm is public, so this is not private FL.</li>
        <li>Integer FedAvg toward zero; outlier bound of 20.</li>
        <li>No proof-of-deletion, escrow, hashmirror, lineage, vertical FL, or agent-tool payments.</li>
        <li>Full notes: <a href="#source/README.md" data-open-source="README.md">README.md</a>. New to Fe? Use the <a href="#walkthrough">Walkthrough</a> tab.</li>
      </ul>
    </section>

    <section class="panel wide" role="tabpanel" id="panel-problem" aria-labelledby="tab-problem" hidden>
      <div class="measure">
        <p class="kicker">Why this coordinator exists</p>
        <h1>A trusted middleman, then a checkable coordinator</h1>
      </div>
      {sb_board()}
      <div class="measure">
        <h2>In short</h2>
        <ul class="summary">
          <li>Clients train a shared model; raw data stays with them.</li>
          <li>Today, one middleman publishes an average nobody can check.</li>
          <li>There is no receipt, poison can skew the average, and a false charge is free.</li>
          <li>Here, each client stakes a hash receipt; updates stay off-chain.</li>
          <li>Anyone can check the average against those receipts.</li>
          <li>A bonded charge can slash an outlier and revise the average; a false charge costs the accuser.</li>
          <li>The demo uses four <code>i64</code> coordinates as a stand-in, not private FL.</li>
          <li>The L1 score is stored in the clear; the client cap is four; Fe 26.x is not production-ready.</li>
        </ul>
      </div>
    </section>

    <section class="panel" role="tabpanel" id="panel-receipts" aria-labelledby="tab-receipts" hidden>
      <p class="kicker">Chapter 1</p>
      <h1>The update stays off-chain; storage keeps only the hash and the L1 score</h1>
      {figure("assets/diagrams/receipts-flow.svg")}
      <div class="table-wrap">
        <table>
          <thead><tr><th>Client</th><th>Vector</th><th>L1 score</th><th>Role</th></tr></thead>
          <tbody>
            <tr><td>A</td><td><code>(1, 2, 3, 4)</code></td><td>10</td><td>honest</td></tr>
            <tr><td>B</td><td><code>(2, 2, 3, 4)</code></td><td>11</td><td>honest</td></tr>
            <tr><td>C</td><td><code>(1, 1, 3, 5)</code></td><td>10</td><td>honest</td></tr>
            <tr><td>D</td><td><code>(40, 40, 40, 40)</code></td><td>160</td><td>outlier</td></tr>
          </tbody>
        </table>
      </div>
      <ul class="summary">
        <li>Register with stake, open round <code>7</code>, then each client submits a hash and a score.</li>
        <li>A second submit reverts with <code>AlreadySubmitted</code>; a stake below <code>min_stake</code> reverts with <code>StakeTooSmall</code>.</li>
        <li>The public-key commitment is a <code>u256</code>, not a name or other personal data.</li>
        <li>Tests: <code>test_stage1_register_open_submit</code>, <code>test_stage1_low_stake</code>, <code>test_stage1_double_submit</code>.</li>
      </ul>

      <h2>Keccak-256 commits to domain, round, client, score, and coordinates</h2>
      {excerpt_block("src/agg.fe", 11, 83, "src/agg.fe — hash_update and l1")}
      <ul class="summary">
        <li>Changing any committed field changes the hash.</li>
        <li>The L1 norm is the only numeric statistic stored beside the hash.</li>
      </ul>

      <h2>The ledger stores clients, receipts, and the round — not the vectors</h2>
      {excerpt_block("src/ledger.fe", 19, 42, "src/ledger.fe — Phase, Client, Receipt")}
      {excerpt_block("src/ledger.fe", 168, 218, "src/ledger.fe — register, open_round, submit")}
      {excerpt_block("src/lib.fe", 18, 27, "src/lib.fe — Register, OpenRound, SubmitReceipt")}
      {excerpt_block("src/lib.fe", 134, 152, "src/lib.fe — recv arms for receipts")}
    </section>

    <section class="panel" role="tabpanel" id="panel-fedavg" aria-labelledby="tab-fedavg" hidden>
      <p class="kicker">Chapter 2</p>
      <h1>Anyone opens the vectors; the contract attests the average — no trusted aggregator</h1>
      {figure("assets/diagrams/fedavg-attest.svg")}
      <ul class="summary">
        <li>Anyone calls <code>attest</code> with the four vectors in calldata. They are not written into the maps.</li>
        <li>For each client the contract recomputes the L1 and the hash. A mismatch reverts (<code>ScoreMismatch</code> or <code>HashMismatch</code>).</li>
        <li>It then stores <code>sum_commitment</code>, <code>avg_commitment</code>, <code>set_commitment</code>, and <code>median_score</code>.</li>
        <li>Integer FedAvg of all four clients is <code>(11, 11, 12, 13)</code>; without D it is <code>(1, 1, 3, 4)</code>. Division truncates toward zero.</li>
        <li>Lower median of <code>[10, 10, 11, 160]</code> is <code>10</code>. Bound <code>20</code>, so only D is an outlier.</li>
        <li><code>previewAverage</code> is a pure view so the shell can ask the chain for the commitment.</li>
        <li>Tests: <code>test_stage2_attest_fedavg</code>, <code>test_stage2_bad_opening</code>.</li>
      </ul>

      <h2>Integer FedAvg, median, and the participant set</h2>
      {excerpt_block("src/agg.fe", 33, 47, "src/agg.fe — Commitment trait")}
      {excerpt_block("src/agg.fe", 118, 160, "src/agg.fe — integer fedavg")}
      {excerpt_block("src/agg.fe", 181, 203, "src/agg.fe — median, outlier, participant set")}
      {excerpt_block("src/ledger.fe", 220, 240, "src/ledger.fe — Ledger::attest")}
      {excerpt_block("src/lib.fe", 28, 37, "src/lib.fe — Attest message")}
      {excerpt_block("src/lib.fe", 154, 163, "src/lib.fe — Attest handler")}
    </section>

    <section class="panel" role="tabpanel" id="panel-slash" aria-labelledby="tab-slash" hidden>
      <p class="kicker">Chapter 3</p>
      <h1>A bonded vote can slash an outlier and revise the average</h1>
      {figure("assets/diagrams/poison-slash.svg")}
      <ol class="steps">
        <li>{step_icon("bond")}<div>After attestation, client A posts <code>bond</code> and accuses D.</div></li>
        <li>{step_icon("check")}<div>Client B posts <code>vote_bond</code> in support.</div></li>
        <li>{step_icon("slash")}<div>Anyone calls <code>resolve</code>.</div></li>
        <li>{step_icon("poison")}<div>D is an outlier and support beats oppose, so the verdict is <strong>upheld</strong> (code <code>1</code>). D is slashed; half to A, half to <code>treasury</code>. D's receipt is marked <code>poisoned</code>.</div></li>
        <li>{step_icon("revise")}<div><code>revise</code> opens only A, B, and C. The new average is the honest FedAvg. The round becomes <code>Settled</code>.</div></li>
      </ol>
      <ul class="summary">
        <li><strong>False accusation</strong> (code <code>2</code>): accusing B (score <code>11</code>) fails the outlier check. A's bond is slashed — half to B, half to treasury. B's stake is untouched.</li>
        <li><strong>Failed quorum</strong> (code <code>3</code>): accusing D with no votes. A's bond is returned. D is not slashed.</li>
        <li>Bonds are <code>Wei</code>, so a gradient cannot be added to a stake. Vote bonds are always returned.</li>
        <li>Payouts use <code>call.send_value</code> after storage updates; a failed transfer reverts the resolution.</li>
        <li>Tests: <code>test_stage3_upheld_slash_and_revise</code>, <code>test_stage3_false_accusation</code>, <code>test_stage3_failed_quorum</code>, <code>test_stage3_self_accusation</code>, <code>test_tour_judge_full</code>.</li>
        <li>The full-tour test checks the contract ETH balance after payouts (3750 wei with the small test stakes).</li>
      </ul>

      <h2>Verdict math and payouts</h2>
      {excerpt_block("src/slash.fe", 17, 90, "src/slash.fe — settle")}
      {excerpt_block("src/ledger.fe", 372, 494, "src/ledger.fe — accuse, vote, resolve")}
      {excerpt_block("src/ledger.fe", 242, 262, "src/ledger.fe — revise")}
      {excerpt_block("src/lib.fe", 175, 197, "src/lib.fe — Accuse, Vote, Resolve")}
      {excerpt_block("src/lib.fe", 296, 320, "src/lib.fe — send / send_payout")}
    </section>

    <section class="panel" role="tabpanel" id="panel-run" aria-labelledby="tab-run" hidden>
      <p class="kicker">Eight stages, teardown last</p>
      <h1>Replay the recorded tour, or run it locally with Fe 26.5.0</h1>
      {figure("assets/diagrams/run-toolchain.svg")}
      <ul class="summary">
        <li>This explorer is static. Fe and Anvil are not executed here.</li>
        <li>Each button replays the verified 24 November 2026 (Asia/Hong_Kong) log for that stage.</li>
        <li>To run it yourself: clone the repo, install Fe 26.5.0 and Foundry, then <code>./scripts/e2e.sh --ci</code> or <code>--stage N</code>.</li>
        <li>A passing run prints <code>PASS  8 stages, 0 failed</code>, with teardown last.</li>
      </ul>
      {stage_deck()}

      <h2>Install Fe 26.5.0, then Foundry, then clone</h2>
      <div class="excerpt"><header><span class="path">shell</span></header>
      <pre data-lang="bash" data-start="1"><code>curl -fsSL https://raw.githubusercontent.com/argotorg/fe/master/feup/feup.sh | bash -s -- --version v26.5.0
source ~/.fe/env
fe --version    # fe 26.5.0 (3dab95f)
curl -fsSL https://foundry.paradigm.xyz | bash
foundryup
git clone https://github.com/kentydotcom/Fe-Builder-Challenge-2026.git
cd Fe-Builder-Challenge-2026
./scripts/e2e.sh --ci</code></pre></div>
      <ul class="summary">
        <li>Install Fe 26.5.0, not “latest” if latest has moved on.</li>
        <li>Fe 26.5 targets Osaka; the script starts <code>anvil --hardfork osaka</code>.</li>
        <li>Menu item 9, or <code>--ci</code>, runs all eight stages in order. Item 8 / <code>--stage 8</code> is teardown only.</li>
        <li>Each stage writes <code>logs/e2e-&lt;timestamp&gt;/&lt;stage&gt;.log</code>. Exit 0 only if every requested stage passed.</li>
      </ul>

      <h2>Anvil is the on-chain chapter, not a second required tour</h2>
      <ul class="summary">
        <li><code>./scripts/anvil_tour.sh</code> after <code>fe build</code> is only for the chain story on its own. A <code>--ci</code> run already starts and stops Anvil.</li>
        <li>It uses Anvil's published development keys on a local node; those keys are not secret and must not be used anywhere else.</li>
        <li>On Anvil, ordinary accounts call <code>FlRegistry</code> directly. <code>Agent</code> exists only for <code>fe test</code>.</li>
      </ul>

      <div class="callout ok">
        <p class="kicker">Documented results</p>
        <ul class="summary">
          <li>24 November 2026 (Asia/Hong_Kong): <code>fe test --jobs 1</code> was <strong>20 passed, 0 failed</strong>; <code>./scripts/e2e.sh --ci</code> was <strong>8 stages passed, 0 failed</strong>, teardown last. Fe 26.5.0, Foundry 1.8.4.</li>
          <li>28 October and 11 November 2026: 20/20 and 7/7, before teardown was stage 8.</li>
        </ul>
      </div>
    </section>

    <section class="panel" role="tabpanel" id="panel-walkthrough" aria-labelledby="tab-walkthrough" hidden>
      <p class="kicker">How to read the Fe source</p>
      <h1>From types to the full tour test</h1>
      {figure("assets/diagrams/walkthrough-guide.svg")}
      <ul class="summary">
        <li>Written for someone who has never seen Fe.</li>
        <li>Follow the diagram, then the sections below.</li>
      </ul>
      <article class="walkthrough">
        {wt}
      </article>
    </section>

    <section class="panel wide" role="tabpanel" id="panel-source" aria-labelledby="tab-source" hidden>
      <p class="kicker">Project source</p>
      <h1>Read or download the explorer tree</h1>
      {figure("assets/diagrams/source-tree.svg")}
      <ul class="summary">
        <li>The public repository is <a href="https://github.com/kentydotcom/Fe-Builder-Challenge-2026">github.com/kentydotcom/Fe-Builder-Challenge-2026</a>.</li>
        <li>Download the tree as a zip if you want it offline.</li>
      </ul>
      <div class="actions">
        <a class="btn" href="{ZIP_NAME}" download>Download source zip</a>
        <a class="btn secondary" href="#source/README.md" data-open-source="README.md">Open README.md</a>
      </div>
      <div class="source-shell">
        {source_nav()}
        <div class="source-view">
          <div class="bar">
            <span class="path" id="source-path">README.md</span>
            <span class="meta" id="source-meta"></span>
          </div>
          <pre><code id="source-code"></code></pre>
        </div>
      </div>
    </section>
  </main>

  <footer>
    <div class="footer-inner">
      Checkable Coordinator (ingot <code>fl_coord</code>). MIT License, Copyright 2026 Kent G Lau, PhD. Source: <a href="https://github.com/kentydotcom/Fe-Builder-Challenge-2026">github.com/kentydotcom/Fe-Builder-Challenge-2026</a>. Exploratory Fe first written 28 October 2026.
    </div>
  </footer>

  <script>window.SOURCE_FILES = [{files_js}];</script>
  <script src="app.js"></script>
</body>
</html>
"""


def main() -> None:
    SITE.mkdir(parents=True, exist_ok=True)
    copy_tree()
    write_zip()
    html_out = page()
    (SITE / "index.html").write_text(html_out, encoding="utf-8")
    print("wrote", SITE / "index.html", "bytes", len(html_out.encode()))
    print("tree files", len(list(TREE.rglob("*"))))
    print("zip", (SITE / ZIP_NAME).stat().st_size)


if __name__ == "__main__":
    main()
