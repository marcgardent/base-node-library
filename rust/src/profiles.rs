use std::collections::HashSet;

use serde::{Deserialize, Serialize};

use crate::ast::{AssignValue, Expr, File, Stmt};

pub const CORE_JSON: &str = include_str!("../../profiles/core.json");
pub const SDF2D_JSON: &str = include_str!("../../profiles/sdf2d.json");
pub const VECTOR2D_JSON: &str = include_str!("../../profiles/vector2d.json");
pub const INK2D_JSON: &str = include_str!("../../profiles/ink2d.json");
pub const RASTER2D_JSON: &str = include_str!("../../profiles/raster2d.json");
pub const BLENDER_GEOMETRY_JSON: &str = include_str!("../../profiles/blender-geometry.json");

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum ProfileKind {
    Core,
    Sdf2d,
    Vector2d,
    Ink2d,
    Raster2d,
    BlenderGeometry,
}

impl ProfileKind {
    pub fn name(&self) -> &'static str {
        match self {
            ProfileKind::Core => "core",
            ProfileKind::Sdf2d => "sdf2d",
            ProfileKind::Vector2d => "vector2d",
            ProfileKind::Ink2d => "ink2d",
            ProfileKind::Raster2d => "raster2d",
            ProfileKind::BlenderGeometry => "blender-geometry",
        }
    }

    pub fn from_str_name(s: &str) -> Option<Self> {
        match s {
            "core" => Some(ProfileKind::Core),
            "sdf2d" => Some(ProfileKind::Sdf2d),
            "vector2d" => Some(ProfileKind::Vector2d),
            "ink2d" => Some(ProfileKind::Ink2d),
            "raster2d" => Some(ProfileKind::Raster2d),
            "blender-geometry" => Some(ProfileKind::BlenderGeometry),
            _ => None,
        }
    }
}

#[derive(Clone, Debug, Deserialize)]
struct RawProfile {
    name: String,
    #[serde(default)]
    version: usize,
    #[serde(default)]
    description: String,
    #[serde(default)]
    extends: Option<String>,
    #[serde(default)]
    kinds: Vec<String>,
    #[serde(default)]
    types: Vec<String>,
    #[serde(default)]
    implicit: Vec<String>,
    #[serde(default)]
    aliases: std::collections::HashMap<String, String>,
    #[serde(default)]
    zones: Vec<String>,
    #[serde(default)]
    nodes: Vec<String>,
    #[serde(default)]
    allow_all_blender_nodes: bool,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct Profile {
    pub name: String,
    pub version: usize,
    pub description: String,
    pub extends: Option<String>,
    pub kinds: Vec<String>,
    pub types: Vec<String>,
    pub implicit: Vec<String>,
    pub aliases: std::collections::HashMap<String, String>,
    pub zones: Vec<String>,
    pub nodes: Vec<String>,
    pub allow_all_blender_nodes: bool,
}

pub fn load_profile(kind: ProfileKind) -> Profile {
    let raw_for = |k: ProfileKind| -> RawProfile {
        let json_str = match k {
            ProfileKind::Core => CORE_JSON,
            ProfileKind::Sdf2d => SDF2D_JSON,
            ProfileKind::Vector2d => VECTOR2D_JSON,
            ProfileKind::Ink2d => INK2D_JSON,
            ProfileKind::Raster2d => RASTER2D_JSON,
            ProfileKind::BlenderGeometry => BLENDER_GEOMETRY_JSON,
        };
        serde_json::from_str(json_str).expect("Embedded profile JSON must be valid")
    };

    let mut chain = Vec::new();
    let mut current_kind = Some(kind);

    while let Some(k) = current_kind {
        let raw = raw_for(k);
        let next_kind = raw.extends.as_deref().and_then(ProfileKind::from_str_name);
        chain.push(raw);
        current_kind = next_kind;
    }

    // Reverse so base profile comes first
    chain.reverse();

    let mut merged = Profile {
        name: kind.name().to_string(),
        version: 1,
        description: String::new(),
        extends: None,
        kinds: Vec::new(),
        types: Vec::new(),
        implicit: Vec::new(),
        aliases: std::collections::HashMap::new(),
        zones: Vec::new(),
        nodes: Vec::new(),
        allow_all_blender_nodes: false,
    };

    for item in chain {
        merged.name = item.name;
        merged.version = item.version;
        merged.description = item.description;
        merged.extends = item.extends;
        for k in item.kinds {
            if !merged.kinds.contains(&k) {
                merged.kinds.push(k);
            }
        }
        for t in item.types {
            if !merged.types.contains(&t) {
                merged.types.push(t);
            }
        }
        for imp in item.implicit {
            if !merged.implicit.contains(&imp) {
                merged.implicit.push(imp);
            }
        }
        for (k, v) in item.aliases {
            merged.aliases.insert(k, v);
        }
        for z in item.zones {
            if !merged.zones.contains(&z) {
                merged.zones.push(z);
            }
        }
        for n in item.nodes {
            if !merged.nodes.contains(&n) {
                merged.nodes.push(n);
            }
        }
        if item.allow_all_blender_nodes {
            merged.allow_all_blender_nodes = true;
        }
    }

    merged
}

const BUILTIN_MATH_FUNCS: &[&str] = &[
    "sin",
    "cos",
    "tan",
    "asin",
    "acos",
    "atan",
    "atan2",
    "sinh",
    "cosh",
    "tanh",
    "sqrt",
    "abs",
    "exp",
    "log",
    "pow",
    "min",
    "max",
    "clamp",
    "floor",
    "ceil",
    "fract",
    "round",
    "trunc",
    "sign",
    "mod",
    "radians",
    "degrees",
    "length",
    "normalize",
    "distance",
    "dot",
    "cross",
    "xor",
    "xnor",
    "nand",
    "nor",
    "imply",
    "nimply",
];

struct CheckCtx<'a> {
    g_name: &'a str,
    prof_name: &'a str,
    allowed_zones: &'a HashSet<&'a str>,
    allowed_nodes: &'a HashSet<&'a str>,
    declared_graphs: &'a HashSet<String>,
    imported_names: &'a HashSet<String>,
    imported_modules: &'a HashSet<String>,
    wildcard_import: bool,
    allow_all: bool,
    errors: &'a mut Vec<String>,
}

fn check_expr(e: &Expr, ctx: &mut CheckCtx<'_>) {
    match e {
        Expr::Call(c) => {
            if !ctx.allow_all {
                let is_builtin = BUILTIN_MATH_FUNCS.contains(&c.name.as_str());
                let is_allowed_node = ctx.allowed_nodes.contains(c.name.as_str());
                let is_declared = ctx.declared_graphs.contains(c.name.as_str());
                let is_module_call = if let Some((mod_name, _)) = c.name.split_once("::") {
                    ctx.imported_modules.contains(mod_name)
                } else {
                    false
                };
                let is_imported = is_module_call
                    || ctx.wildcard_import
                    || ctx.imported_names.contains(c.name.as_str());

                if !is_builtin && !is_allowed_node && !is_declared && !is_imported {
                    ctx.errors.push(format!(
                        "Graph '{}': node or function '{}' not in profile '{}'",
                        ctx.g_name, c.name, ctx.prof_name
                    ));
                }
            }
            for a in &c.args {
                check_expr(&a.value, ctx);
            }
        }
        Expr::BinOp(b) => {
            check_expr(&b.left, ctx);
            check_expr(&b.right, ctx);
        }
        Expr::Pipe(p) => {
            check_expr(&p.left, ctx);
            check_expr(&p.call, ctx);
        }
        Expr::Neg(n) => {
            check_expr(&n.value, ctx);
        }
        Expr::Not(n) => {
            check_expr(&n.value, ctx);
        }
        Expr::Member(m) => {
            check_expr(&m.target, ctx);
        }
        Expr::Tuple(t) => {
            for item in &t.items {
                check_expr(item, ctx);
            }
        }
        _ => {}
    }
}

fn check_stmt(s: &Stmt, ctx: &mut CheckCtx<'_>) {
    match s {
        Stmt::Assign(a) => match &a.value {
            AssignValue::Repeat(r) => {
                if !ctx.allowed_zones.contains("repeat") {
                    ctx.errors.push(format!(
                        "Graph '{}': zone 'repeat' not allowed by profile '{}'",
                        ctx.g_name, ctx.prof_name
                    ));
                }
                check_expr(&r.count, ctx);
                for st in &r.states {
                    check_expr(&st.value, ctx);
                }
                for inner in &r.body {
                    check_stmt(inner, ctx);
                }
            }
            AssignValue::Foreach(f) => {
                if !ctx.allowed_zones.contains("foreach") {
                    ctx.errors.push(format!(
                        "Graph '{}': zone 'foreach' not allowed by profile '{}'",
                        ctx.g_name, ctx.prof_name
                    ));
                }
                check_expr(&f.geometry, ctx);
                for arg in &f.args {
                    check_expr(&arg.value, ctx);
                }
                for inner in &f.body {
                    check_stmt(inner, ctx);
                }
            }
            AssignValue::Simulate(sim) => {
                if !ctx.allowed_zones.contains("simulate") {
                    ctx.errors.push(format!(
                        "Graph '{}': zone 'simulate' not allowed by profile '{}'",
                        ctx.g_name, ctx.prof_name
                    ));
                }
                for st in &sim.states {
                    check_expr(&st.value, ctx);
                }
                for inner in &sim.body {
                    check_stmt(inner, ctx);
                }
            }
            AssignValue::Closure(c) => {
                if !ctx.allowed_zones.contains("closure") {
                    ctx.errors.push(format!(
                        "Graph '{}': zone 'closure' not allowed by profile '{}'",
                        ctx.g_name, ctx.prof_name
                    ));
                }
                for inner in &c.body {
                    check_stmt(inner, ctx);
                }
            }
            AssignValue::Expr(e) => {
                check_expr(e, ctx);
            }
        },
        Stmt::Return(r) => match &r.value {
            crate::ast::ReturnValue::Record(rec) => {
                for f in &rec.fields {
                    check_expr(&f.value, ctx);
                }
            }
            crate::ast::ReturnValue::Expr(e) => {
                check_expr(e, ctx);
            }
        },
        Stmt::Frame(f) => {
            for inner in &f.body {
                check_stmt(inner, ctx);
            }
        }
    }
}

pub fn check_profile(file: &File, kind: ProfileKind) -> Vec<String> {
    let profile = load_profile(kind);
    check_profile_custom(file, &profile)
}

pub fn check_profile_custom(file: &File, profile: &Profile) -> Vec<String> {
    let mut errors = Vec::new();

    let allowed_kinds: HashSet<&str> = profile.kinds.iter().map(|s| s.as_str()).collect();
    let allowed_types: HashSet<&str> = profile.types.iter().map(|s| s.as_str()).collect();
    let allowed_implicits: HashSet<&str> = profile.implicit.iter().map(|s| s.as_str()).collect();
    let allowed_zones: HashSet<&str> = profile.zones.iter().map(|s| s.as_str()).collect();
    let mut allowed_nodes: HashSet<&str> = profile.nodes.iter().map(|s| s.as_str()).collect();

    // Include aliases
    for (alias_name, target) in &profile.aliases {
        if allowed_nodes.contains(alias_name.as_str()) {
            allowed_nodes.insert(target.as_str());
        }
        if allowed_nodes.contains(target.as_str()) {
            allowed_nodes.insert(alias_name.as_str());
        }
    }

    // Graph names in this file can be called by other graphs
    let mut declared_graphs: HashSet<String> = HashSet::new();
    for g in &file.graphs {
        declared_graphs.insert(g.name.clone());
        declared_graphs.insert(crate::ast::key(&g.name));
    }
    let mut imported_names: HashSet<String> = HashSet::new();
    let mut imported_modules: HashSet<String> = HashSet::new();
    let mut wildcard_import = false;
    let profile_rank = match profile.name.as_str() {
        "core" => 0,
        "sdf2d" => 1,
        "vector2d" | "raster2d" => 2,
        "ink2d" => 3,
        _ => 4,
    };

    for u in &file.uses {
        imported_modules.insert(u.name.clone());
        if let Some(ref alias) = u.alias {
            imported_modules.insert(alias.clone());
        }
        if let Some(ref names) = u.names {
            for n in names {
                imported_names.insert(n.clone());
                imported_names.insert(format!("{}::{}", u.name, n));
                if let Some(ref alias) = u.alias {
                    imported_names.insert(format!("{}::{}", alias, n));
                }
            }
        } else {
            wildcard_import = true;
        }

        if !profile.allow_all_blender_nodes {
            let req_rank = match u.name.as_str() {
                "math" => 0,
                "sdf2d" => 1,
                "curves2d" | "patterns2d" | "planar2d" | "fillet2d" | "hachures2d" | "deform2d" => {
                    2
                }
                "ink2d" => 3,
                _ => 0,
            };
            if req_rank > profile_rank {
                errors.push(format!(
                    "Imported module '{}' exceeds profile '{}'",
                    u.name, profile.name
                ));
            }
        }
    }

    for g in &file.graphs {
        // 1. Kind check
        if !allowed_kinds.contains(g.kind.as_str()) {
            errors.push(format!(
                "Graph '{}': tree kind '{}' not allowed by profile '{}'",
                g.name, g.kind, profile.name
            ));
        }

        // 2. Interface types check
        for p in &g.params {
            if !allowed_types.contains(p.type_name.as_str()) {
                errors.push(format!(
                    "Graph '{}': input '{}' of type '{}' not allowed by profile '{}'",
                    g.name, p.name, p.type_name, profile.name
                ));
            }
            // Check default implicit
            if let Some(Expr::Call(c)) = &p.default {
                if ["Position", "Normal", "Index", "ID"].contains(&c.name.as_str())
                    && !allowed_implicits.contains(c.name.as_str())
                {
                    errors.push(format!(
                        "Graph '{}': implicit input '{}' for '{}' not allowed by profile '{}'",
                        g.name, c.name, p.name, profile.name
                    ));
                }
            }
        }

        for out in &g.outputs {
            if !allowed_types.contains(out.type_name.as_str()) {
                errors.push(format!(
                    "Graph '{}': output '{}' of type '{}' not allowed by profile '{}'",
                    g.name, out.name, out.type_name, profile.name
                ));
            }
        }

        // 3. Body check: inspect zones and node calls
        let mut ctx = CheckCtx {
            g_name: &g.name,
            prof_name: &profile.name,
            allowed_zones: &allowed_zones,
            allowed_nodes: &allowed_nodes,
            declared_graphs: &declared_graphs,
            imported_names: &imported_names,
            imported_modules: &imported_modules,
            wildcard_import,
            allow_all: profile.allow_all_blender_nodes,
            errors: &mut errors,
        };

        for s in &g.body {
            check_stmt(s, &mut ctx);
        }
    }

    errors
}

pub const PROFILE_ASCENT_CHAIN: &[ProfileKind] = &[
    ProfileKind::Core,
    ProfileKind::Sdf2d,
    ProfileKind::Vector2d,
    ProfileKind::Ink2d,
    ProfileKind::BlenderGeometry,
];

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct AscentAnalysis {
    pub minimal_profile: ProfileKind,
    pub tested: std::collections::HashMap<String, Vec<String>>,
    pub barriers: std::collections::HashMap<String, Vec<String>>,
}

pub fn solve_minimal_profile(file: &File) -> ProfileKind {
    for &k in PROFILE_ASCENT_CHAIN {
        let errors = check_profile(file, k);
        if errors.is_empty() {
            return k;
        }
    }
    ProfileKind::BlenderGeometry
}

pub fn analyze_profile_ascent(file: &File) -> AscentAnalysis {
    let mut tested = std::collections::HashMap::new();
    let mut minimal = ProfileKind::BlenderGeometry;
    let mut found = false;

    for &k in PROFILE_ASCENT_CHAIN {
        let errors = check_profile(file, k);
        tested.insert(k.name().to_string(), errors.clone());
        if errors.is_empty() && !found {
            minimal = k;
            found = true;
        }
    }

    let mut barriers = std::collections::HashMap::new();
    for &k in PROFILE_ASCENT_CHAIN {
        if k == minimal {
            break;
        }
        if let Some(errs) = tested.get(k.name()) {
            barriers.insert(k.name().to_string(), errs.clone());
        }
    }

    AscentAnalysis {
        minimal_profile: minimal,
        tested,
        barriers,
    }
}
