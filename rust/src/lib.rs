pub const VERSION: &str = "0.7.0";
pub const EDITION: &str = "2026";
pub const STDLIB_VERSION: &str = "0.7.0";

pub mod ast;
pub mod errors;
pub mod format;
pub mod lexer;
pub mod parser;
pub mod profiles;
pub mod tokens;

pub use ast::File;
pub use errors::{BnError, Diagnostic};
pub use format::{format_file, format_source};
pub use lexer::tokenize;
pub use parser::parse;
pub use profiles::{
    analyze_profile_ascent, check_profile, load_profile, solve_minimal_profile, AscentAnalysis,
    Profile, ProfileKind, PROFILE_ASCENT_CHAIN,
};
pub use tokens::{Token, TokenKind};
