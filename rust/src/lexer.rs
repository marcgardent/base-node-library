use crate::errors::BnError;
use crate::tokens::{Token, TokenKind, KEYWORDS, PUNCT};

pub fn tokenize(source: &str, filename: &str, strict: bool) -> Result<Vec<Token>, BnError> {
    let chars: Vec<char> = source.chars().collect();
    let n = chars.len();
    let mut tokens = Vec::new();
    let mut i = 0;
    let mut line = 1;
    let mut col = 1;

    let starts_with = |idx: usize, pat: &str| -> bool {
        let pat_chars: Vec<char> = pat.chars().collect();
        if idx + pat_chars.len() > n {
            return false;
        }
        for (j, &pc) in pat_chars.iter().enumerate() {
            if chars[idx + j] != pc {
                return false;
            }
        }
        true
    };

    while i < n {
        let c = chars[i];
        if c == '\n' {
            i += 1;
            line += 1;
            col = 1;
            continue;
        }
        if c == ' ' || c == '\t' || c == '\r' {
            i += 1;
            col += 1;
            continue;
        }
        if starts_with(i, "//") {
            let start = i;
            while i < n && chars[i] != '\n' {
                i += 1;
            }
            if !strict {
                let text: String = chars[start..i].iter().collect();
                tokens.push(Token::new(TokenKind::Comment, text, line, col));
                col += i - start;
            }
            continue;
        }

        let start = i;
        let (kind, text);
        if c.is_alphabetic() || c == '_' {
            while i < n && (chars[i].is_alphanumeric() || chars[i] == '_') {
                i += 1;
            }
            let s: String = chars[start..i].iter().collect();
            let k = if KEYWORDS.contains(&s.as_str()) {
                TokenKind::Keyword
            } else {
                TokenKind::Ident
            };
            text = s;
            kind = k;
        } else if c.is_ascii_digit() {
            while i < n && chars[i].is_ascii_digit() {
                i += 1;
            }
            if i + 1 < n && chars[i] == '.' && chars[i + 1].is_ascii_digit() {
                i += 1;
                while i < n && chars[i].is_ascii_digit() {
                    i += 1;
                }
            }
            if i < n && (chars[i] == 'e' || chars[i] == 'E') {
                let mut j = i + 1;
                if j < n && (chars[j] == '+' || chars[j] == '-') {
                    j += 1;
                }
                if j < n && chars[j].is_ascii_digit() {
                    i = j;
                    while i < n && chars[i].is_ascii_digit() {
                        i += 1;
                    }
                }
            }
            text = chars[start..i].iter().collect();
            kind = TokenKind::Number;
        } else if c == '#' {
            i += 1;
            while i < n && (chars[i].is_alphanumeric() || chars[i] == '_') {
                i += 1;
            }
            text = chars[start..i].iter().collect();
            kind = TokenKind::Color;
        } else if c == '"' {
            i += 1;
            while i < n && chars[i] != '"' && chars[i] != '\n' {
                i += 1;
            }
            if i < n && chars[i] == '"' {
                i += 1;
                text = chars[start + 1..i - 1].iter().collect();
                kind = TokenKind::String;
            } else if strict {
                return Err(BnError::new(filename, line, col, "unclosed string"));
            } else {
                text = chars[start + 1..i].iter().collect();
                kind = TokenKind::OpenString;
            }
        } else {
            let mut matched_p = None;
            for &p in PUNCT {
                if starts_with(i, p) {
                    matched_p = Some(p);
                    break;
                }
            }
            if let Some(p) = matched_p {
                let p_len = p.chars().count();
                i += p_len;
                text = p.to_string();
                kind = TokenKind::Punct(p.to_string());
            } else if strict {
                return Err(BnError::new(
                    filename,
                    line,
                    col,
                    format!("unexpected character '{}'", c),
                ));
            } else {
                i += 1;
                col += 1;
                continue;
            }
        }

        tokens.push(Token::new(kind, text, line, col));
        col += i - start;
    }

    tokens.push(Token::new(TokenKind::Eof, "", line, col));
    Ok(tokens)
}
