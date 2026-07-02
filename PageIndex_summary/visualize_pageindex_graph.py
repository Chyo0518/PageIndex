#!/usr/bin/env python3
"""Render a PageIndex-style nested tree as a standalone SVG graph."""

import argparse
import ast
import html
import json
from pathlib import Path


def load_tree(path):
    raw = Path(path).read_text(encoding="utf-8")
    data = ast.literal_eval(raw)
    return data if isinstance(data, list) else [data]


def children_of(node):
    return node.get("nodes") or node.get("sub_nodes") or []


def truncate(text, limit=34):
    text = " ".join(str(text or "Untitled").split())
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def flatten(nodes):
    flat = []
    edges = []

    def walk(node, depth, parent=None):
        idx = len(flat)
        flat.append(
            {
                "id": str(node.get("node_id", idx)),
                "title": str(node.get("title", "Untitled")),
                "page": node.get("page_index"),
                "summary": node.get("summary", ""),
                "prefix_summary": node.get("prefix_summary", ""),
                "depth": depth,
                "children": [],
                "x": 0,
                "y": 0,
            }
        )
        if parent is not None:
            edges.append((parent, idx))
            flat[parent]["children"].append(idx)
        for child in children_of(node):
            walk(child, depth + 1, idx)
        return idx

    for root in nodes:
        walk(root, 0)
    return flat, edges


def assign_layout(flat):
    x_gap = 260
    y_gap = 82
    margin_x = 80
    margin_y = 60
    next_leaf = 0

    def place(idx):
        nonlocal next_leaf
        node = flat[idx]
        node["x"] = margin_x + node["depth"] * x_gap
        if not node["children"]:
            node["y"] = margin_y + next_leaf * y_gap
            next_leaf += 1
            return node["y"]
        child_ys = [place(child_idx) for child_idx in node["children"]]
        node["y"] = sum(child_ys) / len(child_ys)
        return node["y"]

    roots = [i for i, node in enumerate(flat) if node["depth"] == 0]
    for root in roots:
        place(root)

    max_x = max((node["x"] for node in flat), default=0) + 260
    max_y = max((node["y"] for node in flat), default=0) + margin_y
    return max_x, max_y


def render_edge(parent, child):
    x1 = parent["x"] + 168
    y1 = parent["y"]
    x2 = child["x"] - 12
    y2 = child["y"]
    mid = (x1 + x2) / 2
    return (
        f'<path class="edge" d="M {x1:.1f} {y1:.1f} '
        f'C {mid:.1f} {y1:.1f}, {mid:.1f} {y2:.1f}, {x2:.1f} {y2:.1f}" />'
    )


def render_node(node, index):
    title = html.escape(truncate(node["title"]))
    node_id = html.escape(node["id"])
    page = node["page"]
    page_text = "" if page is None else f"p. {html.escape(str(page))}"
    color_class = f"depth-{min(node['depth'], 6)}"
    x = node["x"]
    y = node["y"]

    return f"""
<g class="graph-node {color_class}" data-index="{index}" transform="translate({x:.1f} {y:.1f})">
  <circle r="13" />
  <rect x="20" y="-27" width="148" height="54" rx="8" />
  <text class="node-title" x="32" y="-5">{title}</text>
  <text class="node-meta" x="32" y="15">id {node_id} {page_text}</text>
</g>
"""


def render_html(nodes):
    flat, edges = flatten(nodes)
    width, height = assign_layout(flat)
    edge_html = "\n".join(render_edge(flat[parent], flat[child]) for parent, child in edges)
    node_html = "\n".join(render_node(node, i) for i, node in enumerate(flat))
    root_title = nodes[0].get("title", "PageIndex Graph") if nodes else "PageIndex Graph"
    data_json = json.dumps(flat, ensure_ascii=False)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(str(root_title))} - Graph</title>
  <style>
    :root {{
      --bg: #f7f8fa;
      --panel: #ffffff;
      --ink: #17202a;
      --muted: #64748b;
      --line: #d9dee7;
      --edge: #aab4c2;
      --blue: #075fc7;
      --green: #16803a;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    header {{
      padding: 16px 22px;
      border-bottom: 1px solid var(--line);
      background: var(--panel);
    }}
    h1 {{
      margin: 0 0 10px;
      font-size: 21px;
      line-height: 1.3;
    }}
    .toolbar {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
    }}
    input, button {{
      height: 36px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      font: inherit;
    }}
    input {{
      width: min(520px, 100%);
      padding: 0 10px;
    }}
    button {{
      padding: 0 10px;
      cursor: pointer;
    }}
    button:hover {{ color: var(--blue); border-color: var(--blue); }}
    .stats {{ color: var(--muted); font-size: 14px; }}
    .layout {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) 360px;
      gap: 0;
      height: calc(100vh - 91px);
    }}
    .canvas {{
      overflow: auto;
      padding: 18px;
    }}
    .side {{
      overflow: auto;
      border-left: 1px solid var(--line);
      background: var(--panel);
      padding: 18px;
    }}
    .side h2 {{
      margin: 0 0 6px;
      font-size: 18px;
      line-height: 1.3;
    }}
    .side .meta {{
      margin-bottom: 14px;
      color: var(--muted);
      font-size: 13px;
    }}
    .field-label {{
      margin-top: 14px;
      color: var(--green);
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }}
    .text-block {{
      margin-top: 5px;
      padding: 10px;
      border-radius: 6px;
      background: #f3f4f6;
      white-space: pre-wrap;
      font-size: 13px;
      line-height: 1.45;
    }}
    svg {{
      min-width: 100%;
      background: #fff;
      border: 1px solid var(--line);
      border-radius: 8px;
    }}
    .edge {{
      fill: none;
      stroke: var(--edge);
      stroke-width: 1.6;
    }}
    .graph-node {{
      cursor: pointer;
    }}
    .graph-node circle {{
      fill: #fff;
      stroke: currentColor;
      stroke-width: 3;
    }}
    .graph-node rect {{
      fill: #fff;
      stroke: #d8dee8;
    }}
    .graph-node:hover rect,
    .graph-node.selected rect {{
      stroke: currentColor;
      stroke-width: 2;
    }}
    .node-title {{
      font-size: 13px;
      font-weight: 650;
      fill: #17202a;
    }}
    .node-meta {{
      font-size: 11px;
      fill: var(--muted);
    }}
    .depth-0 {{ color: #075fc7; }}
    .depth-1 {{ color: #16803a; }}
    .depth-2 {{ color: #b35a00; }}
    .depth-3 {{ color: #8b3fb8; }}
    .depth-4 {{ color: #b42318; }}
    .depth-5 {{ color: #0f766e; }}
    .depth-6 {{ color: #475569; }}
    .dim {{ opacity: 0.14; }}
    .match circle, .match rect {{
      stroke: #eab308;
      stroke-width: 3;
    }}
    @media (max-width: 900px) {{
      .layout {{ grid-template-columns: 1fr; height: auto; }}
      .side {{ border-left: 0; border-top: 1px solid var(--line); }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>{html.escape(str(root_title))}</h1>
    <div class="toolbar">
      <input id="search" type="search" placeholder="Search title, node_id, summary...">
      <button type="button" id="fit">Scroll to root</button>
      <span class="stats">{len(flat)} nodes · {len(edges)} edges</span>
    </div>
  </header>
  <div class="layout">
    <main class="canvas" id="canvas">
      <svg viewBox="0 0 {width:.0f} {height:.0f}" width="{width:.0f}" height="{height:.0f}" role="img">
        <g class="edges">{edge_html}</g>
        <g class="nodes">{node_html}</g>
      </svg>
    </main>
    <aside class="side" id="details">
      <h2>Select a node</h2>
      <div class="meta">Click a graph node to view its summary.</div>
    </aside>
  </div>
  <script>
    const data = {data_json};
    const graphNodes = [...document.querySelectorAll(".graph-node")];
    const details = document.getElementById("details");
    const canvas = document.getElementById("canvas");

    function escapeHtml(value) {{
      return String(value ?? "").replace(/[&<>"']/g, ch => ({{
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
      }}[ch]));
    }}

    function block(label, value) {{
      if (!value) return "";
      return `<div class="field-label">${{label}}</div><div class="text-block">${{escapeHtml(value)}}</div>`;
    }}

    function selectNode(index) {{
      graphNodes.forEach(node => node.classList.remove("selected"));
      const el = graphNodes[index];
      el.classList.add("selected");
      const item = data[index];
      const page = item.page == null ? "" : ` · page ${{escapeHtml(item.page)}}`;
      details.innerHTML = `
        <h2>${{escapeHtml(item.title)}}</h2>
        <div class="meta">id ${{escapeHtml(item.id)}} · depth ${{item.depth}}${{page}}</div>
        ${{block("Prefix summary", item.prefix_summary)}}
        ${{block("Summary", item.summary)}}
      `;
    }}

    graphNodes.forEach(node => {{
      node.addEventListener("click", () => selectNode(Number(node.dataset.index)));
    }});

    document.getElementById("search").addEventListener("input", event => {{
      const query = event.target.value.trim().toLowerCase();
      graphNodes.forEach(node => {{
        node.classList.remove("dim", "match");
      }});
      if (!query) return;
      graphNodes.forEach((node, index) => {{
        const item = data[index];
        const haystack = `${{item.id}} ${{item.title}} ${{item.summary}} ${{item.prefix_summary}}`.toLowerCase();
        const matched = haystack.includes(query);
        node.classList.toggle("match", matched);
        node.classList.toggle("dim", !matched);
      }});
    }});

    document.getElementById("fit").addEventListener("click", () => {{
      canvas.scrollTo({{ left: 0, top: 0, behavior: "smooth" }});
      selectNode(0);
    }});

    if (graphNodes.length) selectNode(0);
  </script>
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Path to PageIndex Python-literal tree file")
    parser.add_argument(
        "-o",
        "--output",
        default="pageindex_graph.html",
        help="Output HTML path",
    )
    args = parser.parse_args()

    nodes = load_tree(args.input)
    Path(args.output).write_text(render_html(nodes), encoding="utf-8")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
