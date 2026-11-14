use serde::{Deserialize, Serialize};

pub const RESERVED: &[&str] = &[
    "graph", "return", "true", "false", "and", "or", "xor", "not", "dot", "cross", "repeat",
];

pub fn is_reserved(s: &str) -> bool {
    RESERVED.contains(&s)
}

pub fn is_identifier(s: &str) -> bool {
    let mut chars = s.chars();
    match chars.next() {
        Some(c) if c.is_alphabetic() || c == '_' => chars.all(|c| c.is_alphanumeric() || c == '_'),
        _ => false,
    }
}

pub fn snake(name: &str) -> String {
    let lower = name.to_lowercase();
    let mut res = String::new();
    let mut in_non_word = false;
    for c in lower.chars() {
        if c.is_alphanumeric() || c == '_' {
            if in_non_word && !res.is_empty() {
                res.push('_');
            }
            in_non_word = false;
            res.push(c);
        } else {
            in_non_word = true;
        }
    }
    let trimmed = res.trim_matches('_');
    let mut s = trimmed.to_string();
    if s.is_empty() || s.chars().next().unwrap().is_ascii_digit() {
        s = format!("_{}", s);
    }
    if is_reserved(&s) {
        s.push('_');
    }
    s
}

pub fn key(name: &str) -> String {
    if is_identifier(name) && !is_reserved(name) {
        name.to_string()
    } else {
        snake(name)
    }
}

pub fn name_display(n: &str) -> String {
    if is_identifier(n) && !is_reserved(n) {
        n.to_string()
    } else {
        quote(n)
    }
}

pub fn label_display(n: &str) -> String {
    if is_identifier(n) && !is_reserved(n) {
        n.to_string()
    } else {
        quote(n)
    }
}

pub fn quote(s: &str) -> String {
    format!("\"{}\"", s)
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Number {
    pub value: f64,
    pub is_int: bool,
    pub line: usize,
    pub col: usize,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct StringLit {
    pub value: String,
    pub line: usize,
    pub col: usize,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct BoolLit {
    pub value: bool,
    pub line: usize,
    pub col: usize,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Tuple {
    pub items: Vec<Expr>,
    pub line: usize,
    pub col: usize,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct Ref {
    pub name: String,
    pub line: usize,
    pub col: usize,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Member {
    pub target: Box<Expr>,
    pub socket: String,
    pub line: usize,
    pub col: usize,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Call {
    pub name: String,
    pub args: Vec<Arg>,
    pub line: usize,
    pub col: usize,
    pub outputs: Option<Vec<Param>>,
    pub single_output: bool,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Pipe {
    pub left: Box<Expr>,
    pub call: Box<Expr>,
    pub line: usize,
    pub col: usize,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct BinOp {
    pub op: String,
    pub left: Box<Expr>,
    pub right: Box<Expr>,
    pub line: usize,
    pub col: usize,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Neg {
    pub value: Box<Expr>,
    pub line: usize,
    pub col: usize,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Not {
    pub value: Box<Expr>,
    pub line: usize,
    pub col: usize,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub enum Expr {
    Number(Number),
    String(StringLit),
    Bool(BoolLit),
    Tuple(Tuple),
    Ref(Ref),
    Member(Member),
    Call(Call),
    Pipe(Pipe),
    BinOp(BinOp),
    Neg(Neg),
    Not(Not),
}

impl Expr {
    pub fn line(&self) -> usize {
        match self {
            Expr::Number(e) => e.line,
            Expr::String(e) => e.line,
            Expr::Bool(e) => e.line,
            Expr::Tuple(e) => e.line,
            Expr::Ref(e) => e.line,
            Expr::Member(e) => e.line,
            Expr::Call(e) => e.line,
            Expr::Pipe(e) => e.line,
            Expr::BinOp(e) => e.line,
            Expr::Neg(e) => e.line,
            Expr::Not(e) => e.line,
        }
    }

    pub fn col(&self) -> usize {
        match self {
            Expr::Number(e) => e.col,
            Expr::String(e) => e.col,
            Expr::Bool(e) => e.col,
            Expr::Tuple(e) => e.col,
            Expr::Ref(e) => e.col,
            Expr::Member(e) => e.col,
            Expr::Call(e) => e.col,
            Expr::Pipe(e) => e.col,
            Expr::BinOp(e) => e.col,
            Expr::Neg(e) => e.col,
            Expr::Not(e) => e.col,
        }
    }
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Arg {
    pub name: Option<String>,
    pub value: Expr,
    pub line: usize,
    pub col: usize,
    pub options: Vec<Arg>,
    pub type_decl: Option<Param>,
    pub alias: Option<String>,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Param {
    pub name: String,
    pub type_name: String,
    pub line: usize,
    pub col: usize,
    pub default: Option<Expr>,
    pub range: Option<(Option<Expr>, Option<Expr>)>,
    pub options: Vec<Arg>,
    pub alias: Option<String>,
}

impl Param {
    pub fn key(&self) -> String {
        self.alias.clone().unwrap_or_else(|| key(&self.name))
    }
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Panel {
    pub name: String,
    pub items: Vec<ParamTreeItem>,
    pub line: usize,
    pub col: usize,
    pub options: Vec<Arg>,
    pub end: usize,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[allow(clippy::large_enum_variant)]
pub enum ParamTreeItem {
    Param(Param),
    Panel(Panel),
}

pub fn flatten(items: &[ParamTreeItem]) -> Vec<Param> {
    let mut out = Vec::new();
    for item in items {
        match item {
            ParamTreeItem::Param(p) => out.push(p.clone()),
            ParamTreeItem::Panel(panel) => out.extend(flatten(&panel.items)),
        }
    }
    out
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct Look {
    pub flags: Vec<String>,
    pub line: usize,
    pub col: usize,
    pub label: Option<String>,
    pub color: Option<String>,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Record {
    pub fields: Vec<Arg>,
    pub line: usize,
    pub col: usize,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub enum ReturnValue {
    Expr(Expr),
    Record(Record),
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Return {
    pub value: ReturnValue,
    pub line: usize,
    pub col: usize,
    pub look: Option<Look>,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Frame {
    pub label: Option<String>,
    pub color: Option<String>,
    pub body: Vec<Stmt>,
    pub line: usize,
    pub col: usize,
    pub end: usize,
    pub continued: bool,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Repeat {
    pub count: Expr,
    pub states: Vec<Arg>,
    pub body: Vec<Stmt>,
    pub line: usize,
    pub col: usize,
    pub end: usize,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Closure {
    pub params: Vec<Param>,
    pub outputs: Vec<Param>,
    pub single_output: bool,
    pub body: Vec<Stmt>,
    pub line: usize,
    pub col: usize,
    pub end: usize,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Simulate {
    pub states: Vec<Arg>,
    pub body: Vec<Stmt>,
    pub line: usize,
    pub col: usize,
    pub end: usize,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Foreach {
    pub geometry: Expr,
    pub args: Vec<Arg>,
    pub body: Vec<Stmt>,
    pub line: usize,
    pub col: usize,
    pub end: usize,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub enum AssignValue {
    Expr(Expr),
    Repeat(Repeat),
    Closure(Closure),
    Simulate(Simulate),
    Foreach(Foreach),
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Assign {
    pub name: String,
    pub value: AssignValue,
    pub line: usize,
    pub col: usize,
    pub look: Option<Look>,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub enum Stmt {
    Assign(Assign),
    Return(Return),
    Frame(Frame),
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Graph {
    pub kind: String,
    pub name: String,
    pub params: Vec<Param>,
    pub outputs: Vec<Param>,
    pub single_output: bool,
    pub body: Vec<Stmt>,
    pub line: usize,
    pub col: usize,
    pub end: usize,
    pub description: Option<String>,
    pub description_line: usize,
    pub settings: Vec<Arg>,
    pub param_tree: Option<Vec<ParamTreeItem>>,
    pub output_tree: Option<Vec<ParamTreeItem>>,
}

impl Graph {
    pub fn tree(&self, side: &str) -> Vec<ParamTreeItem> {
        if side == "INPUT" {
            if let Some(ref pt) = self.param_tree {
                pt.clone()
            } else {
                self.params
                    .iter()
                    .map(|p| ParamTreeItem::Param(p.clone()))
                    .collect()
            }
        } else if let Some(ref ot) = self.output_tree {
            ot.clone()
        } else {
            self.outputs
                .iter()
                .map(|p| ParamTreeItem::Param(p.clone()))
                .collect()
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct Use {
    pub name: String,
    pub alias: Option<String>,
    pub names: Option<Vec<String>>,
    pub source: Option<String>,
    pub line: usize,
    pub col: usize,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct File {
    pub uses: Vec<Use>,
    pub graphs: Vec<Graph>,
}
