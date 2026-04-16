#!/usr/bin/env python3
"""
Kerma Notebook
==============
A browser-based Mathcad-style interface for Kerma.

Usage:
    python notebook.py              # starts on http://localhost:8470
    python notebook.py --port 9000  # custom port

Opens a notebook in your default browser where you can write and execute
Kerma code in cells, with rich formatted output.
"""

import sys
import os
import json
import html as html_mod
import http.server
import webbrowser
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lexer import lex, LexerError
from parser import parse, ParseError
from compiler import compile_program
from vm import VM, VMError
from units import Quantity, REGISTRY, Constants, DimensionError, DIMENSIONLESS
from display import (display, format_symbolic, format_quantity, format_vec,
                     format_mat, format_number, format_unit_dim)
from linalg import Vec, Mat
from symbolic import Expr as SymExpr

UNIT_SYMS = set(REGISTRY._units.keys())
CONST_NAMES = {a for a in dir(Constants) if not a.startswith('_')}

# ─── Session ─────────────────────────────────────────────────────────────────

session_vm = None

def get_vm():
    global session_vm
    if session_vm is None:
        session_vm = VM(output_fn=lambda x: None)
    return session_vm

def reset_session():
    global session_vm
    session_vm = None


# ─── Cell execution ──────────────────────────────────────────────────────────

def execute_cell(source: str) -> dict:
    vm = get_vm()
    outputs = []

    def capture(text):
        outputs.append({'type': 'print', 'plain': text, 'html': format_html_print(text)})

    vm.output_fn = capture
    vm.output_log = []

    try:
        tokens = lex(source, UNIT_SYMS, CONST_NAMES)
        program = parse(tokens)
        code = compile_program(program)
        result = vm.execute(code)

        if result is not None:
            from ast_nodes import ExprStatement
            last = program.body[-1] if program.body else None
            if isinstance(last, ExprStatement):
                outputs.append({
                    'type': 'result',
                    'plain': display(result),
                    'html': value_to_html(result),
                })

        return {'ok': True, 'outputs': outputs}

    except (LexerError, ParseError) as e:
        return {'ok': False, 'error': str(e), 'error_type': 'syntax'}
    except (VMError, DimensionError, NameError, ValueError, TypeError) as e:
        return {'ok': False, 'error': str(e), 'error_type': 'runtime'}
    except Exception as e:
        return {'ok': False, 'error': f"{type(e).__name__}: {e}", 'error_type': 'internal'}


# ─── HTML rendering ──────────────────────────────────────────────────────────

def format_html_print(text: str) -> str:
    return f'<span class="out-print">{html_mod.escape(text)}</span>'

def value_to_html(value) -> str:
    if isinstance(value, SymExpr):
        return f'<span class="out-sym">{html_mod.escape(format_symbolic(value))}</span>'
    if isinstance(value, Mat):
        return mat_to_html(value)
    if isinstance(value, Vec):
        return vec_to_html(value)
    if isinstance(value, list):
        if all(isinstance(v, SymExpr) for v in value):
            items = ', '.join(f'<span class="out-sym">{html_mod.escape(format_symbolic(v))}</span>' for v in value)
            return f'<span class="out-list">[{items}]</span>'
        items = ', '.join(value_to_html(v) for v in value)
        return f'<span class="out-list">[{items}]</span>'
    if isinstance(value, Quantity):
        return quantity_to_html(value)
    if isinstance(value, bool):
        return f'<span class="out-bool">{value}</span>'
    if isinstance(value, (int, float)):
        return f'<span class="out-num">{format_number(value)}</span>'
    if isinstance(value, str):
        return f'<span class="out-str">&quot;{html_mod.escape(value)}&quot;</span>'
    return f'<span>{html_mod.escape(str(value))}</span>'

def quantity_to_html(q) -> str:
    u = q._best_unit()
    if u:
        dv = q.value / u.to_si
        return f'<span class="out-num">{format_number(dv)}</span>&hairsp;<span class="out-unit">{html_mod.escape(u.symbol)}</span>'
    if q.dim == DIMENSIONLESS:
        return f'<span class="out-num">{format_number(q.value)}</span>'
    dim_str = format_unit_dim(q.dim)
    return f'<span class="out-num">{format_number(q.value)}</span>&hairsp;<span class="out-unit">{html_mod.escape(dim_str)}</span>'

def vec_to_html(v) -> str:
    vals = v._display_values()
    unit = v._best_unit_str()
    items = ', '.join(f'<span class="out-num">{format_number(x)}</span>' for x in vals)
    u = f'&hairsp;<span class="out-unit">{html_mod.escape(unit)}</span>' if unit else ''
    return f'<span class="out-vec">⟨{items}⟩{u}</span>'

def mat_to_html(m) -> str:
    vals = m._display_values()
    unit = m._best_unit_str()
    rows_html = []
    for i in range(vals.shape[0]):
        cells = ''.join(f'<td>{format_number(vals[i,j])}</td>' for j in range(vals.shape[1]))
        rows_html.append(f'<tr>{cells}</tr>')
    u = f'<span class="out-unit mat-unit">{html_mod.escape(unit)}</span>' if unit else ''
    return f'<div class="out-mat-wrap"><table class="out-mat">{"".join(rows_html)}</table>{u}</div>'


# ─── HTTP handler ────────────────────────────────────────────────────────────

class NotebookHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(NOTEBOOK_HTML.encode('utf-8'))
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == '/api/execute':
            length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(length))
            result = execute_cell(body.get('source', ''))
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(result).encode('utf-8'))
        elif self.path == '/api/reset':
            reset_session()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'ok': True}).encode('utf-8'))
        else:
            self.send_error(404)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def log_message(self, format, *args):
        pass  # suppress HTTP logs


# ─── Notebook HTML ───────────────────────────────────────────────────────────

NOTEBOOK_HTML = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Kerma Notebook</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=Crimson+Pro:ital,wght@0,300;0,400;0,600;1,400&display=swap" rel="stylesheet">
<style>
:root {
  --bg: #fdfcf9; --bg2: #f7f5f0; --bg-cell: #fff; --bg-out: #faf8f4;
  --border: #e4e0d6; --border-focus: #9a8664; --border-run: #6a8f6e;
  --text: #302d28; --text2: #706b60; --text3: #a09a8e;
  --num: #1b6e4a; --unit: #8b5e2f; --sym: #5a3d8a; --err: #b33; --err-bg: #fdf0f0;
  --print-c: #3a5a3c;
  --font-code: 'IBM Plex Mono', 'Consolas', monospace;
  --font-text: 'Crimson Pro', Georgia, serif;
  --radius: 5px;
}
@media(prefers-color-scheme:dark){:root{
  --bg:#18171a; --bg2:#1e1d20; --bg-cell:#222126; --bg-out:#1c1b1f;
  --border:#3a383f; --border-focus:#b89e6c; --border-run:#7aad7e;
  --text:#dcd8cf; --text2:#8a867e; --text3:#5a5750;
  --num:#5ec49a; --unit:#d4a06a; --sym:#c4a8f0; --err:#f06; --err-bg:#2a1520;
  --print-c:#8abf8c;
}}
*{margin:0;padding:0;box-sizing:border-box}
html{font-size:15px}
body{font-family:var(--font-text);background:var(--bg);color:var(--text);min-height:100vh}

/* Header */
.hdr{text-align:center;padding:28px 0 20px;border-bottom:1px solid var(--border);margin-bottom:8px;position:relative}
.hdr h1{font-family:var(--font-code);font-size:1.3rem;font-weight:500;letter-spacing:6px;text-transform:uppercase;color:var(--text2)}
.hdr .sub{font-size:.82rem;color:var(--text3);font-style:italic;margin-top:3px}
.hdr .btns{position:absolute;right:24px;top:50%;transform:translateY(-50%);display:flex;gap:8px}
.hdr .btns button{font-family:var(--font-code);font-size:.7rem;padding:4px 10px;border:1px solid var(--border);background:var(--bg2);color:var(--text2);border-radius:3px;cursor:pointer;letter-spacing:1px;text-transform:uppercase}
.hdr .btns button:hover{border-color:var(--border-focus);color:var(--text)}

/* Notebook */
.nb{max-width:760px;margin:0 auto;padding:16px 20px 160px}

/* Cell */
.cell{margin-bottom:4px;position:relative;animation:fadeIn .2s ease}
@keyframes fadeIn{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}
.cell-n{position:absolute;left:-32px;top:10px;font-family:var(--font-code);font-size:.65rem;color:var(--text3);user-select:none;width:24px;text-align:right}
.cell-in{background:var(--bg-cell);border:1px solid var(--border);border-radius:var(--radius);overflow:hidden;transition:border-color .15s}
.cell-in:focus-within{border-color:var(--border-focus)}
.cell-in.running{border-color:var(--border-run)}
.cell-in textarea{width:100%;border:none;background:transparent;color:var(--text);font-family:var(--font-code);font-size:.85rem;line-height:1.7;padding:10px 14px;resize:none;outline:none;tab-size:4;min-height:38px;overflow:hidden}
.cell-in textarea::placeholder{color:var(--text3);font-style:italic}

/* Output */
.cell-out{padding:6px 14px 8px;font-family:var(--font-code);font-size:.85rem;line-height:1.6;min-height:0}
.cell-out:empty{display:none}
.cell-out .out-line{display:block;padding:2px 0}
.cell-out .out-print{color:var(--print-c)}
.cell-out .out-num{color:var(--num);font-weight:500}
.cell-out .out-unit{color:var(--unit)}
.cell-out .out-sym{color:var(--sym);font-weight:500}
.cell-out .out-str{color:var(--text2)}
.cell-out .out-bool{color:var(--num)}
.cell-out .out-err{color:var(--err);background:var(--err-bg);padding:4px 10px;border-radius:3px;display:inline-block;margin:2px 0}
.cell-out .out-list{color:var(--text)}
.cell-out .out-vec{color:var(--text)}

/* Matrix */
.out-mat-wrap{display:inline-flex;align-items:center;gap:6px}
.out-mat{border-collapse:collapse;display:inline-block}
.out-mat td{padding:2px 10px;text-align:right;color:var(--num);font-weight:500;font-family:var(--font-code);font-size:.82rem}
.out-mat tr:first-child td{padding-top:4px}
.out-mat tr:last-child td{padding-bottom:4px}
.out-mat{border-left:2px solid var(--text2);border-right:2px solid var(--text2);border-radius:2px;position:relative}
.out-mat::before,.out-mat::after{content:'';position:absolute;width:6px;border:2px solid var(--text2);border-radius:1px}
.out-mat::before{top:-1px;left:-2px;bottom:-1px;border-right:none}
.out-mat::after{top:-1px;right:-2px;bottom:-1px;border-left:none}
.mat-unit{color:var(--unit);font-size:.82rem;align-self:center}

/* Shortcuts hint */
.shortcuts{text-align:center;color:var(--text3);font-size:.72rem;font-family:var(--font-code);padding:12px 0;letter-spacing:.5px}
.shortcuts kbd{display:inline-block;padding:1px 5px;border:1px solid var(--border);border-radius:2px;background:var(--bg2);font-size:.68rem;margin:0 1px}

/* Scrollbar */
::-webkit-scrollbar{width:6px;height:6px}
::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}
</style>
</head>
<body>

<div class="hdr">
  <h1>Kerma</h1>
  <div class="sub">physics notebook</div>
  <div class="btns">
    <button onclick="resetSession()">Reset</button>
    <button onclick="addCell()">+ Cell</button>
  </div>
</div>

<div class="shortcuts">
  <kbd>Shift</kbd>+<kbd>Enter</kbd> run cell &nbsp;&middot;&nbsp;
  <kbd>Ctrl</kbd>+<kbd>Enter</kbd> run &amp; new cell &nbsp;&middot;&nbsp;
  <kbd>Alt</kbd>+<kbd>Enter</kbd> add cell below
</div>

<div class="nb" id="notebook"></div>

<script>
let cellCount = 0;

function createCell(prefill = '') {
  cellCount++;
  const cell = document.createElement('div');
  cell.className = 'cell';
  cell.dataset.n = cellCount;
  cell.innerHTML = `
    <span class="cell-n">${cellCount}</span>
    <div class="cell-in">
      <textarea rows="1" placeholder="Kerma expression..." spellcheck="false">${esc(prefill)}</textarea>
    </div>
    <div class="cell-out"></div>`;
  document.getElementById('notebook').appendChild(cell);

  const ta = cell.querySelector('textarea');
  ta.addEventListener('input', () => autoResize(ta));
  ta.addEventListener('keydown', e => handleKey(e, cell));
  autoResize(ta);
  ta.focus();
  return cell;
}

function addCell(prefill = '') {
  return createCell(prefill);
}

function autoResize(ta) {
  ta.style.height = 'auto';
  ta.style.height = ta.scrollHeight + 'px';
}

function esc(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function handleKey(e, cell) {
  const ta = cell.querySelector('textarea');
  // Tab → insert 4 spaces
  if (e.key === 'Tab') {
    e.preventDefault();
    const s = ta.selectionStart, end = ta.selectionEnd;
    ta.value = ta.value.substring(0, s) + '    ' + ta.value.substring(end);
    ta.selectionStart = ta.selectionEnd = s + 4;
    autoResize(ta);
    return;
  }
  // Shift+Enter → run cell
  if (e.key === 'Enter' && e.shiftKey) {
    e.preventDefault();
    runCell(cell);
    return;
  }
  // Ctrl+Enter → run and add new cell
  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
    e.preventDefault();
    runCell(cell).then(() => {
      const next = cell.nextElementSibling;
      if (next && next.classList.contains('cell')) {
        next.querySelector('textarea').focus();
      } else {
        addCell();
      }
    });
    return;
  }
  // Alt+Enter → add cell below
  if (e.key === 'Enter' && e.altKey) {
    e.preventDefault();
    const newCell = addCell();
    // Move it right after current cell
    cell.parentNode.insertBefore(newCell, cell.nextSibling);
    return;
  }
  // Enter inside textarea — auto-indent
  if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey && !e.altKey) {
    const pos = ta.selectionStart;
    const before = ta.value.substring(0, pos);
    const lastLine = before.split('\n').pop();
    const indent = lastLine.match(/^\s*/)[0];
    // Add extra indent after :
    const extra = lastLine.trimEnd().endsWith(':') ? '    ' : '';
    // Don't prevent default for plain enter — let it insert newline
    // But we do want auto-indent
    setTimeout(() => {
      const p = ta.selectionStart;
      ta.value = ta.value.substring(0, p) + indent + extra + ta.value.substring(p);
      ta.selectionStart = ta.selectionEnd = p + indent.length + extra.length;
      autoResize(ta);
    }, 0);
  }
}

async function runCell(cell) {
  const ta = cell.querySelector('textarea');
  const out = cell.querySelector('.cell-out');
  const inp = cell.querySelector('.cell-in');
  const source = ta.value.trim();
  if (!source) return;

  inp.classList.add('running');
  out.innerHTML = '';

  try {
    const resp = await fetch('/api/execute', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({source})
    });
    const data = await resp.json();

    if (data.ok) {
      let html = '';
      for (const o of data.outputs) {
        html += `<div class="out-line">${o.html}</div>`;
      }
      out.innerHTML = html;
    } else {
      out.innerHTML = `<div class="out-line"><span class="out-err">${esc(data.error)}</span></div>`;
    }
  } catch (err) {
    out.innerHTML = `<div class="out-line"><span class="out-err">Connection error: ${esc(err.message)}</span></div>`;
  }

  inp.classList.remove('running');
}

async function resetSession() {
  await fetch('/api/reset', {method: 'POST'});
  document.getElementById('notebook').innerHTML = '';
  cellCount = 0;
  addCell();
}

// Boot with example cells
function boot() {
  const examples = [
    '# Rest mass energy\nm_e * c**2 | MeV',
    '# Photon attenuation\nI0 = 1000\nmu = 0.0547\nI0 * exp(-mu * 50)',
    '# Symbolic differentiation\nx = sym("x")\nf = x**3 - 6*x**2 + 11*x\ndiff(f, x)',
  ];
  for (const ex of examples) {
    createCell(ex);
  }
  // Auto-run all example cells
  document.querySelectorAll('.cell').forEach(c => runCell(c));
}

boot();
</script>
</body>
</html>'''


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    port = 8470
    for i, arg in enumerate(sys.argv[1:]):
        if arg == '--port' and i + 2 < len(sys.argv):
            port = int(sys.argv[i + 2])

    server = http.server.HTTPServer(('127.0.0.1', port), NotebookHandler)
    url = f'http://localhost:{port}'
    print(f"\033[1;36mKerma Notebook\033[0m running at \033[4m{url}\033[0m")
    print(f"Press Ctrl+C to stop.\n")

    # Open browser after a short delay
    threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\033[90mNotebook stopped.\033[0m")
        server.server_close()


if __name__ == '__main__':
    main()
