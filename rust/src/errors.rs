use std::fmt;

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Diagnostic {
    pub filename: String,
    pub line: usize,
    pub col: usize,
    pub message: String,
}

impl fmt::Display for Diagnostic {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}:{}:{}: {}", self.filename, self.line, self.col, self.message)
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct BnError {
    pub diagnostics: Vec<Diagnostic>,
}

impl BnError {
    pub fn new(filename: impl Into<String>, line: usize, col: usize, message: impl Into<String>) -> Self {
        Self {
            diagnostics: vec![Diagnostic {
                filename: filename.into(),
                line,
                col,
                message: message.into(),
            }],
        }
    }

    pub fn from_diagnostics(diagnostics: Vec<Diagnostic>) -> Self {
        Self { diagnostics }
    }
}

impl fmt::Display for BnError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        for (i, d) in self.diagnostics.iter().enumerate() {
            if i > 0 {
                writeln!(f)?;
            }
            write!(f, "{}", d)?;
        }
        Ok(())
    }
}

impl std::error::Error for BnError {}
