#!/usr/bin/env python3
"""Render a PageIndex-style nested tree as a standalone HTML file."""

import argparse
import ast
import html
import json
from pathlib import Path


CHILD_KEYS = {"nodes", "sub_nodes"}


def load_tree(path):
    raw = Path(path).read_text(encoding="utf-8")
    return ast.literal_eval(raw)


def children_of(node):
    return node.get("nodes") or node.get("sub_nodes") or []


def count_nodes(nodes):
    total = 0
    for node in nodes:
        total += 1 + count_nodes(children_of(node))
    return total


def max_depth(nodes, depth=1):
    if not nodes:
        return depth - 1
    return max(max_depth(children_of(node), depth + 1) for node in nodes)


def non_child_fields(node):
    return {key: value for key, value in node.items() if key not in CHILD_KEYS}


def format_field_value(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2)
    if value is None:
        return "null"
    return str(value)


def render_field_block(label, value):
    return (
        f'<div class="field-label">{html.escape(label)}</div>'
        f'<div class="text-block">{html.escape(format_field_value(value))}</div>'
    )


def render_all_fields(node):
    return "".join(
        render_field_block(key, value) for key, value in non_child_fields(node).items()
    )


def render_node(node, depth=0):
    title = html.escape(str(node.get("title", "Untitled")))
    node_id = html.escape(str(node.get("node_id", "")))
    page = node.get("page_index")
    children = children_of(node)
    open_attr = " open" if depth < 2 else ""

    badges = []
    if node_id:
        badges.append(f'<span class="badge">id {node_id}</span>')
    if page is not None:
        badges.append(f'<span class="badge">page {html.escape(str(page))}</span>')
    if children:
        badges.append(f'<span class="badge">{len(children)} children</span>')

    child_html = "\n".join(render_node(child, depth + 1) for child in children)
    return f"""
<details class="node depth-{depth}"{open_attr}>
  <summary>
    <span class="title">{title}</span>
    {' '.join(badges)}
  </summary>
  <div class="node-body">
    {render_all_fields(node)}
    <div class="children">{child_html}</div>
  </div>
</details>
"""


def truncate(text, limit=34):
    text = " ".join(str(text or "Untitled").split())
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def flatten_graph(nodes):
    flat = []
    edges = []

    def walk(node, depth, parent=None):
        index = len(flat)
        flat.append(
            {
                "id": str(node.get("node_id", index)),
                "title": str(node.get("title", "Untitled")),
                "page": node.get("page_index"),
                "summary": node.get("summary", ""),
                "prefix_summary": node.get("prefix_summary", ""),
                "fields": non_child_fields(node),
                "depth": depth,
                "children": [],
                "x": 0,
                "y": 0,
            }
        )
        if parent is not None:
            edges.append((parent, index))
            flat[parent]["children"].append(index)
        for child in children_of(node):
            walk(child, depth + 1, index)

    for root in nodes:
        walk(root, 0)
    return flat, edges


def assign_graph_layout(flat):
    x_gap = 230
    y_gap = 115
    margin_x = 70
    margin_y = 70
    next_leaf = 0

    def place(index):
        nonlocal next_leaf
        node = flat[index]
        node["y"] = margin_y + node["depth"] * y_gap
        if not node["children"]:
            node["x"] = margin_x + next_leaf * x_gap
            next_leaf += 1
            return node["x"]
        child_xs = [place(child_index) for child_index in node["children"]]
        node["x"] = sum(child_xs) / len(child_xs)
        return node["x"]

    roots = [index for index, node in enumerate(flat) if node["depth"] == 0]
    for root in roots:
        place(root)

    width = max((node["x"] for node in flat), default=0) + 240
    height = max((node["y"] for node in flat), default=0) + 90
    return width, height


def render_graph_edge(parent, child):
    x1 = parent["x"] + 104
    y1 = parent["y"] + 27
    x2 = child["x"] + 104
    y2 = child["y"] - 27
    mid = (y1 + y2) / 2
    return (
        f'<path class="edge" d="M {x1:.1f} {y1:.1f} '
        f'C {x1:.1f} {mid:.1f}, {x2:.1f} {mid:.1f}, {x2:.1f} {y2:.1f}" />'
    )


def render_graph_node(node, index):
    title = html.escape(truncate(node["title"]))
    node_id = html.escape(node["id"])
    page = node["page"]
    page_text = "" if page is None else f"p. {html.escape(str(page))}"
    color_class = f"graph-depth-{min(node['depth'], 6)}"

    return f"""
<g class="graph-node {color_class}" data-index="{index}" transform="translate({node['x']:.1f} {node['y']:.1f})">
  <circle r="13" />
  <rect x="20" y="-27" width="168" height="54" rx="8" />
  <text class="node-title" x="32" y="-5">{title}</text>
  <text class="node-meta" x="32" y="15">id {node_id} {page_text}</text>
</g>
"""


def render_html(nodes):
    total = count_nodes(nodes)
    depth = max_depth(nodes)
    root_title = nodes[0].get("title", "PageIndex Tree") if nodes else "PageIndex Tree"
    tree_html = "\n".join(render_node(node) for node in nodes)
    graph_nodes, graph_edges = flatten_graph(nodes)
    graph_width, graph_height = assign_graph_layout(graph_nodes)
    graph_edge_html = "\n".join(
        render_graph_edge(graph_nodes[parent], graph_nodes[child])
        for parent, child in graph_edges
    )
    graph_node_html = "\n".join(
        render_graph_node(node, index) for index, node in enumerate(graph_nodes)
    )
    graph_data_json = json.dumps(graph_nodes, ensure_ascii=False)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(root_title)} - PageIndex Viewer</title>
  <style>
    :root {{
      --bg: #f6f7f8;
      --panel: #ffffff;
      --ink: #1f2933;
      --muted: #6b7280;
      --line: #d9dee5;
      --edge: #aab4c2;
      --blue: #075fc7;
      --green: #1f7a3a;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.45;
    }}
    header {{
      position: sticky;
      top: 0;
      z-index: 2;
      padding: 18px 28px;
      border-bottom: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.95);
      backdrop-filter: blur(8px);
    }}
    h1 {{
      margin: 0 0 10px;
      font-size: 22px;
      line-height: 1.25;
    }}
    .toolbar {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
    }}
    input {{
      width: min(520px, 100%);
      padding: 8px 10px;
      border: 1px solid var(--line);
      border-radius: 6px;
      font: inherit;
    }}
    select, button {{
      padding: 8px 10px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      font: inherit;
    }}
    button {{ cursor: pointer; }}
    button:hover {{ border-color: var(--blue); color: var(--blue); }}
    .stats {{ color: var(--muted); font-size: 14px; }}
    main.tree-view {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 24px 28px 48px;
    }}
    .view {{ display: none; }}
    .view.active {{ display: block; }}
    details.node {{
      margin: 8px 0;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
    }}
    details.node details.node {{ margin-left: 22px; }}
    summary {{
      padding: 10px 12px;
      cursor: pointer;
      user-select: none;
    }}
    .title {{ font-weight: 650; }}
    .badge {{
      display: inline-block;
      margin-left: 6px;
      padding: 1px 6px;
      border-radius: 999px;
      background: #eef2f7;
      color: var(--muted);
      font-size: 12px;
      vertical-align: 1px;
    }}
    .node-body {{
      padding: 0 12px 12px 28px;
      border-top: 1px solid #edf0f4;
    }}
    .field-label {{
      margin-top: 10px;
      color: var(--green);
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}
    .text-block {{
      max-height: 260px;
      overflow: auto;
      margin-top: 4px;
      padding: 10px;
      border-radius: 6px;
      background: #f3f4f6;
      white-space: pre-wrap;
      font-size: 13px;
    }}
    .children {{ margin-top: 8px; }}
    .dim > summary {{ opacity: 0.3; }}
    .graph-view {{
      height: calc(100vh - 96px);
    }}
    .graph-layout {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) 360px;
      height: 100%;
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
    .graph-depth-0 {{ color: #075fc7; }}
    .graph-depth-1 {{ color: #16803a; }}
    .graph-depth-2 {{ color: #b35a00; }}
    .graph-depth-3 {{ color: #8b3fb8; }}
    .graph-depth-4 {{ color: #b42318; }}
    .graph-depth-5 {{ color: #0f766e; }}
    .graph-depth-6 {{ color: #475569; }}
    .graph-node.dim {{ opacity: 0.14; }}
    .graph-node.match circle,
    .graph-node.match rect {{
      stroke: #eab308;
      stroke-width: 3;
    }}
    @media (max-width: 900px) {{
      .graph-view {{ height: auto; }}
      .graph-layout {{ grid-template-columns: 1fr; }}
      .side {{ border-left: 0; border-top: 1px solid var(--line); }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>{html.escape(root_title)}</h1>
    <div class="toolbar">
      <select id="view-mode" aria-label="View mode">
        <option value="tree">Tree view</option>
        <option value="graph">Graph view</option>
      </select>
      <input id="search" type="search" placeholder="Search title, node_id, summary...">
      <button type="button" id="expand">Expand all</button>
      <button type="button" id="collapse">Collapse all</button>
      <span class="stats">{total} nodes · max depth {depth}</span>
    </div>
  </header>
  <main id="tree-view" class="view tree-view active">{tree_html}</main>
  <section id="graph-view" class="view graph-view">
    <div class="graph-layout">
      <main class="canvas" id="canvas">
        <svg viewBox="0 0 {graph_width:.0f} {graph_height:.0f}" width="{graph_width:.0f}" height="{graph_height:.0f}" role="img">
          <g class="edges">{graph_edge_html}</g>
          <g class="nodes">{graph_node_html}</g>
        </svg>
      </main>
      <aside class="side" id="details">
        <h2>Select a node</h2>
        <div class="meta">Click a graph node to view its summary.</div>
      </aside>
    </div>
  </section>
  <script>
    const treeNodes = [...document.querySelectorAll("details.node")];
    const graphData = {graph_data_json};
    const graphNodes = [...document.querySelectorAll(".graph-node")];
    const details = document.getElementById("details");
    const viewMode = document.getElementById("view-mode");
    const expandButton = document.getElementById("expand");
    const collapseButton = document.getElementById("collapse");

    function escapeHtml(value) {{
      return String(value ?? "").replace(/[&<>"']/g, ch => ({{
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
      }}[ch]));
    }}

    function fieldValue(value) {{
      if (value === null || value === undefined) return "null";
      if (typeof value === "object") return JSON.stringify(value, null, 2);
      return String(value);
    }}

    function block(label, value) {{
      return `<div class="field-label">${{escapeHtml(label)}}</div><div class="text-block">${{escapeHtml(fieldValue(value))}}</div>`;
    }}

    function renderFields(fields) {{
      return Object.entries(fields || {{}})
        .map(([key, value]) => block(key, value))
        .join("");
    }}

    function selectGraphNode(index) {{
      graphNodes.forEach(node => node.classList.remove("selected"));
      const element = graphNodes[index];
      if (!element) return;
      element.classList.add("selected");
      const item = graphData[index];
      const page = item.page == null ? "" : ` · page ${{escapeHtml(item.page)}}`;
      details.innerHTML = `
        <h2>${{escapeHtml(item.title)}}</h2>
        <div class="meta">id ${{escapeHtml(item.id)}} · depth ${{item.depth}}${{page}}</div>
        ${{renderFields(item.fields)}}
      `;
    }}

    function applyViewMode() {{
      const isGraph = viewMode.value === "graph";
      document.getElementById("tree-view").classList.toggle("active", !isGraph);
      document.getElementById("graph-view").classList.toggle("active", isGraph);
      expandButton.disabled = isGraph;
      collapseButton.disabled = isGraph;
      if (isGraph && graphNodes.length) selectGraphNode(0);
    }}

    function applySearch(query) {{
      treeNodes.forEach(node => node.classList.remove("dim"));
      graphNodes.forEach(node => node.classList.remove("dim", "match"));
      if (!query) return;

      treeNodes.forEach(node => {{
        const matched = node.innerText.toLowerCase().includes(query);
        node.classList.toggle("dim", !matched);
        if (matched) {{
          node.open = true;
          let parent = node.parentElement.closest("details.node");
          while (parent) {{
            parent.open = true;
            parent.classList.remove("dim");
            parent = parent.parentElement.closest("details.node");
          }}
        }}
      }});

      graphNodes.forEach((node, index) => {{
        const item = graphData[index];
        const haystack = [
          item.id,
          item.title,
          item.summary,
          item.prefix_summary,
          ...Object.values(item.fields || {{}}).map(fieldValue),
        ].join(" ").toLowerCase();
        const matched = haystack.includes(query);
        node.classList.toggle("match", matched);
        node.classList.toggle("dim", !matched);
      }});
    }}

    expandButton.onclick = () => treeNodes.forEach(node => node.open = true);
    collapseButton.onclick = () => treeNodes.forEach((node, index) => node.open = index === 0);
    viewMode.addEventListener("change", applyViewMode);
    document.getElementById("search").addEventListener("input", event => {{
      applySearch(event.target.value.trim().toLowerCase());
    }});
    graphNodes.forEach(node => {{
      node.addEventListener("click", () => selectGraphNode(Number(node.dataset.index)));
    }});
    applyViewMode();
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
        default="pageindex_tree.html",
        help="Output HTML path",
    )
    args = parser.parse_args()

    data = load_tree(args.input)
    nodes = data if isinstance(data, list) else [data]
    Path(args.output).write_text(render_html(nodes), encoding="utf-8")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
