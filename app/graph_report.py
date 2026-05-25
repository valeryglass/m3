from __future__ import annotations

import argparse
import html
import json
import re
from collections import Counter
from dataclasses import dataclass
from itertools import groupby
from pathlib import Path

from app.readiness import (
    EpisodeReadiness,
    ProfileMaturity,
    StateSnapshotSummary,
    classify_episode_readiness,
    summarize_profile_maturity,
    summarize_state_snapshots,
)
from app.schemas.episode import Episode


ANNOTATION_FIELDS = (
    "trigger_annotations",
    "actor_annotations",
    "cognition_annotations",
    "emotion_annotations",
    "behavior_annotations",
)


@dataclass(frozen=True)
class EpisodeSignature:
    episode_id: str
    source: str
    triggers: tuple[str, ...]
    cognitions: tuple[str, ...]
    emotions: tuple[str, ...]
    behaviors: tuple[str, ...]
    relation_types: tuple[str, ...]


@dataclass(frozen=True)
class GraphReport:
    total_episodes: int
    graph_ready: tuple[EpisodeSignature, ...]
    readiness: tuple[EpisodeReadiness, ...]
    state_snapshots: StateSnapshotSummary
    profile_maturity: ProfileMaturity
    emotion_signatures: Counter[tuple[str, ...]]
    behavior_signatures: Counter[tuple[str, ...]]
    cognition_signatures: Counter[tuple[str, ...]]
    trigger_emotion_signatures: Counter[tuple[str, str]]
    cognition_behavior_signatures: Counter[tuple[str, str]]
    emotion_behavior_signatures: Counter[tuple[str, str]]
    relation_type_signatures: Counter[tuple[str, ...]]

    @property
    def skipped(self) -> tuple[str, ...]:
        return tuple(
            item.episode_id for item in self.readiness if not item.graph_ready
        )


def load_episodes(episode_dir: Path) -> list[Episode]:
    episodes = []
    for path in sorted(episode_dir.glob("episode-*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        episodes.append(Episode.model_validate(data))
    return episodes


def is_graph_ready(episode: Episode) -> bool:
    return classify_episode_readiness(episode).graph_ready


def build_signature(episode: Episode) -> EpisodeSignature:
    derived = episode.derived
    return EpisodeSignature(
        episode_id=episode.id,
        source=episode.source,
        triggers=_sorted_unique(item.type for item in derived.trigger_annotations),
        cognitions=_sorted_unique(item.kind for item in derived.cognition_annotations),
        emotions=_sorted_unique(item.label for item in derived.emotion_annotations),
        behaviors=_sorted_unique(item.type for item in derived.behavior_annotations),
        relation_types=_sorted_unique(item.type for item in derived.relations),
    )


def build_report(episodes: list[Episode]) -> GraphReport:
    readiness = tuple(classify_episode_readiness(episode) for episode in episodes)
    graph_ready_ids = {item.episode_id for item in readiness if item.graph_ready}
    signatures = tuple(
        build_signature(episode) for episode in episodes if episode.id in graph_ready_ids
    )

    return GraphReport(
        total_episodes=len(episodes),
        graph_ready=signatures,
        readiness=readiness,
        state_snapshots=summarize_state_snapshots(episodes),
        profile_maturity=summarize_profile_maturity(episodes, readiness),
        emotion_signatures=_count_tuple_signatures(sig.emotions for sig in signatures),
        behavior_signatures=_count_tuple_signatures(sig.behaviors for sig in signatures),
        cognition_signatures=_count_tuple_signatures(sig.cognitions for sig in signatures),
        trigger_emotion_signatures=_count_pairs(
            (trigger, emotion)
            for sig in signatures
            for trigger in sig.triggers
            for emotion in sig.emotions
        ),
        cognition_behavior_signatures=_count_pairs(
            (cognition, behavior)
            for sig in signatures
            for cognition in sig.cognitions
            for behavior in sig.behaviors
        ),
        emotion_behavior_signatures=_count_pairs(
            (emotion, behavior)
            for sig in signatures
            for emotion in sig.emotions
            for behavior in sig.behaviors
        ),
        relation_type_signatures=_count_tuple_signatures(
            sig.relation_types for sig in signatures
        ),
    )


def render_markdown(report: GraphReport, min_count: int = 2) -> str:
    skipped = tuple(item for item in report.readiness if not item.graph_ready)
    lines = [
        "# Graph Report",
        "",
        "## Summary",
        f"- episodes: {report.total_episodes}",
        f"- graph_ready: {len(report.graph_ready)}",
        f"- report_ready: {sum(1 for item in report.readiness if item.report_ready)}",
        f"- profile_eligible: {sum(1 for item in report.readiness if item.profile_eligible)}",
        f"- skipped: {len(skipped)}",
        "",
        "## State Snapshots",
        f"- total: {report.state_snapshots.total}",
        f"- complete: {report.state_snapshots.complete}",
        f"- partial: {report.state_snapshots.partial}",
        f"- average_confidence: {report.state_snapshots.average_confidence:.2f}",
        "",
        "## Profile Maturity",
        f"- quantity: {report.profile_maturity.quantity}",
        f"- diversity: {report.profile_maturity.diversity}",
        f"- recurrence: {report.profile_maturity.recurrence}",
        f"- stability: {report.profile_maturity.stability_percent}%",
        f"- coverage: {report.profile_maturity.coverage_percent}%",
        f"- freshness: {report.profile_maturity.freshness}",
        f"- confidence: {report.profile_maturity.confidence_band}",
        "",
    ]

    lines.extend(_render_counter("## Top Emotion Signatures", report.emotion_signatures, min_count))
    lines.extend(_render_counter("## Top Behavior Signatures", report.behavior_signatures, min_count))
    lines.extend(_render_counter("## Top Cognition Signatures", report.cognition_signatures, min_count))
    lines.extend(
        _render_counter(
            "## Trigger + Emotion Signatures",
            report.trigger_emotion_signatures,
            min_count,
            separator=" -> ",
        )
    )
    lines.extend(
        _render_counter(
            "## Cognition + Behavior Signatures",
            report.cognition_behavior_signatures,
            min_count,
            separator=" -> ",
        )
    )
    lines.extend(
        _render_counter(
            "## Emotion + Behavior Signatures",
            report.emotion_behavior_signatures,
            min_count,
            separator=" -> ",
        )
    )
    lines.extend(_render_counter("## Relation Type Patterns", report.relation_type_signatures, min_count))

    lines.extend(["## Per Episode"])
    for sig in sorted(report.graph_ready, key=lambda item: item.episode_id):
        lines.append(
            "- "
            + sig.episode_id
            + ": trigger="
            + _join_values(sig.triggers)
            + "; cognition="
            + _join_values(sig.cognitions)
            + "; emotion="
            + _join_values(sig.emotions)
            + "; behavior="
            + _join_values(sig.behaviors)
        )

    if skipped:
        lines.extend(["", "## Gaps", f"- not_graph_ready: {len(skipped)}"])
        for item in sorted(skipped, key=lambda value: value.episode_id)[:10]:
            reasons = ", ".join(item.gap_reasons) or "unknown"
            lines.append(f"- {item.episode_id}: {reasons}")

    return "\n".join(lines).rstrip() + "\n"


def write_markdown_reports(
    episodes: list[Episode],
    output_dir: Path,
    *,
    min_count: int = 2,
    by_source: bool = False,
) -> tuple[Path, ...]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written = [
        _write_report(
            output_dir / "all.md",
            build_report(episodes),
            min_count=min_count,
        )
    ]

    if by_source:
        for source, group in groupby(sorted(episodes, key=lambda item: item.source), key=lambda item: item.source):
            written.append(
                _write_report(
                    output_dir / f"{_safe_filename(source)}.md",
                    build_report(list(group)),
                    min_count=min_count,
                )
            )

    return tuple(written)


def render_graph_html(episodes: list[Episode]) -> str:
    graph = _build_visual_graph(episodes)
    payload = json.dumps(graph, ensure_ascii=False)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>CBT Graph</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f7f5f0;
      --ink: #1f2933;
      --muted: #667085;
      --panel: #ffffff;
      --line: #d7d0c2;
      --accent: #176b63;
      --accent-2: #b45309;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    header {{
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 16px;
      align-items: end;
      padding: 18px 22px 14px;
      border-bottom: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.82);
    }}
    h1 {{
      margin: 0;
      font-size: 22px;
      font-weight: 680;
      letter-spacing: 0;
    }}
    .summary {{
      margin-top: 6px;
      color: var(--muted);
      font-size: 13px;
    }}
    .controls {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      justify-content: end;
    }}
    label {{
      display: grid;
      gap: 4px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 560;
    }}
    select, input {{
      min-width: 160px;
      height: 34px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--ink);
      padding: 0 10px;
      font: inherit;
      font-size: 13px;
    }}
    main {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) 330px;
      min-height: calc(100vh - 78px);
    }}
    #canvas-wrap {{
      position: relative;
      overflow: hidden;
      min-height: 720px;
      background:
        linear-gradient(rgba(31, 41, 51, 0.04) 1px, transparent 1px),
        linear-gradient(90deg, rgba(31, 41, 51, 0.04) 1px, transparent 1px);
      background-size: 28px 28px;
    }}
    svg {{
      display: block;
      width: 100%;
      height: calc(100vh - 78px);
      min-height: 720px;
    }}
    aside {{
      border-left: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.76);
      padding: 18px;
      overflow: auto;
      max-height: calc(100vh - 78px);
    }}
    .side-title {{
      margin: 0 0 10px;
      font-size: 15px;
      font-weight: 680;
    }}
    .side-section {{
      margin-top: 18px;
    }}
    .metric {{
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 12px;
      padding: 8px 0;
      border-bottom: 1px solid #ece7dc;
      color: var(--muted);
      font-size: 13px;
    }}
    .metric strong {{
      color: var(--ink);
    }}
    .node {{
      cursor: pointer;
    }}
    .node circle {{
      stroke: rgba(31, 41, 51, 0.28);
      stroke-width: 1.2;
      filter: drop-shadow(0 2px 2px rgba(31, 41, 51, 0.16));
    }}
    .node text {{
      fill: var(--ink);
      font-size: 12px;
      font-weight: 620;
      text-anchor: middle;
      dominant-baseline: middle;
      pointer-events: none;
    }}
    .edge {{
      stroke: rgba(79, 88, 99, 0.46);
      stroke-width: 1.4;
      marker-end: url(#arrow);
    }}
    .edge-label {{
      fill: var(--muted);
      font-size: 11px;
      text-anchor: middle;
      pointer-events: none;
    }}
    .selected circle {{
      stroke: var(--accent-2);
      stroke-width: 3;
    }}
    .episode-list {{
      display: grid;
      gap: 8px;
      margin-top: 10px;
    }}
    .episode {{
      padding: 8px 10px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      font-size: 12px;
      line-height: 1.35;
    }}
    .episode strong {{
      display: block;
      margin-bottom: 4px;
    }}
    @media (max-width: 900px) {{
      header, main {{ grid-template-columns: 1fr; }}
      .controls {{ justify-content: start; }}
      aside {{
        max-height: none;
        border-left: 0;
        border-top: 1px solid var(--line);
      }}
      svg {{ height: 680px; }}
    }}
  </style>
</head>
<body>
  <header>
    <div>
      <h1>CBT Graph</h1>
      <div class="summary" id="summary"></div>
    </div>
    <div class="controls">
      <label>Source
        <select id="source-filter"></select>
      </label>
      <label>Edge
        <select id="edge-filter"></select>
      </label>
      <label>Min count
        <input id="min-count" type="number" min="1" value="1">
      </label>
    </div>
  </header>
  <main>
    <section id="canvas-wrap">
      <svg id="graph" role="img" aria-label="CBT graph visualization"></svg>
    </section>
    <aside>
      <h2 class="side-title">Selection</h2>
      <div id="details"></div>
    </aside>
  </main>
  <script id="graph-data" type="application/json">{html.escape(payload, quote=False)}</script>
  <script>
    const DATA = JSON.parse(document.getElementById('graph-data').textContent);
    const COLORS = {{
      trigger: '#a85524',
      cognition: '#2563a8',
      emotion: '#c24168',
      behavior: '#16805d',
      source: '#6b7280'
    }};
    const svg = document.getElementById('graph');
    const details = document.getElementById('details');
    const sourceFilter = document.getElementById('source-filter');
    const edgeFilter = document.getElementById('edge-filter');
    const minCount = document.getElementById('min-count');
    let selectedId = null;

    function option(value, label) {{
      const opt = document.createElement('option');
      opt.value = value;
      opt.textContent = label;
      return opt;
    }}

    function initControls() {{
      sourceFilter.append(option('all', 'All sources'));
      DATA.sources.forEach(src => sourceFilter.append(option(src, src)));
      edgeFilter.append(option('all', 'All edges'));
      DATA.edgeTypes.forEach(type => edgeFilter.append(option(type, type)));
      [sourceFilter, edgeFilter, minCount].forEach(el => el.addEventListener('input', draw));
    }}

    function filtered() {{
      const source = sourceFilter.value;
      const edgeType = edgeFilter.value;
      const threshold = Math.max(1, Number(minCount.value || 1));
      const nodes = new Map(DATA.nodes.map(node => [node.id, {{...node, count: 0, episodes: []}}]));
      let edges = DATA.edges.filter(edge =>
        (source === 'all' || edge.sources.includes(source)) &&
        (edgeType === 'all' || edge.type === edgeType) &&
        edge.count >= threshold
      );
      const used = new Set();
      edges.forEach(edge => {{
        used.add(edge.from);
        used.add(edge.to);
        [edge.from, edge.to].forEach(id => {{
          const node = nodes.get(id);
          if (!node) return;
          node.count += edge.count;
          edge.episodes.forEach(ep => {{
            if (!node.episodes.includes(ep)) node.episodes.push(ep);
          }});
        }});
      }});
      const visibleNodes = [...nodes.values()].filter(node => used.has(node.id));
      return {{nodes: visibleNodes, edges}};
    }}

    function draw() {{
      const {{nodes, edges}} = filtered();
      const width = svg.clientWidth || 1000;
      const height = svg.clientHeight || 720;
      svg.innerHTML = `<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="rgba(79,88,99,0.62)"></path></marker></defs>`;
      document.getElementById('summary').textContent = `${{DATA.episodes}} episodes · ${{nodes.length}} visible nodes · ${{edges.length}} visible edges`;

      const layers = ['source', 'trigger', 'cognition', 'emotion', 'behavior'];
      const byKind = new Map(layers.map(kind => [kind, []]));
      nodes.forEach(node => (byKind.get(node.kind) || byKind.get('source')).push(node));
      layers.forEach((kind, layerIndex) => {{
        const group = byKind.get(kind);
        const x = 90 + layerIndex * ((width - 180) / Math.max(1, layers.length - 1));
        group.sort((a, b) => b.count - a.count || a.label.localeCompare(b.label));
        group.forEach((node, index) => {{
          const y = 72 + index * Math.max(58, Math.min(92, (height - 140) / Math.max(1, group.length)));
          node.x = x;
          node.y = Math.min(height - 64, y);
        }});
      }});

      edges.forEach(edge => {{
        const from = nodes.find(node => node.id === edge.from);
        const to = nodes.find(node => node.id === edge.to);
        if (!from || !to) return;
        const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        line.setAttribute('class', 'edge');
        line.setAttribute('x1', from.x);
        line.setAttribute('y1', from.y);
        line.setAttribute('x2', to.x);
        line.setAttribute('y2', to.y);
        line.setAttribute('stroke-width', String(1 + Math.min(5, edge.count * 0.45)));
        svg.append(line);

        const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        label.setAttribute('class', 'edge-label');
        label.setAttribute('x', (from.x + to.x) / 2);
        label.setAttribute('y', (from.y + to.y) / 2 - 6);
        label.textContent = `${{edge.type}} · ${{edge.count}}`;
        svg.append(label);
      }});

      nodes.forEach(node => {{
        const group = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        group.setAttribute('class', 'node' + (node.id === selectedId ? ' selected' : ''));
        group.addEventListener('click', () => {{
          selectedId = node.id;
          showDetails(node, edges);
          draw();
        }});
        const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        circle.setAttribute('cx', node.x);
        circle.setAttribute('cy', node.y);
        circle.setAttribute('r', String(20 + Math.min(16, node.count)));
        circle.setAttribute('fill', COLORS[node.kind] || '#64748b');
        circle.setAttribute('fill-opacity', '0.88');
        const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        text.setAttribute('x', node.x);
        text.setAttribute('y', node.y);
        text.textContent = node.shortLabel;
        group.append(circle, text);
        svg.append(group);
      }});

      if (!selectedId || !nodes.find(node => node.id === selectedId)) {{
        showOverview(nodes, edges);
      }}
    }}

    function showOverview(nodes, edges) {{
      details.innerHTML = `<div class="metric"><span>Visible nodes</span><strong>${{nodes.length}}</strong></div><div class="metric"><span>Visible edges</span><strong>${{edges.length}}</strong></div><div class="metric"><span>Sources</span><strong>${{DATA.sources.length}}</strong></div>`;
    }}

    function showDetails(node, edges) {{
      const related = edges.filter(edge => edge.from === node.id || edge.to === node.id);
      details.innerHTML = `
        <div class="metric"><span>Node</span><strong>${{escapeHtml(node.label)}}</strong></div>
        <div class="metric"><span>Kind</span><strong>${{node.kind}}</strong></div>
        <div class="metric"><span>Edge count</span><strong>${{node.count}}</strong></div>
        <div class="side-section"><h3 class="side-title">Related Edges</h3>${{related.map(edge => `<div class="episode"><strong>${{edge.type}} · ${{edge.count}}</strong>${{escapeHtml(edge.from)}} → ${{escapeHtml(edge.to)}}</div>`).join('') || '<div class="episode">none</div>'}}</div>
        <div class="side-section"><h3 class="side-title">Episodes</h3><div class="episode-list">${{node.episodes.slice(0, 24).map(ep => `<div class="episode">${{escapeHtml(ep)}}</div>`).join('') || '<div class="episode">none</div>'}}</div></div>
      `;
    }}

    function escapeHtml(value) {{
      return String(value).replace(/[&<>"']/g, ch => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[ch]));
    }}

    initControls();
    draw();
    window.addEventListener('resize', draw);
  </script>
</body>
</html>
"""


def write_graph_html(episodes: list[Episode], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_graph_html(episodes), encoding="utf-8")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Print or write Markdown graph signature reports for episode JSON files."
    )
    parser.add_argument(
        "--episode-dir",
        default="data/episodes",
        help="Directory containing episode-*.json files.",
    )
    parser.add_argument(
        "--min-count",
        type=int,
        default=2,
        help="Minimum cluster count to show in top signature sections.",
    )
    parser.add_argument(
        "--output-dir",
        help="Directory for Markdown report files. Prints to stdout when omitted.",
    )
    parser.add_argument(
        "--by-source",
        action="store_true",
        help="When writing files, also create one report per episode source.",
    )
    parser.add_argument(
        "--html",
        action="store_true",
        help="When writing files, also create graph.html.",
    )
    args = parser.parse_args()

    episodes = load_episodes(Path(args.episode_dir))
    if args.output_dir:
        written = write_markdown_reports(
            episodes,
            Path(args.output_dir),
            min_count=args.min_count,
            by_source=args.by_source,
        )
        if args.html:
            written = written + (
                write_graph_html(episodes, Path(args.output_dir) / "graph.html"),
            )
        for path in written:
            print(path.as_posix())
    else:
        print(render_markdown(build_report(episodes), min_count=args.min_count), end="")


def _sorted_unique(values) -> tuple[str, ...]:
    return tuple(sorted({str(value) for value in values}))


def _count_tuple_signatures(signatures) -> Counter[tuple[str, ...]]:
    return Counter(tuple(signature) for signature in signatures if signature)


def _count_pairs(pairs) -> Counter[tuple[str, str]]:
    return Counter(pairs)


def _render_counter(
    title: str,
    counter: Counter,
    min_count: int,
    *,
    separator: str = " + ",
) -> list[str]:
    lines = [title]
    items = [
        (signature, count)
        for signature, count in counter.most_common()
        if count >= min_count
    ]
    if not items:
        lines.extend(["- none", ""])
        return lines
    for signature, count in items:
        lines.append(f"- {_join_values(signature, separator=separator)}: {count} episodes")
    lines.append("")
    return lines


def _join_values(values: tuple[str, ...], *, separator: str = " + ") -> str:
    return separator.join(values) if values else "none"


def _build_visual_graph(episodes: list[Episode]) -> dict[str, object]:
    nodes: dict[str, dict[str, object]] = {}
    edges: dict[tuple[str, str, str], dict[str, object]] = {}

    def ensure_node(kind: str, label: str) -> str:
        node_id = f"{kind}:{label}"
        if node_id not in nodes:
            nodes[node_id] = {
                "id": node_id,
                "kind": kind,
                "label": label,
                "shortLabel": _short_label(label),
            }
        return node_id

    def add_edge(edge_type: str, from_id: str, to_id: str, episode: Episode) -> None:
        key = (edge_type, from_id, to_id)
        if key not in edges:
            edges[key] = {
                "type": edge_type,
                "from": from_id,
                "to": to_id,
                "count": 0,
                "episodes": [],
                "sources": [],
            }
        edge = edges[key]
        edge["count"] = int(edge["count"]) + 1
        episodes_list = edge["episodes"]
        sources_list = edge["sources"]
        if episode.id not in episodes_list:
            episodes_list.append(episode.id)
        if episode.source not in sources_list:
            sources_list.append(episode.source)

    for episode in episodes:
        if not is_graph_ready(episode):
            continue
        source_id = ensure_node("source", episode.source)
        trigger_ids = [
            ensure_node("trigger", item.type)
            for item in episode.derived.trigger_annotations
        ]
        cognition_ids = [
            ensure_node("cognition", item.kind)
            for item in episode.derived.cognition_annotations
        ]
        emotion_ids = [
            ensure_node("emotion", item.label)
            for item in episode.derived.emotion_annotations
        ]
        behavior_ids = [
            ensure_node("behavior", item.type)
            for item in episode.derived.behavior_annotations
        ]

        for trigger_id in trigger_ids:
            add_edge("has_trigger", source_id, trigger_id, episode)
        for trigger_id in trigger_ids:
            for emotion_id in emotion_ids:
                add_edge("trigger_emotion", trigger_id, emotion_id, episode)
        for cognition_id in cognition_ids:
            for behavior_id in behavior_ids:
                add_edge("cognition_behavior", cognition_id, behavior_id, episode)
        for emotion_id in emotion_ids:
            for behavior_id in behavior_ids:
                add_edge("emotion_behavior", emotion_id, behavior_id, episode)

    return {
        "episodes": len(episodes),
        "nodes": list(nodes.values()),
        "edges": list(edges.values()),
        "sources": sorted({episode.source for episode in episodes}),
        "edgeTypes": sorted({str(edge["type"]) for edge in edges.values()}),
    }


def _short_label(label: str) -> str:
    if label.startswith("telegram-chat:"):
        return label.removeprefix("telegram-chat:")
    return label[:18]


def _write_report(path: Path, report: GraphReport, *, min_count: int) -> Path:
    path.write_text(render_markdown(report, min_count=min_count), encoding="utf-8")
    return path


def _safe_filename(value: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip("-._")
    return name or "unknown"


if __name__ == "__main__":
    main()
