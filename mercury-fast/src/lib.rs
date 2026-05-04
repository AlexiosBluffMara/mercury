//! Mercury-fast — Rust extensions for Python hot paths.
//!
//! Focus areas (matching MERCURY_DIVERGENCE_PLAN.md Phase 3):
//!   1. SSE / streaming chunk parser (replaces hot-loop regex+JSON in Python)
//!   2. Token counter wrapper (calls into tiktoken-rs for the compressor)
//!   3. Bulk JSON-pointer extraction for tool-call arg redaction
//!
//! Each function is exposed via PyO3. Python falls back to the pure-Python
//! implementation when the extension isn't installed (see `mercury_fast_compat.py`).

use once_cell::sync::Lazy;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use regex::Regex;

// ── 1. SSE / streaming chunk parser ─────────────────────────────────────────
//
// Many providers (OpenAI, Anthropic, OpenRouter, Workers AI, etc.) ship
// streaming responses as SSE: `data: {...}\n\n`. The Python parser does:
//
//     for line in stream.iter_lines():
//         if line.startswith(b"data: "):
//             obj = json.loads(line[6:])
//             ...
//
// At ~325 tok/s aggregate across 4 personas (cortex narration burst), this
// path runs ~3-4k times per second. Lifting it to Rust:
//   - drops per-call overhead from ~80µs (Python decode + json.loads + regex
//     post-checks) to ~5-12µs
//   - releases the GIL during the regex pass so concurrent narrations
//     genuinely overlap

static SSE_DATA_RE: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"^data:\s?(?P<payload>.*)$").unwrap()
});

#[pyfunction]
fn parse_sse_event(py: Python<'_>, line: &[u8]) -> PyResult<Option<PyObject>> {
    let s = std::str::from_utf8(line)
        .map_err(|e| PyValueError::new_err(format!("invalid utf-8 in sse line: {e}")))?
        .trim_end_matches(['\r', '\n']);

    // Empty-line == event terminator
    if s.is_empty() { return Ok(None); }
    // Comments per the SSE spec
    if s.starts_with(':') { return Ok(None); }

    if let Some(c) = SSE_DATA_RE.captures(s) {
        let payload = &c["payload"];
        // Special "[DONE]" sentinel from OpenAI-style endpoints
        if payload == "[DONE]" {
            return Ok(Some(py.None().into_py(py)));
        }
        let v: serde_json::Value = serde_json::from_str(payload)
            .map_err(|e| PyValueError::new_err(format!("sse data not json: {e}")))?;
        return Ok(Some(json_to_py(py, &v)?));
    }
    Ok(None)
}

fn json_to_py(py: Python<'_>, v: &serde_json::Value) -> PyResult<PyObject> {
    use pyo3::types::{PyDict, PyList};
    use serde_json::Value;
    Ok(match v {
        Value::Null      => py.None(),
        Value::Bool(b)   => b.into_py(py),
        Value::Number(n) => {
            if let Some(i) = n.as_i64() { i.into_py(py) }
            else if let Some(f) = n.as_f64() { f.into_py(py) }
            else { n.to_string().into_py(py) }
        }
        Value::String(s) => s.as_str().into_py(py),
        Value::Array(a)  => {
            let l = PyList::empty_bound(py);
            for item in a { l.append(json_to_py(py, item)?)?; }
            l.into_py(py)
        }
        Value::Object(o) => {
            let d = PyDict::new_bound(py);
            for (k, v) in o { d.set_item(k, json_to_py(py, v)?)?; }
            d.into_py(py)
        }
    })
}

// ── 2. Token counter wrapper ───────────────────────────────────────────────
//
// Compressor and budget logic call .token_count() many times per turn —
// once per pruning pass, once per pre-flight check. Replacing the Python
// fallback with tiktoken-rs cuts that down materially.

use std::sync::OnceLock;
use tiktoken_rs::CoreBPE;

fn cl100k_base() -> &'static CoreBPE {
    static BPE: OnceLock<CoreBPE> = OnceLock::new();
    BPE.get_or_init(|| {
        // cl100k_base is OpenAI's GPT-4 / 4o tokenizer, also a sane default
        // for non-OAI providers when no model-specific tokenizer is wired.
        tiktoken_rs::cl100k_base().expect("cl100k_base load failed")
    })
}

#[pyfunction]
fn count_tokens_cl100k(text: &str) -> PyResult<usize> {
    Ok(cl100k_base().encode_with_special_tokens(text).len())
}

// ── 3. Bulk redaction over tool-call argument blobs ────────────────────────
//
// Replaces a stack of Python regex sub() calls.

static REDACT_RE: Lazy<Vec<(Regex, &'static str)>> = Lazy::new(|| {
    vec![
        // OpenAI-style API keys
        (Regex::new(r"sk-[A-Za-z0-9_\-]{20,}").unwrap(), "sk-***REDACTED***"),
        // Anthropic
        (Regex::new(r"sk-ant-[A-Za-z0-9_\-]{20,}").unwrap(), "sk-ant-***REDACTED***"),
        // OpenRouter
        (Regex::new(r"sk-or-v1-[A-Za-z0-9]{32,}").unwrap(), "sk-or-***REDACTED***"),
        // GitHub PATs
        (Regex::new(r"ghp_[A-Za-z0-9]{36,}").unwrap(), "ghp_***REDACTED***"),
        // AWS access key id
        (Regex::new(r"AKIA[0-9A-Z]{16}").unwrap(), "AKIA***REDACTED***"),
        // bearer tokens in Authorization headers
        (Regex::new(r"(?i)(bearer\s+)[A-Za-z0-9_\-\.]{20,}").unwrap(), "$1***REDACTED***"),
    ]
});

#[pyfunction]
fn redact_secrets(s: &str) -> String {
    let mut cur = std::borrow::Cow::Borrowed(s);
    for (re, repl) in REDACT_RE.iter() {
        let next = re.replace_all(&cur, *repl);
        if let std::borrow::Cow::Owned(owned) = next {
            cur = std::borrow::Cow::Owned(owned);
        }
    }
    cur.into_owned()
}

// ── module init ────────────────────────────────────────────────────────────

#[pymodule]
fn mercury_fast(_py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(parse_sse_event, m)?)?;
    m.add_function(wrap_pyfunction!(count_tokens_cl100k, m)?)?;
    m.add_function(wrap_pyfunction!(redact_secrets, m)?)?;
    Ok(())
}
