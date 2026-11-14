use std::collections::{HashMap, HashSet};

use crate::ast::*;
use crate::errors::BnError;
use crate::lexer::tokenize;
use crate::parser::parse;
use crate::tokens::TokenKind;

const INDENT: &str = "  ";
const WIDTH: usize = 100;

fn char_len(s: &str) -> usize {
    s.chars().count()
}

fn precedence(op: &str) -> usize {
    match op {
        "|>" => 1,
        "or" | "xor" => 2,
        "and" => 3,
        "not" => 4,
        "<" | "<=" | ">" | ">=" | "==" | "!=" => 5,
        "+" | "-" => 6,
        "*" | "/" | "⋅" | "×" => 7,
        _ => 0,
    }
}

pub fn format_source(source: &str, filename: &str) -> Result<String, BnError> {
    let file = parse(source, filename)?;
    let rows: Vec<&str> = source.split('\n').collect();

    let all_tokens = tokenize(source, filename, false)?;
    let comments: Vec<_> = all_tokens
        .into_iter()
        .filter(|t| t.kind == TokenKind::Comment)
        .collect();

    let mut alone = HashSet::new();
    for c in &comments {
        if c.line <= rows.len() {
            let row = rows[c.line - 1];
            let prefix: String = row.chars().take(c.col - 1).collect();
            if prefix.trim().is_empty() {
                alone.insert(c.line);
            }
        }
    }

    let mut printed: Vec<(usize, String, bool)> = Vec::new();

    fn walk(
        statements: &[Stmt],
        pad: &str,
        alone: &HashSet<usize>,
        printed: &mut Vec<(usize, String, bool)>,
    ) {
        for s in statements {
            match s {
                Stmt::Frame(f) => {
                    let has_alone = alone.iter().any(|&n| f.line < n && n < f.end);
                    if !f.body.is_empty() || has_alone {
                        printed.push((f.line, format!("{}{}", pad, frame_head(f)), true));
                        let inner_pad = format!("{}{}", pad, INDENT);
                        walk(&f.body, &inner_pad, alone, printed);
                        printed.push((f.end, format!("{}}}", pad), false));
                    } else {
                        let lines = format_statement(s, pad);
                        for (k, (o, t)) in lines.into_iter().enumerate() {
                            printed.push((o, t, k == 0));
                        }
                    }
                }
                Stmt::Assign(a) => match &a.value {
                    AssignValue::Repeat(_)
                    | AssignValue::Closure(_)
                    | AssignValue::Simulate(_)
                    | AssignValue::Foreach(_) => {
                        let head_lines = zone_head(&a.name, &a.value, pad, a.line);
                        for (k, (o, t)) in head_lines.into_iter().enumerate() {
                            printed.push((o, t, k == 0));
                        }
                        let inner_body = match &a.value {
                            AssignValue::Repeat(r) => &r.body,
                            AssignValue::Closure(c) => &c.body,
                            AssignValue::Simulate(s) => &s.body,
                            AssignValue::Foreach(f) => &f.body,
                            _ => unreachable!(),
                        };
                        let end = match &a.value {
                            AssignValue::Repeat(r) => r.end,
                            AssignValue::Closure(c) => c.end,
                            AssignValue::Simulate(s) => s.end,
                            AssignValue::Foreach(f) => f.end,
                            _ => unreachable!(),
                        };
                        let inner_pad = format!("{}{}", pad, INDENT);
                        walk(inner_body, &inner_pad, alone, printed);
                        printed.push((end, format!("{}}}", pad), false));
                    }
                    AssignValue::Expr(_) => {
                        let lines = format_statement(s, pad);
                        for (k, (o, t)) in lines.into_iter().enumerate() {
                            printed.push((o, t, k == 0));
                        }
                    }
                },
                Stmt::Return(_) => {
                    let lines = format_statement(s, pad);
                    for (k, (o, t)) in lines.into_iter().enumerate() {
                        printed.push((o, t, k == 0));
                    }
                }
            }
        }
    }

    // Sorted uses
    let sorted = sorted_uses(&file.uses);
    for u in &sorted {
        let lines = format_use(u);
        for (k, (o, t)) in lines.into_iter().enumerate() {
            printed.push((o, t, k == 0));
        }
    }
    if !file.uses.is_empty() {
        let max_line = file.uses.iter().map(|u| u.line).max().unwrap_or(1);
        printed.push((max_line, String::new(), false));
    }

    for (i, g) in file.graphs.iter().enumerate() {
        if i > 0 {
            printed.push((file.graphs[i - 1].end, String::new(), false));
        }
        let head_lines = format_header(g);
        for (k, (o, t)) in head_lines.into_iter().enumerate() {
            printed.push((o, t, k == 0));
        }
        if let Some(ref desc) = g.description {
            printed.push((
                g.description_line,
                format!("{}{}", INDENT, quote(desc)),
                true,
            ));
        }
        walk(&g.body, INDENT, &alone, &mut printed);
        printed.push((g.end, "}".to_string(), false));
    }

    let mut own = Vec::new();
    let mut trailing: HashMap<usize, Vec<String>> = HashMap::new();

    for c in &comments {
        let text = c.text.trim_end().to_string();
        if !alone.contains(&c.line) {
            let on: Vec<usize> = printed
                .iter()
                .enumerate()
                .filter(|(_, (o, t, _))| *o == c.line && !t.is_empty())
                .map(|(k, _)| k)
                .collect();
            let at = if !on.is_empty() {
                *on.last().unwrap()
            } else {
                let candidates: Vec<usize> = printed
                    .iter()
                    .enumerate()
                    .filter(|(_, (o, t, _))| *o <= c.line && !t.is_empty())
                    .map(|(k, _)| k)
                    .collect();
                if candidates.is_empty() {
                    0
                } else {
                    *candidates.last().unwrap()
                }
            };
            trailing.entry(at).or_default().push(text);
        } else {
            own.push((c.line, text));
        }
    }

    let mut out: Vec<String> = Vec::new();

    let blank_fn = |line: usize| -> bool {
        1 <= line && line <= rows.len() && rows[line - 1].trim().is_empty()
    };

    let mut emit = |origin: usize, text: String, starts: bool| {
        if starts
            && !out.is_empty()
            && !out.last().unwrap().is_empty()
            && !out.last().unwrap().ends_with('{')
            && blank_fn(origin - 1)
        {
            out.push(String::new());
        }
        out.push(text);
    };

    let mut j = 0;
    for (k, (origin, text, starts)) in printed.into_iter().enumerate() {
        while j < own.len() && own[j].0 < origin {
            let (line, comment) = &own[j];
            emit(*line, format!("{}{}", indent(&text), comment), true);
            j += 1;
        }
        let line_text = if let Some(tr) = trailing.get(&k) {
            let mut parts = vec![text];
            parts.extend(tr.clone());
            parts.join("  ")
        } else {
            text
        };
        emit(origin, line_text, starts);
    }

    while j < own.len() {
        let (line, comment) = &own[j];
        emit(*line, comment.clone(), true);
        j += 1;
    }

    let mut result = out.join("\n");
    result.push('\n');
    Ok(result)
}

fn indent(text: &str) -> String {
    let stripped = text.trim_start();
    let pad_len = text.len() - stripped.len();
    let pad = &text[..pad_len];
    if stripped == "}" {
        format!("{}{}", pad, INDENT)
    } else {
        pad.to_string()
    }
}

pub fn format_file(file: &File) -> String {
    let mut parts = Vec::new();
    let head = sorted_uses(&file.uses)
        .iter()
        .flat_map(format_use)
        .map(|(_, t)| format!("{}\n", t))
        .collect::<String>();
    if !head.is_empty() {
        parts.push(head);
    }
    let graphs = file
        .graphs
        .iter()
        .map(|g| {
            let mut lines = format_header(g);
            if let Some(ref desc) = g.description {
                lines.push((g.description_line, format!("{}{}", INDENT, quote(desc))));
            }
            for s in &g.body {
                lines.extend(format_statement(s, INDENT));
            }
            lines.push((g.end, "}".to_string()));
            lines
                .into_iter()
                .map(|(_, t)| format!("{}\n", t))
                .collect::<String>()
        })
        .collect::<Vec<_>>()
        .join("\n");
    parts.push(graphs);
    parts.join("\n")
}

fn sorted_uses(uses: &[Use]) -> Vec<Use> {
    let mut out = uses.to_vec();
    out.sort_by(|a, b| {
        a.name.cmp(&b.name).then_with(|| {
            a.source
                .as_deref()
                .unwrap_or("")
                .cmp(b.source.as_deref().unwrap_or(""))
        })
    });
    out
}

fn format_use(u: &Use) -> Vec<(usize, String)> {
    let tail = if let Some(ref src) = u.source {
        format!(" from {}", quote(src))
    } else {
        String::new()
    };
    let alias_str = if let Some(ref alias) = u.alias {
        format!(" as {}", alias)
    } else {
        String::new()
    };
    let names_str = if let Some(ref names) = u.names {
        format!(" ({})", names.join(", "))
    } else {
        String::new()
    };
    let line = format!("use {}{}{}{}", u.name, alias_str, names_str, tail);
    if char_len(&line) <= WIDTH || u.names.is_none() {
        return vec![(u.line, line)];
    }
    let mut lines = vec![(u.line, format!("use {}{} (", u.name, alias_str))];
    if let Some(ref names) = u.names {
        for n in names {
            lines.push((u.line, format!("{}{},", INDENT, n)));
        }
    }
    lines.push((u.line, format!("){}", tail)));
    lines
}

fn format_header(g: &Graph) -> Vec<(usize, String)> {
    let lead_settings = if !g.settings.is_empty() {
        format!("({})", format_args(&g.settings))
    } else {
        String::new()
    };
    let lead = format!("{}{lead_settings} graph {}", g.kind, name_display(&g.name));
    let params: Vec<String> = g.params.iter().map(format_param).collect();
    let outputs = if g.single_output {
        g.outputs[0].type_name.clone()
    } else {
        format!(
            "({})",
            g.outputs
                .iter()
                .map(format_param)
                .collect::<Vec<_>>()
                .join(", ")
        )
    };
    let head = format!("{lead}({}) -> {} {{", params.join(", "), outputs);
    let paneled = (g.param_tree.is_some(), g.output_tree.is_some());
    if char_len(&head) <= WIDTH && !paneled.0 && !paneled.1 {
        return vec![(g.line, head)];
    }

    let mut lines = Vec::new();
    if !params.is_empty() || paneled.0 {
        let ins = g.tree("INPUT");
        let ins_last = last_line(&ins);
        lines.push((g.line, format!("{lead}(")));
        lines.extend(one_per_line(&ins, &format!("{}{}", INDENT, INDENT)));
        lines.push((ins_last, format!(") -> {} {{", outputs)));
    } else {
        lines.push((g.line, format!("{lead}() -> {} {{", outputs)));
    }

    if (char_len(&lines.last().unwrap().1) <= WIDTH && !paneled.1) || g.single_output {
        return lines;
    }

    let close = if lines.len() > 1 {
        ") -> (".to_string()
    } else {
        format!("{lead}() -> (")
    };
    let outs = g.tree("OUTPUT");
    let outs_last = last_line(&outs);
    let last_idx = lines.len() - 1;
    lines[last_idx].1 = close;
    lines.extend(one_per_line(&outs, &format!("{}{}", INDENT, INDENT)));
    lines.push((outs_last, ") {".to_string()));
    lines
}

fn one_per_line(items: &[ParamTreeItem], pad: &str) -> Vec<(usize, String)> {
    let mut lines = Vec::new();
    for i in items {
        match i {
            ParamTreeItem::Panel(p) => {
                let opt_str = if p.options.is_empty() {
                    String::new()
                } else {
                    format!("({})", format_args(&p.options))
                };
                let head = format!("{}{}{} {{", pad, quote(&p.name), opt_str);
                if p.items.is_empty() {
                    lines.push((p.line, format!("{}}},", head)));
                    continue;
                }
                lines.push((p.line, head));
                let inner_pad = format!("{}{}{}", pad, INDENT, INDENT);
                lines.extend(one_per_line(&p.items, &inner_pad));
                lines.push((p.end, format!("{}}},", pad)));
            }
            ParamTreeItem::Param(p) => {
                lines.push((p.line, format!("{}{},", pad, format_param(p))));
            }
        }
    }
    if let Some(last) = lines.last_mut() {
        last.1.pop(); // remove trailing comma
    }
    lines
}

fn last_line(items: &[ParamTreeItem]) -> usize {
    if let Some(last) = items.last() {
        match last {
            ParamTreeItem::Panel(p) => p.end,
            ParamTreeItem::Param(p) => p.line,
        }
    } else {
        0
    }
}

pub fn format_param(p: &Param) -> String {
    let mut text = name_display(&p.name);
    if let Some(ref alias) = p.alias {
        text.push_str(&format!(" as {}", alias));
    }
    text.push_str(&format!(": {}", p.type_name));
    if !p.options.is_empty() {
        text.push_str(&format!("({})", format_args(&p.options)));
    }
    if let Some(ref default) = p.default {
        text.push_str(&format!(" = {}", format_expr(default, 0)));
    }
    if let Some(ref range) = p.range {
        let lo = range
            .0
            .as_ref()
            .map(|b| format_expr(b, 0))
            .unwrap_or_default();
        let hi = range
            .1
            .as_ref()
            .map(|b| format_expr(b, 0))
            .unwrap_or_default();
        text.push_str(&format!(" in {}..{}", lo, hi));
    }
    text
}

pub fn format_statement(s: &Stmt, pad: &str) -> Vec<(usize, String)> {
    match s {
        Stmt::Frame(f) => {
            let head = frame_head(f);
            if f.body.is_empty() {
                return vec![(f.line, format!("{}{}}}", pad, head))];
            }
            let mut lines = vec![(f.line, format!("{}{}", pad, head))];
            let inner_pad = format!("{}{}", pad, INDENT);
            for inner in &f.body {
                lines.extend(format_statement(inner, &inner_pad));
            }
            lines.push((f.end, format!("{}}}", pad)));
            lines
        }
        Stmt::Assign(a) => match &a.value {
            AssignValue::Repeat(_)
            | AssignValue::Closure(_)
            | AssignValue::Simulate(_)
            | AssignValue::Foreach(_) => {
                let mut lines = zone_head(&a.name, &a.value, pad, a.line);
                let inner_body = match &a.value {
                    AssignValue::Repeat(r) => &r.body,
                    AssignValue::Closure(c) => &c.body,
                    AssignValue::Simulate(s) => &s.body,
                    AssignValue::Foreach(f) => &f.body,
                    _ => unreachable!(),
                };
                let end = match &a.value {
                    AssignValue::Repeat(r) => r.end,
                    AssignValue::Closure(c) => c.end,
                    AssignValue::Simulate(s) => s.end,
                    AssignValue::Foreach(f) => f.end,
                    _ => unreachable!(),
                };
                let inner_pad = format!("{}{}", pad, INDENT);
                for inner in inner_body {
                    lines.extend(format_statement(inner, &inner_pad));
                }
                lines.push((end, format!("{}}}", pad)));
                lines
            }
            AssignValue::Expr(e) => {
                let lead = format!("{}{} = ", pad, a.name);
                looked(block(&lead, e, a.line, pad), a.look.as_ref())
            }
        },
        Stmt::Return(r) => match &r.value {
            ReturnValue::Record(rec) => {
                let line = format!("{}return ({})", pad, format_args(&rec.fields));
                if char_len(&line) <= WIDTH {
                    looked(vec![(r.line, line)], r.look.as_ref())
                } else {
                    let lead = format!("{}return (", pad);
                    looked(spread(&lead, &rec.fields, r.line, pad), r.look.as_ref())
                }
            }
            ReturnValue::Expr(e) => {
                let lead = format!("{}return ", pad);
                looked(block(&lead, e, r.line, pad), r.look.as_ref())
            }
        },
    }
}

fn looked(mut lines: Vec<(usize, String)>, look: Option<&Look>) -> Vec<(usize, String)> {
    if let Some(l) = look {
        if let Some(last) = lines.last_mut() {
            last.1 = format!("{} {}", last.1, look_text(l));
        }
    }
    lines
}

fn look_text(look: &Look) -> String {
    let mut parts = vec!["@".to_string()];
    if let Some(ref label) = look.label {
        parts.push(quote(label));
    }
    if let Some(ref color) = look.color {
        parts.push(color.clone());
    }
    for f in &look.flags {
        parts.push(f.clone());
    }
    parts.join(" ")
}

fn zone_head(name: &str, z: &AssignValue, pad: &str, _assign_line: usize) -> Vec<(usize, String)> {
    match z {
        AssignValue::Closure(c) => closure_head(name, c, pad),
        AssignValue::Repeat(r) => {
            let mut items = vec![Arg {
                name: None,
                value: r.count.clone(),
                line: r.line,
                col: r.col,
                options: Vec::new(),
                type_decl: None,
                alias: None,
            }];
            items.extend(r.states.clone());
            let line = format!("{}{} = repeat({}) {{", pad, name, format_args(&items));
            if char_len(&line) <= WIDTH || items.is_empty() {
                return vec![(r.line, line)];
            }
            let mut lines = spread(&format!("{}{} = repeat(", pad, name), &items, r.line, pad);
            if let Some(last) = lines.last_mut() {
                last.1.push_str(" {");
            }
            lines
        }
        AssignValue::Simulate(s) => {
            let line = format!("{}{} = simulate({}) {{", pad, name, format_args(&s.states));
            if char_len(&line) <= WIDTH || s.states.is_empty() {
                return vec![(s.line, line)];
            }
            let mut lines = spread(
                &format!("{}{} = simulate(", pad, name),
                &s.states,
                s.line,
                pad,
            );
            if let Some(last) = lines.last_mut() {
                last.1.push_str(" {");
            }
            lines
        }
        AssignValue::Foreach(f) => {
            let mut items = vec![Arg {
                name: None,
                value: f.geometry.clone(),
                line: f.line,
                col: f.col,
                options: Vec::new(),
                type_decl: None,
                alias: None,
            }];
            items.extend(f.args.clone());
            let line = format!("{}{} = foreach({}) {{", pad, name, format_args(&items));
            if char_len(&line) <= WIDTH || items.is_empty() {
                return vec![(f.line, line)];
            }
            let mut lines = spread(&format!("{}{} = foreach(", pad, name), &items, f.line, pad);
            if let Some(last) = lines.last_mut() {
                last.1.push_str(" {");
            }
            lines
        }
        AssignValue::Expr(_) => unreachable!(),
    }
}

fn closure_head(name: &str, c: &Closure, pad: &str) -> Vec<(usize, String)> {
    let outs = signature_outputs(&c.outputs, c.single_output);
    let params_str = c
        .params
        .iter()
        .map(format_param)
        .collect::<Vec<_>>()
        .join(", ");
    let line = format!("{}{} = closure({}) -> {} {{", pad, name, params_str, outs);
    if char_len(&line) <= WIDTH || c.params.is_empty() {
        return vec![(c.line, line)];
    }
    let mut lines = vec![(c.line, format!("{}{} = closure(", pad, name))];
    for p in &c.params {
        lines.push((p.line, format!("{}{}{},", pad, INDENT, format_param(p))));
    }
    if let Some(last) = lines.last_mut() {
        last.1.pop(); // remove comma
    }
    lines.push((
        c.params.last().map(|p| p.line).unwrap_or(c.line),
        format!("{}) -> {} {{", pad, outs),
    ));
    lines
}

fn signature_outputs(outputs: &[Param], single: bool) -> String {
    if single {
        outputs[0].type_name.clone()
    } else {
        format!(
            "({})",
            outputs
                .iter()
                .map(format_param)
                .collect::<Vec<_>>()
                .join(", ")
        )
    }
}

fn frame_head(f: &Frame) -> String {
    let mut parts = Vec::new();
    if let Some(ref label) = f.label {
        parts.push(quote(label));
    }
    if f.continued {
        parts.push("..".to_string());
    } else if let Some(ref color) = f.color {
        parts.push(color.clone());
    }
    let mut s = String::new();
    for p in parts {
        s.push_str(&p);
        s.push(' ');
    }
    s.push('{');
    s
}

fn block(lead: &str, e: &Expr, origin: usize, pad: &str) -> Vec<(usize, String)> {
    if let Expr::Pipe(_) = e {
        let mut pipes = Vec::new();
        let mut cur = e;
        while let Expr::Pipe(p) = cur {
            pipes.push(p);
            cur = p.left.as_ref();
        }
        pipes.reverse();
        let first = pipes[0];
        let rest = &pipes[1..];
        let mut lines = vec![(
            origin,
            format!(
                "{}{} |> {}",
                lead,
                format_expr(cur, 0),
                format_expr(&first.call, 0)
            ),
        )];
        for p in rest {
            lines.push((
                p.line,
                format!("{}{}|> {}", pad, INDENT, format_expr(&p.call, 0)),
            ));
        }
        return lines;
    }
    let line = format!("{}{}", lead, format_expr(e, 0));
    if char_len(&line) > WIDTH {
        if let Expr::Call(ref c) = e {
            if !c.args.is_empty() {
                let mut lines = spread(&format!("{}{}(", lead, c.name), &c.args, origin, pad);
                if let Some(ref outs) = c.outputs {
                    if let Some(last) = lines.last_mut() {
                        last.1
                            .push_str(&format!(" -> {}", signature_outputs(outs, c.single_output)));
                    }
                }
                return lines;
            }
        }
    }
    vec![(origin, line)]
}

fn spread(head: &str, items: &[Arg], origin: usize, pad: &str) -> Vec<(usize, String)> {
    let mut lines = Vec::new();
    for a in items {
        lines.push((a.line, format!("{}{}{},", pad, INDENT, format_arg(a))));
    }
    if let Some(last) = lines.last_mut() {
        last.1.pop(); // remove comma
        last.1.push(')');
    }
    let mut out = vec![(origin, head.to_string())];
    out.extend(lines);
    out
}

pub fn format_args(items: &[Arg]) -> String {
    items.iter().map(format_arg).collect::<Vec<_>>().join(", ")
}

pub fn format_arg(a: &Arg) -> String {
    if let Some(ref name) = a.name {
        let mut options = String::new();
        if let Some(ref alias) = a.alias {
            options.push_str(&format!(" as {}", alias));
        }
        if !a.options.is_empty() {
            options.push_str(&format!("({})", format_args(&a.options)));
        }
        if let Some(ref type_decl) = a.type_decl {
            format!(
                "{}{}: {} = {}",
                label_display(name),
                options,
                type_decl.type_name,
                format_expr(&a.value, 0)
            )
        } else {
            format!(
                "{}{}: {}",
                label_display(name),
                options,
                format_expr(&a.value, 0)
            )
        }
    } else {
        format_expr(&a.value, 0)
    }
}

pub fn format_expr(e: &Expr, outer: usize) -> String {
    match e {
        Expr::Number(num) => {
            if num.is_int {
                format!("{}", num.value as i64)
            } else {
                let mut s = format!("{}", num.value);
                if !s.contains('.') && !s.contains('e') && !s.contains('E') {
                    s.push_str(".0");
                }
                s
            }
        }
        Expr::String(s) => quote(&s.value),
        Expr::Bool(b) => {
            if b.value {
                "true".to_string()
            } else {
                "false".to_string()
            }
        }
        Expr::Tuple(t) => {
            format!(
                "({})",
                t.items
                    .iter()
                    .map(|i| format_expr(i, 0))
                    .collect::<Vec<_>>()
                    .join(", ")
            )
        }
        Expr::Ref(r) => r.name.clone(),
        Expr::Member(m) => {
            format!("{}.{}", format_expr(&m.target, 9), label_display(&m.socket))
        }
        Expr::Call(c) => {
            if let Some(ref outs) = c.outputs {
                let text = format!(
                    "{}({}) -> {}",
                    c.name,
                    format_args(&c.args),
                    signature_outputs(outs, c.single_output)
                );
                if outer >= 9 {
                    format!("({})", text)
                } else {
                    text
                }
            } else {
                format!("{}({})", c.name, format_args(&c.args))
            }
        }
        Expr::Neg(neg) => {
            let text = format!("-{}", format_expr(&neg.value, 9));
            if outer > 8 {
                format!("({})", text)
            } else {
                text
            }
        }
        Expr::Not(not) => {
            let p = precedence("not");
            let text = format!("not {}", format_expr(&not.value, p));
            if outer > p {
                format!("({})", text)
            } else {
                text
            }
        }
        Expr::BinOp(b) => {
            let p = precedence(&b.op);
            let mixed = match b.left.as_ref() {
                Expr::BinOp(left_bin) => {
                    left_bin.op != b.op
                        && (["⋅", "×", "xor"].contains(&b.op.as_str())
                            || ["⋅", "×", "xor"].contains(&left_bin.op.as_str()))
                }
                _ => false,
            };
            let left_outer = if p == precedence("==") || mixed {
                p + 1
            } else {
                p
            };
            let left_str = format_expr(&b.left, left_outer);
            let right_str = format_expr(&b.right, p + 1);
            let text = format!("{} {} {}", left_str, b.op, right_str);
            if p < outer {
                format!("({})", text)
            } else {
                text
            }
        }
        Expr::Pipe(p) => {
            let prec = precedence("|>");
            let left_str = format_expr(&p.left, prec);
            let right_str = format_expr(&p.call, prec + 1);
            let text = format!("{} |> {}", left_str, right_str);
            if prec < outer {
                format!("({})", text)
            } else {
                text
            }
        }
    }
}
