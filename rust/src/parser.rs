use crate::ast::*;
use crate::errors::BnError;
use crate::lexer::tokenize;
use crate::tokens::Token;

pub fn parse(source: &str, filename: &str) -> Result<File, BnError> {
    let tokens = tokenize(source, filename, true)?;
    let mut parser = Parser::new(&tokens, filename);
    parser.parse_file()
}

pub struct Parser<'a> {
    tokens: &'a [Token],
    filename: &'a str,
    i: usize,
}

impl<'a> Parser<'a> {
    pub fn new(tokens: &'a [Token], filename: &'a str) -> Self {
        Self {
            tokens,
            filename,
            i: 0,
        }
    }

    fn tok(&self) -> &Token {
        if self.i < self.tokens.len() {
            &self.tokens[self.i]
        } else {
            &self.tokens[self.tokens.len() - 1]
        }
    }

    fn peek(&self, offset: usize) -> &Token {
        let idx = (self.i + offset).min(self.tokens.len() - 1);
        &self.tokens[idx]
    }

    fn at(&self, kind_or_punct: &str) -> bool {
        self.tok().is(kind_or_punct)
    }

    fn at_text(&self, kind: &str, text: &str) -> bool {
        self.tok().is_with_text(kind, text)
    }

    fn advance(&mut self) -> Token {
        let t = self.tok().clone();
        if self.i < self.tokens.len() {
            self.i += 1;
        }
        t
    }

    fn accept(&mut self, kind_or_punct: &str) -> Option<Token> {
        if self.at(kind_or_punct) {
            Some(self.advance())
        } else {
            None
        }
    }

    fn accept_text(&mut self, kind: &str, text: &str) -> Option<Token> {
        if self.at_text(kind, text) {
            Some(self.advance())
        } else {
            None
        }
    }

    fn expect(&mut self, kind_or_punct: &str, what: Option<&str>) -> Result<Token, BnError> {
        if self.at(kind_or_punct) {
            Ok(self.advance())
        } else {
            let desc = what.unwrap_or(kind_or_punct);
            Err(self.fail(format!("expected {}, found {}", desc, self.tok().describe()), None))
        }
    }

    fn expect_text(&mut self, kind: &str, text: &str, what: Option<&str>) -> Result<Token, BnError> {
        if self.at_text(kind, text) {
            Ok(self.advance())
        } else {
            let desc = what.unwrap_or(text);
            Err(self.fail(format!("expected {}, found {}", desc, self.tok().describe()), None))
        }
    }

    fn fail(&self, message: impl Into<String>, tok: Option<&Token>) -> BnError {
        let t = tok.unwrap_or_else(|| self.tok());
        BnError::new(self.filename, t.line, t.col, message)
    }

    // Grammar

    pub fn parse_file(&mut self) -> Result<File, BnError> {
        let mut uses = Vec::new();
        while self.at_use() {
            uses.push(self.parse_use()?);
        }
        let mut graphs = Vec::new();
        while !self.at("EOF") {
            if self.at_use() {
                return Err(self.fail("use declarations must appear at top of file before graphs", None));
            }
            graphs.push(self.parse_graph()?);
        }
        if graphs.is_empty() {
            return Err(self.fail("empty file: no graphs found", None));
        }
        Ok(File { uses, graphs })
    }

    fn at_use(&self) -> bool {
        self.at_text("IDENT", "use") && self.peek(1).is("IDENT")
    }

    fn parse_use(&mut self) -> Result<Use, BnError> {
        let t = self.advance();
        let name_tok = self.advance();
        let mut names = None;
        if self.accept("(").is_some() {
            let mut list = Vec::new();
            while self.accept(")").is_none() {
                let g = self.expect("IDENT", Some("graph name"))?;
                list.push(g.text);
                if self.accept(",").is_none() {
                    self.expect(")", None)?;
                    break;
                }
            }
            if list.is_empty() {
                return Err(self.fail(
                    format!("empty list: write 'use {}' to import the entire module", name_tok.text),
                    Some(&t),
                ));
            }
            names = Some(list);
        }
        let mut source = None;
        if self.accept_text("IDENT", "from").is_some() {
            let s = self.expect("STRING", Some("quoted source"))?;
            source = Some(s.text);
        }
        Ok(Use {
            name: name_tok.text,
            names,
            source,
            line: t.line,
            col: t.col,
        })
    }

    fn parse_graph(&mut self) -> Result<Graph, BnError> {
        let kind = self.expect("IDENT", Some("tree kind (geometry, shader, compositor)"))?;
        let settings = if self.accept("(").is_some() {
            self.args(true)?
        } else {
            Vec::new()
        };
        self.expect_text("KEYWORD", "graph", None)?;
        let name_tok = if let Some(s) = self.accept("STRING") {
            s
        } else {
            self.expect("IDENT", Some("graph name"))?
        };
        self.expect("(", None)?;
        let param_tree = self.typed_list(")", true)?;
        self.expect("->", None)?;
        let (output_tree, single) = if self.accept("(").is_some() {
            (self.typed_list(")", true)?, false)
        } else {
            let t = self.expect("IDENT", Some("return type"))?;
            (
                vec![ParamTreeItem::Param(Param {
                    name: t.text.clone(),
                    type_name: t.text,
                    line: t.line,
                    col: t.col,
                    default: None,
                    range: None,
                    options: Vec::new(),
                    alias: None,
                })],
                true,
            )
        };
        let params = flatten(&param_tree);
        let outputs = flatten(&output_tree);
        self.expect("{", None)?;
        let mut description = None;
        let mut description_line = 0;
        if self.at_description() {
            let desc_tok = self.advance();
            description = Some(desc_tok.text);
            description_line = desc_tok.line;
        }
        let mut body = Vec::new();
        while !self.at("}") {
            if self.at("EOF") {
                return Err(self.fail("expected '}' before end of file", None));
            }
            if self.at_description() {
                return Err(self.fail(
                    "graph description must be the first statement in graph body",
                    None,
                ));
            }
            body.push(self.statement()?);
        }
        let end = self.advance();
        let has_panels_in_params = param_tree.iter().any(|i| matches!(i, ParamTreeItem::Panel(_)));
        let has_panels_in_outputs = output_tree.iter().any(|i| matches!(i, ParamTreeItem::Panel(_)));
        Ok(Graph {
            kind: kind.text,
            name: name_tok.text,
            params,
            outputs,
            single_output: single,
            body,
            line: kind.line,
            col: kind.col,
            end: end.line,
            description,
            description_line,
            settings,
            param_tree: if has_panels_in_params {
                Some(param_tree)
            } else {
                None
            },
            output_tree: if has_panels_in_outputs {
                Some(output_tree)
            } else {
                None
            },
        })
    }

    fn at_description(&self) -> bool {
        self.at("STRING") && !self.peek(1).is("{") && !self.peek(1).is("COLOR") && !self.peek(1).is("..")
    }

    fn typed_list(&mut self, close: &str, header: bool) -> Result<Vec<ParamTreeItem>, BnError> {
        let mut items = Vec::new();
        while self.accept(close).is_none() {
            if self.at("STRING") && (self.peek(1).is("{") || self.peek(1).is("(")) {
                if !header {
                    return Err(self.fail("panels are only allowed in graph headers", None));
                }
                items.push(ParamTreeItem::Panel(self.panel()?));
                if self.accept(",").is_none() {
                    self.expect(close, None)?;
                    break;
                }
                continue;
            }
            let name_tok = if let Some(s) = self.accept("STRING") {
                s
            } else {
                self.expect("IDENT", Some("name"))?
            };
            let mut alias = None;
            if self.at_text("IDENT", "as") && self.peek(1).is("IDENT") {
                if !header {
                    return Err(self.fail("'as' is only allowed in graph headers", None));
                }
                self.advance();
                alias = Some(self.advance().text);
            }
            self.expect(":", None)?;
            let t = self.expect("IDENT", Some("type"))?;
            let mut options = Vec::new();
            if self.accept("(").is_some() {
                options = self.args(true)?;
            }
            let mut default = None;
            if self.accept("=").is_some() {
                default = Some(self.unary()?);
            }
            let mut range = None;
            if self.at_text("IDENT", "in") && !self.peek(1).is(":") {
                self.advance();
                let lo = if self.at("..") {
                    None
                } else {
                    Some(self.unary()?)
                };
                self.expect("..", Some("'..' between min and max"))?;
                let hi = if self.tok().is("NUMBER") || self.tok().is("-") {
                    Some(self.unary()?)
                } else {
                    None
                };
                if lo.is_none() && hi.is_none() {
                    return Err(self.fail("empty bounds: specify at least min or max", None));
                }
                range = Some((lo, hi));
            }
            items.push(ParamTreeItem::Param(Param {
                name: name_tok.text,
                type_name: t.text,
                line: name_tok.line,
                col: name_tok.col,
                default,
                range,
                options,
                alias,
            }));
            if self.accept(",").is_none() {
                self.expect(close, None)?;
                break;
            }
        }
        Ok(items)
    }

    fn panel(&mut self) -> Result<Panel, BnError> {
        let t = self.advance();
        let options = if self.accept("(").is_some() {
            self.args(true)?
        } else {
            Vec::new()
        };
        self.expect("{", Some("'{' after panel name"))?;
        let items = self.typed_list("}", true)?;
        let end = self.tokens[self.i - 1].line;
        Ok(Panel {
            name: t.text,
            items,
            line: t.line,
            col: t.col,
            options,
            end,
        })
    }

    fn statement(&mut self) -> Result<Stmt, BnError> {
        let t = self.tok().clone();
        if self.at("{")
            || self.at("COLOR")
            || self.at("..")
            || (self.at("STRING")
                && (self.peek(1).is("{") || self.peek(1).is("COLOR") || self.peek(1).is("..")))
        {
            return Ok(Stmt::Frame(self.frame()?));
        }
        if self.accept_text("KEYWORD", "return").is_some() {
            if self.at("(")
                && (self.peek(1).is(")")
                    || ((self.peek(1).is("IDENT") || self.peek(1).is("STRING")) && self.peek(2).is(":")))
            {
                self.advance();
                let fields = self.args(true)?;
                let look = self.look()?;
                return Ok(Stmt::Return(Return {
                    value: ReturnValue::Record(Record {
                        fields,
                        line: t.line,
                        col: t.col,
                    }),
                    line: t.line,
                    col: t.col,
                    look,
                }));
            }
            let val = self.expr()?;
            let look = self.look()?;
            return Ok(Stmt::Return(Return {
                value: ReturnValue::Expr(val),
                line: t.line,
                col: t.col,
                look,
            }));
        }
        if self.at("IDENT") && self.peek(1).is("=") {
            if t.text == "dot" || t.text == "cross" {
                let msg = if t.text == "dot" { "dot product" } else { "cross product" };
                return Err(self.fail(
                    format!(
                        "'{}' is reserved for {}: choose another name",
                        t.text, msg
                    ),
                    Some(&t),
                ));
            }
            self.advance(); // IDENT
            self.advance(); // =
            let value = if self.at_text("KEYWORD", "repeat") {
                AssignValue::Repeat(self.repeat()?)
            } else if self.at_closure() {
                AssignValue::Closure(self.closure()?)
            } else if self.at_zone() {
                self.zone()?
            } else {
                let e = self.expr()?;
                let look = self.look()?;
                return Ok(Stmt::Assign(Assign {
                    name: t.text,
                    value: AssignValue::Expr(e),
                    line: t.line,
                    col: t.col,
                    look,
                }));
            };
            return Ok(Stmt::Assign(Assign {
                name: t.text,
                value,
                line: t.line,
                col: t.col,
                look: None,
            }));
        }
        Err(self.fail(
            format!(
                "expected statement (name = ..., return, or frame \"title\" {{ ... }}), found {}",
                t.describe()
            ),
            Some(&t),
        ))
    }

    fn look(&mut self) -> Result<Option<Look>, BnError> {
        let at = match self.accept("@") {
            Some(tok) => tok,
            None => return Ok(None),
        };
        let label = if self.at("STRING") && self.tok().line == at.line {
            Some(self.advance().text)
        } else {
            None
        };
        let color = if self.at("COLOR") && self.tok().line == at.line {
            Some(self.advance().text)
        } else {
            None
        };
        let mut flags = Vec::new();
        while self.at("IDENT")
            && (self.tok().text == "hide" || self.tok().text == "mute")
            && self.tok().line == at.line
        {
            let f = self.advance().text;
            if flags.contains(&f) {
                return Err(self.fail(format!("duplicate flag '{}'", f), None));
            }
            flags.push(f);
        }
        if label.is_none() && color.is_none() && flags.is_empty() {
            return Err(self.fail(
                "after '@' on the same line: a \"label\", #color, hide, or mute",
                Some(&at),
            ));
        }
        Ok(Some(Look {
            flags,
            line: at.line,
            col: at.col,
            label,
            color,
        }))
    }

    fn frame(&mut self) -> Result<Frame, BnError> {
        let t = self.tok().clone();
        let label = if self.at("STRING") {
            Some(self.advance().text)
        } else {
            None
        };
        let continued = self.accept("..").is_some();
        let color = if continued {
            None
        } else if self.at("COLOR") {
            Some(self.advance().text)
        } else {
            None
        };
        if continued && self.at("COLOR") {
            return Err(self.fail(
                "continued frame retains its color: write only \"title\" .. {",
                None,
            ));
        }
        self.expect("{", None)?;
        let mut body = Vec::new();
        while !self.at("}") {
            if self.at("EOF") {
                return Err(self.fail("expected '}' before end of file", None));
            }
            body.push(self.statement()?);
        }
        let end = self.advance();
        Ok(Frame {
            label,
            color,
            body,
            line: t.line,
            col: t.col,
            end: end.line,
            continued,
        })
    }

    fn repeat(&mut self) -> Result<Repeat, BnError> {
        let t = self.advance();
        self.expect("(", Some("'(' after repeat"))?;
        let args = self.args(false)?;
        self.no_alias(&args)?;
        if args.is_empty() || args[0].name.is_some() {
            return Err(self.fail(
                "repeat expects iteration count first: repeat(10, state: init, ...)",
                Some(&t),
            ));
        }
        if args.len() < 2 {
            return Err(self.fail(
                "repeat expects at least one state: repeat(10, state: init)",
                Some(&t),
            ));
        }
        if args.iter().any(|a| !a.options.is_empty()) {
            return Err(self.fail("repeat state does not accept options", Some(&t)));
        }
        self.expect("{", Some("'{' after repeat(...)"))?;
        let (body, end) = self.block()?;
        Ok(Repeat {
            count: args[0].value.clone(),
            states: args[1..].to_vec(),
            body,
            line: t.line,
            col: t.col,
            end: end.line,
        })
    }

    fn at_zone(&self) -> bool {
        if !(self.at("IDENT")
            && (self.tok().text == "simulate" || self.tok().text == "foreach")
            && self.peek(1).is("("))
        {
            return false;
        }
        let mut depth = 0;
        let mut j = self.i + 1;
        while !self.tokens[j].is("EOF") {
            if self.tokens[j].is("(") {
                depth += 1;
            } else if self.tokens[j].is(")") {
                depth -= 1;
                if depth == 0 {
                    return self.tokens[j + 1].is("{");
                }
            }
            j += 1;
        }
        false
    }

    fn zone(&mut self) -> Result<AssignValue, BnError> {
        let t = self.advance();
        self.advance(); // "("
        let args = self.args(false)?;
        self.no_alias(&args)?;
        if t.text == "simulate" {
            if args.iter().any(|a| a.name.is_none()) {
                return Err(self.fail(
                    "simulate expects named states: simulate(state: init, ...)",
                    Some(&t),
                ));
            }
        } else if args.is_empty()
            || args[0].name.is_some()
            || args[1..].iter().any(|a| a.name.is_none())
        {
            return Err(self.fail(
                "foreach expects geometry first, then named arguments: foreach(geometry, domain: FACE, value: field, ...)",
                Some(&t),
            ));
        }
        self.expect("{", None)?;
        let (body, end) = self.block()?;
        if t.text == "simulate" {
            Ok(AssignValue::Simulate(Simulate {
                states: args,
                body,
                line: t.line,
                col: t.col,
                end: end.line,
            }))
        } else {
            Ok(AssignValue::Foreach(Foreach {
                geometry: args[0].value.clone(),
                args: args[1..].to_vec(),
                body,
                line: t.line,
                col: t.col,
                end: end.line,
            }))
        }
    }

    fn block(&mut self) -> Result<(Vec<Stmt>, Token), BnError> {
        let mut body = Vec::new();
        while !self.at("}") {
            if self.at("EOF") {
                return Err(self.fail("expected '}' before end of file", None));
            }
            body.push(self.statement()?);
        }
        let end = self.advance();
        Ok((body, end))
    }

    fn at_closure(&self) -> bool {
        if !(self.at_text("IDENT", "closure") && self.peek(1).is("(")) {
            return false;
        }
        if let Some(mut idx) = self.matching(self.i + 1) {
            if self.tokens[idx + 1].is("->") {
                idx += 2;
                if self.tokens[idx].is("(") {
                    if let Some(c_idx) = self.matching(idx) {
                        return self.tokens[c_idx + 1].is("{");
                    }
                } else {
                    return self.tokens[idx + 1].is("{");
                }
            }
        }
        false
    }

    fn matching(&self, i: usize) -> Option<usize> {
        let mut depth = 0;
        for j in i..self.tokens.len() {
            if self.tokens[j].is("(") {
                depth += 1;
            } else if self.tokens[j].is(")") {
                depth -= 1;
                if depth == 0 {
                    return Some(j);
                }
            } else if self.tokens[j].is("EOF") {
                return None;
            }
        }
        None
    }

    fn closure(&mut self) -> Result<Closure, BnError> {
        let t = self.advance();
        self.expect("(", None)?;
        let params = flatten(&self.typed_list(")", false)?);
        self.expect("->", None)?;
        let (outputs, single) = self.outputs()?;
        self.expect("{", Some("'{' after closure(...) -> ..."))?;
        let mut body = Vec::new();
        while !self.at("}") {
            if self.at("EOF") {
                return Err(self.fail("expected '}' before end of file", None));
            }
            body.push(self.statement()?);
        }
        let end = self.advance();
        Ok(Closure {
            params,
            outputs,
            single_output: single,
            body,
            line: t.line,
            col: t.col,
            end: end.line,
        })
    }

    fn outputs(&mut self) -> Result<(Vec<Param>, bool), BnError> {
        if self.accept("(").is_some() {
            Ok((flatten(&self.typed_list(")", false)?), false))
        } else {
            let t = self.expect("IDENT", Some("return type"))?;
            Ok((
                vec![Param {
                    name: t.text.clone(),
                    type_name: t.text,
                    line: t.line,
                    col: t.col,
                    default: None,
                    range: None,
                    options: Vec::new(),
                    alias: None,
                }],
                true,
            ))
        }
    }

    pub fn expr(&mut self) -> Result<Expr, BnError> {
        let mut left = self.disjunction()?;
        while self.at("|>") {
            let op = self.advance();
            let rhs = self.postfix()?;
            let call = match &rhs {
                Expr::Member(m) => m.target.as_ref(),
                _ => &rhs,
            };
            if !matches!(call, Expr::Call(_)) {
                return Err(self.fail("expected node call after |>", Some(&op)));
            }
            left = Expr::Pipe(Pipe {
                left: Box::new(left),
                call: Box::new(rhs),
                line: op.line,
                col: op.col,
            });
        }
        Ok(left)
    }

    fn disjunction(&mut self) -> Result<Expr, BnError> {
        let mut left = self.conjunction()?;
        while self.at_text("KEYWORD", "or") || self.at_text("KEYWORD", "xor") {
            let op = self.advance();
            let right = self.conjunction()?;
            left = Expr::BinOp(BinOp {
                op: op.text,
                left: Box::new(left),
                right: Box::new(right),
                line: op.line,
                col: op.col,
            });
        }
        Ok(left)
    }

    fn conjunction(&mut self) -> Result<Expr, BnError> {
        let mut left = self.negation()?;
        while self.at_text("KEYWORD", "and") {
            let op = self.advance();
            let right = self.negation()?;
            left = Expr::BinOp(BinOp {
                op: "and".to_string(),
                left: Box::new(left),
                right: Box::new(right),
                line: op.line,
                col: op.col,
            });
        }
        Ok(left)
    }

    fn negation(&mut self) -> Result<Expr, BnError> {
        if self.at_text("KEYWORD", "not") {
            let op = self.advance();
            let val = self.negation()?;
            return Ok(Expr::Not(Not {
                value: Box::new(val),
                line: op.line,
                col: op.col,
            }));
        }
        self.comparison()
    }

    fn comparison(&mut self) -> Result<Expr, BnError> {
        let mut left = self.additive()?;
        let is_cmp = |s: &str| ["<", "<=", ">", ">=", "==", "!="].contains(&s);
        let cur_kind = self.tok().kind_str();
        if is_cmp(cur_kind) {
            let op = self.advance();
            let right = self.additive()?;
            left = Expr::BinOp(BinOp {
                op: op.kind_str().to_string(),
                left: Box::new(left),
                right: Box::new(right),
                line: op.line,
                col: op.col,
            });
            if is_cmp(self.tok().kind_str()) {
                return Err(self.fail(
                    "chained comparisons not allowed; assign intermediate result to a variable",
                    None,
                ));
            }
        }
        Ok(left)
    }

    fn additive(&mut self) -> Result<Expr, BnError> {
        let mut left = self.multiplicative()?;
        while self.at("+") || self.at("-") {
            let op = self.advance();
            let right = self.multiplicative()?;
            left = Expr::BinOp(BinOp {
                op: op.kind_str().to_string(),
                left: Box::new(left),
                right: Box::new(right),
                line: op.line,
                col: op.col,
            });
        }
        Ok(left)
    }

    fn multiplicative(&mut self) -> Result<Expr, BnError> {
        let mut left = self.unary()?;
        let punct_ops = ["*", "/", "⋅", "·", "×"];
        let is_punct = |s: &str| punct_ops.contains(&s);
        let is_word_product = |t: &Token, peek: &Token| {
            t.is("IDENT") && (t.text == "dot" || t.text == "cross" || t.text == "·") && !peek.is("=")
        };

        while is_punct(self.tok().kind_str()) || is_word_product(self.tok(), self.peek(1)) {
            let op = self.advance();
            let canonical_op = match op.text.as_str() {
                "dot" | "·" => "⋅",
                "cross" => "×",
                _ => &op.text,
            };
            let right = self.unary()?;
            left = Expr::BinOp(BinOp {
                op: canonical_op.to_string(),
                left: Box::new(left),
                right: Box::new(right),
                line: op.line,
                col: op.col,
            });
        }
        Ok(left)
    }

    fn unary(&mut self) -> Result<Expr, BnError> {
        if self.at("-") {
            let op = self.advance();
            let val = self.unary()?;
            if let Expr::Number(num) = val {
                return Ok(Expr::Number(Number {
                    value: -num.value,
                    is_int: num.is_int,
                    line: op.line,
                    col: op.col,
                }));
            }
            return Ok(Expr::Neg(Neg {
                value: Box::new(val),
                line: op.line,
                col: op.col,
            }));
        }
        self.postfix()
    }

    fn postfix(&mut self) -> Result<Expr, BnError> {
        let mut node = self.primary()?;
        if let Expr::Call(ref mut c) = node {
            if self.at("->") {
                self.advance();
                let (outs, single) = self.outputs()?;
                c.outputs = Some(outs);
                c.single_output = single;
                return Ok(node);
            }
        }
        while self.at(".") {
            let dot = self.advance();
            if self.at("IDENT") || self.at("STRING") {
                let member_tok = self.advance();
                node = Expr::Member(Member {
                    target: Box::new(node),
                    socket: member_tok.text,
                    line: dot.line,
                    col: dot.col,
                });
            } else {
                return Err(self.fail("expected output socket name after '.'", None));
            }
        }
        Ok(node)
    }

    fn primary(&mut self) -> Result<Expr, BnError> {
        let t = self.tok().clone();
        if self.accept("NUMBER").is_some() {
            let is_int = !t.text.contains('.') && !t.text.contains('e') && !t.text.contains('E');
            let val: f64 = if is_int {
                t.text.parse::<i64>().map_err(|_| self.fail("invalid integer", Some(&t)))? as f64
            } else {
                t.text.parse::<f64>().map_err(|_| self.fail("invalid float", Some(&t)))?
            };
            return Ok(Expr::Number(Number {
                value: val,
                is_int,
                line: t.line,
                col: t.col,
            }));
        }
        if self.accept("STRING").is_some() {
            return Ok(Expr::String(StringLit {
                value: t.text,
                line: t.line,
                col: t.col,
            }));
        }
        if self.accept_text("KEYWORD", "true").is_some() {
            return Ok(Expr::Bool(BoolLit {
                value: true,
                line: t.line,
                col: t.col,
            }));
        }
        if self.accept_text("KEYWORD", "false").is_some() {
            return Ok(Expr::Bool(BoolLit {
                value: false,
                line: t.line,
                col: t.col,
            }));
        }
        if self.at_text("KEYWORD", "repeat") {
            return Err(self.fail(
                "repeat can only be assigned to a variable: r = repeat(10, state: init) { ... }",
                Some(&t),
            ));
        }
        if self.at_text("KEYWORD", "xor") && self.peek(1).is("(") {
            self.advance();
            self.advance();
            let args = self.args(false)?;
            return Ok(Expr::Call(Call {
                name: "xor".to_string(),
                args,
                line: t.line,
                col: t.col,
                outputs: None,
                single_output: false,
            }));
        }
        if self.accept("IDENT").is_some() {
            if self.accept("(").is_some() {
                let args = self.args(false)?;
                return Ok(Expr::Call(Call {
                    name: t.text,
                    args,
                    line: t.line,
                    col: t.col,
                    outputs: None,
                    single_output: false,
                }));
            }
            return Ok(Expr::Ref(Ref {
                name: t.text,
                line: t.line,
                col: t.col,
            }));
        }
        if self.accept("(").is_some() {
            let mut items = vec![self.expr()?];
            while self.accept(",").is_some() {
                if self.at(")") {
                    break;
                }
                items.push(self.expr()?);
            }
            self.expect(")", None)?;
            return if items.len() == 1 {
                Ok(items.remove(0))
            } else {
                Ok(Expr::Tuple(Tuple {
                    items,
                    line: t.line,
                    col: t.col,
                }))
            };
        }
        Err(self.fail(format!("expected expression, found {}", t.describe()), Some(&t)))
    }

    fn args(&mut self, named_only: bool) -> Result<Vec<Arg>, BnError> {
        let mut args = Vec::new();
        while self.accept(")").is_none() {
            let t = self.tok().clone();
            if (t.is("IDENT") || t.is("STRING"))
                && self.peek(1).is_with_text("IDENT", "as")
                && self.peek(2).is("IDENT")
                && (self.peek(3).is(":") || self.peek(3).is("("))
            {
                self.advance(); // name
                self.advance(); // as
                let alias = self.advance();
                if named_only {
                    return Err(self.fail(
                        "'as' is only allowed for items in itemized node calls or inputs in graph headers",
                        Some(&alias),
                    ));
                }
                let options = if self.accept("(").is_some() {
                    self.args(true)?
                } else {
                    Vec::new()
                };
                self.expect(":", None)?;
                let mut it = self.item(&t, options)?;
                it.alias = Some(alias.text);
                args.push(it);
            } else if (t.is("IDENT") || t.is("STRING")) && self.peek(1).is(":") {
                self.advance();
                self.advance();
                args.push(self.item(&t, Vec::new())?);
            } else if !named_only && self.at_item_options() {
                self.advance();
                self.advance();
                let options = self.args(true)?;
                self.expect(":", None)?;
                args.push(self.item(&t, options)?);
            } else if named_only {
                return Err(self.fail("expected named argument (name: value)", None));
            } else {
                if args.iter().any(|a| a.name.is_some()) {
                    return Err(self.fail("positional argument after named argument", None));
                }
                let val = self.expr()?;
                args.push(Arg {
                    name: None,
                    value: val,
                    line: t.line,
                    col: t.col,
                    options: Vec::new(),
                    type_decl: None,
                    alias: None,
                });
            }
            if self.accept(",").is_none() {
                self.expect(")", None)?;
                break;
            }
        }
        Ok(args)
    }

    fn no_alias(&self, args: &[Arg]) -> Result<(), BnError> {
        for a in args {
            if let Some(ref alias) = a.alias {
                let name_str = a.name.as_deref().unwrap_or("");
                return Err(BnError::new(
                    self.filename,
                    a.line,
                    a.col,
                    format!(
                        "'{} as {}': 'as' is only allowed for items in itemized node calls",
                        name_str, alias
                    ),
                ));
            }
        }
        Ok(())
    }

    fn at_item_options(&self) -> bool {
        if !self.tok().is("IDENT") && !self.tok().is("STRING") {
            return false;
        }
        if !self.peek(1).is("(") {
            return false;
        }
        let mut depth = 0;
        let mut k = 1;
        loop {
            let peeked = self.peek(k);
            if peeked.is("EOF") {
                return false;
            }
            if peeked.is("(") {
                depth += 1;
            } else if peeked.is(")") {
                depth -= 1;
                if depth == 0 {
                    return self.peek(k + 1).is(":");
                }
            }
            k += 1;
        }
    }

    fn item(&mut self, t: &Token, mut options: Vec<Arg>) -> Result<Arg, BnError> {
        let mut value = self.expr()?;
        let mut type_decl = None;
        if self.at("=") {
            let eq = self.advance();
            let mut p = self.item_type(&t.text, &value, &eq)?;
            options.extend(p.options);
            p.options = Vec::new();
            type_decl = Some(p);
            value = self.expr()?;
        }
        Ok(Arg {
            name: Some(t.text.clone()),
            value,
            line: t.line,
            col: t.col,
            options,
            type_decl,
            alias: None,
        })
    }

    fn item_type(&self, name: &str, e: &Expr, at: &Token) -> Result<Param, BnError> {
        if let Expr::Ref(r) = e {
            return Ok(Param {
                name: name.to_string(),
                type_name: r.name.clone(),
                line: r.line,
                col: r.col,
                default: None,
                range: None,
                options: Vec::new(),
                alias: None,
            });
        }
        if let Expr::Call(c) = e {
            if c.outputs.is_none()
                && c.args.iter().all(|a| a.name.is_some() && a.type_decl.is_none())
            {
                return Ok(Param {
                    name: name.to_string(),
                    type_name: c.name.clone(),
                    line: c.line,
                    col: c.col,
                    default: None,
                    range: None,
                    options: c.args.clone(),
                    alias: None,
                });
            }
        }
        Err(self.fail("type expected before '=': name: Type = value", Some(at)))
    }
}
