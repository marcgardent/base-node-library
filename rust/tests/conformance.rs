use std::fs;
use std::path::Path;

use base_node::{check_profile, format_source, parse, ProfileKind};

fn read_stdlib_file(candidates: &[&str]) -> (String, String) {
    let mut last_err = String::new();
    for &name in candidates {
        let relative = format!("../stdlib/{}", name);
        let content = fs::read_to_string(&relative).or_else(|_| {
            fs::read_to_string(format!(
                "/home/marcgardent/base-node-library/stdlib/{}",
                name
            ))
        });
        if let Ok(src) = content {
            if let Ok(file) = parse(&src, name) {
                if !file.graphs.is_empty() {
                    return (name.to_string(), src);
                }
            }
            last_err = format!("Candidate '{}' was read but failed parse validation", name);
        }
    }
    panic!(
        "Unable to read valid stdlib file; candidates: {:?}; last error: {}",
        candidates, last_err
    );
}

#[test]
fn test_stdlib_conformance() {
    let files: &[(&[&str], usize)] = &[
        (&["math.bn"], 47),
        (&["sdf2d.bn"], 17),
        (&["curves2d.bn"], 7),
        (&["patterns2d.bn"], 5),
        (&["ink2d.bn"], 7),
        (&["planar2d.bn"], 4),
        (&["fillet2d.bn"], 4),
        (&["hachures2d.bn"], 4),
        (&["deform2d.bn"], 4),
    ];

    for (candidates, expected_graphs) in files {
        let (filename, src) = read_stdlib_file(candidates);

        let file =
            parse(&src, &filename).unwrap_or_else(|e| panic!("Parse error on {}: {}", filename, e));
        assert_eq!(
            file.graphs.len(),
            *expected_graphs,
            "Unexpected graph count for {}",
            filename
        );

        let formatted = format_source(&src, &filename)
            .unwrap_or_else(|e| panic!("Formatting error on {}: {}", filename, e));

        assert_eq!(formatted, src, "Formatter mismatch on {}", filename);
    }
}

#[test]
fn test_compat_1_0_files() {
    let compat_dir = Path::new("../conformance");
    if !compat_dir.exists() {
        return;
    }

    for entry in fs::read_dir(compat_dir).unwrap() {
        let entry = entry.unwrap();
        let path = entry.path();
        if path.extension().and_then(|s| s.to_str()) == Some("bn") {
            let filename = path.file_name().unwrap().to_str().unwrap();
            let src = fs::read_to_string(&path).unwrap();
            let file = parse(&src, filename)
                .unwrap_or_else(|e| panic!("Parse error on compat {}: {}", filename, e));
            assert!(!file.graphs.is_empty());

            let formatted = format_source(&src, filename)
                .unwrap_or_else(|e| panic!("Formatting error on compat {}: {}", filename, e));

            if filename == "shapes.bn" {
                // shapes.bn contains 1.0 variants (dot, cross, ·) that the formatter canonicalizes
                let idempotent = format_source(&formatted, filename).unwrap();
                assert_eq!(
                    idempotent, formatted,
                    "Formatting not idempotent on shapes.bn"
                );
            } else {
                assert_eq!(
                    formatted, src,
                    "Formatting not character-identical on compat {}",
                    filename
                );
            }
        }
    }
}

#[test]
fn test_examples_and_fixtures() {
    let fixtures_dir = Path::new("../python/tests/fixtures");
    if fixtures_dir.exists() {
        for entry in fs::read_dir(fixtures_dir).unwrap() {
            let entry = entry.unwrap();
            let path = entry.path();
            if path.extension().and_then(|s| s.to_str()) == Some("bn") {
                let filename = path.file_name().unwrap().to_str().unwrap();
                let src = fs::read_to_string(&path).unwrap();
                let file = parse(&src, filename)
                    .unwrap_or_else(|e| panic!("Parse error on fixture {}: {}", filename, e));
                assert!(!file.graphs.is_empty());

                let formatted = format_source(&src, filename).unwrap();
                assert_eq!(
                    formatted, src,
                    "Formatting not character-identical on fixture {}",
                    filename
                );
            }
        }
    }
}

#[test]
fn test_profiles_validation() {
    let load_stdlib = |candidates: &[&str]| {
        let (filename, src) = read_stdlib_file(candidates);
        parse(&src, &filename).unwrap()
    };

    // 1. math.bn passes Core with 0 errors
    let math = load_stdlib(&["math.bn"]);
    let math_core_errors = check_profile(&math, ProfileKind::Core);
    assert!(
        math_core_errors.is_empty(),
        "math stdlib file should pass Core with 0 errors, but got: {:?}",
        math_core_errors
    );

    // 2. sdf2d.bn passes Sdf2d with 0 errors
    let sdf2d = load_stdlib(&["sdf2d.bn"]);
    let sdf2d_sdf_errors = check_profile(&sdf2d, ProfileKind::Sdf2d);
    assert!(
        sdf2d_sdf_errors.is_empty(),
        "sdf2d.bn should pass Sdf2d with 0 errors, but got: {:?}",
        sdf2d_sdf_errors
    );

    // A graph calling Position() in its body fails Core because Position is not in Core nodes
    let src_call_position = r#"
geometry graph "test_spatial"(factor: Float = 0.5) -> Vector {
  p = Position() * factor
  return p
}
"#;
    let file_spatial = parse(src_call_position, "test_spatial.bn").unwrap();
    let spatial_core_errors = check_profile(&file_spatial, ProfileKind::Core);
    assert!(
        !spatial_core_errors.is_empty(),
        "A graph calling Position() in its body must fail Core"
    );
    assert!(
        spatial_core_errors.iter().any(|e| e.contains("Position")),
        "Error message must mention Position"
    );

    let spatial_sdf_errors = check_profile(&file_spatial, ProfileKind::Sdf2d);
    assert!(
        spatial_sdf_errors.is_empty(),
        "A graph calling Position() in its body must pass Sdf2d with 0 errors: {:?}",
        spatial_sdf_errors
    );

    // 3. curves2d.bn, patterns2d.bn, and ink2d.bn pass Vector2d / Ink2d
    let curves = load_stdlib(&["curves2d.bn"]);
    let patterns = load_stdlib(&["patterns2d.bn"]);
    let ink2d = load_stdlib(&["ink2d.bn"]);

    let curves_errors = check_profile(&curves, ProfileKind::Vector2d);
    assert!(
        curves_errors.is_empty(),
        "curves2d stdlib file should pass Vector2d with 0 errors, but got: {:?}",
        curves_errors
    );

    let patterns_errors = check_profile(&patterns, ProfileKind::Vector2d);
    assert!(
        patterns_errors.is_empty(),
        "patterns2d stdlib file should pass Vector2d with 0 errors, but got: {:?}",
        patterns_errors
    );

    let ink2d_errors = check_profile(&ink2d, ProfileKind::Ink2d);
    assert!(
        ink2d_errors.is_empty(),
        "ink2d stdlib file should pass Ink2d with 0 errors, but got: {:?}",
        ink2d_errors
    );

    // They fail Core because they use Geometry or vector nodes
    assert!(!check_profile(&curves, ProfileKind::Core).is_empty());
    assert!(!check_profile(&patterns, ProfileKind::Core).is_empty());
    assert!(!check_profile(&ink2d, ProfileKind::Core).is_empty());

    // 4. Test qualified namespace calls: use ink2d as gp -> gp::living_ink(...)
    let src_qualified = r#"use ink2d as gp

geometry graph test_qualified(strokes: Geometry) -> Geometry {
  return gp::living_ink(strokes)
}
"#;
    let file_qualified = parse(src_qualified, "test_qualified.bn").unwrap();
    assert_eq!(file_qualified.uses.len(), 1);
    assert_eq!(file_qualified.uses[0].name, "ink2d");
    assert_eq!(file_qualified.uses[0].alias.as_deref(), Some("gp"));
    let qualified_errors = check_profile(&file_qualified, ProfileKind::Ink2d);
    assert!(
        qualified_errors.is_empty(),
        "Qualified module call gp::living_ink should pass Ink2d profile, but got: {:?}",
        qualified_errors
    );
    let formatted = format_source(src_qualified, "test_qualified.bn").unwrap();
    assert_eq!(formatted, src_qualified);

    // They fail Core because they use Geometry or vector nodes
    assert!(!check_profile(&curves, ProfileKind::Core).is_empty());
    assert!(!check_profile(&patterns, ProfileKind::Core).is_empty());
    assert!(!check_profile(&ink2d, ProfileKind::Core).is_empty());
}

#[test]
fn test_versioning_and_manifest() {
    assert_eq!(base_node::VERSION, "0.10.0");
    assert_eq!(base_node::EDITION, "2026");
    assert_eq!(base_node::STDLIB_VERSION, "0.10.0");

    let manifest_path = Path::new("../stdlib/manifest.json");
    let manifest_content = fs::read_to_string(manifest_path)
        .or_else(|_| fs::read_to_string("/home/marcgardent/base-node-library/stdlib/manifest.json"))
        .expect("Failed to read stdlib/manifest.json");

    let v: serde_json::Value =
        serde_json::from_str(&manifest_content).expect("Invalid JSON in manifest.json");
    assert_eq!(v["stdlib_version"], "0.10.0");
    assert_eq!(v["edition"], "2026");

    let modules = v["modules"].as_object().expect("Expected modules object");
    assert!(modules.contains_key("math"));
    assert!(modules.contains_key("sdf2d"));
    assert!(modules.contains_key("curves2d"));
    assert!(modules.contains_key("patterns2d"));
    assert!(modules.contains_key("ink2d"));
}

#[test]
fn test_profile_ascent_solving() {
    use base_node::{analyze_profile_ascent, parse, solve_minimal_profile, ProfileKind};

    // 1. Math -> Core
    let src_core =
        "geometry graph calc(a: Float, b: Float) -> Float {\n  return sin(a) + cos(b)\n}\n";
    let file_core = parse(src_core, "core.bn").unwrap();
    assert_eq!(solve_minimal_profile(&file_core), ProfileKind::Core);

    // 2. SDF with Position() -> Sdf2d
    let src_sdf = "geometry graph dist(c: Vector, r: Float) -> Float {\n  p = Position()\n  return length(p - c) - r\n}\n";
    let file_sdf = parse(src_sdf, "sdf.bn").unwrap();
    assert_eq!(solve_minimal_profile(&file_sdf), ProfileKind::Sdf2d);

    // 3. Curves -> Vector2d
    let src_vec = "geometry graph circ(r: Float = 1.0) -> Geometry {\n  c = CurveCircle(radius: r)\n  return c.curve\n}\n";
    let file_vec = parse(src_vec, "vec.bn").unwrap();
    assert_eq!(solve_minimal_profile(&file_vec), ProfileKind::Vector2d);

    // 4. Ink2d with Grease Pencil
    let src_ink = "use ink2d as gp\n\ngeometry graph ink(s: Geometry) -> Geometry {\n  return gp::living_ink(s, speed: 1.0)\n}\n";
    let file_ink = parse(src_ink, "ink.bn").unwrap();
    assert_eq!(solve_minimal_profile(&file_ink), ProfileKind::Ink2d);

    // 5. Ascent analysis with barriers
    let analysis = analyze_profile_ascent(&file_vec);
    assert_eq!(analysis.minimal_profile, ProfileKind::Vector2d);
    assert!(analysis.barriers.contains_key("core"));
    assert!(analysis.barriers.contains_key("sdf2d"));
    assert!(!analysis.barriers.contains_key("vector2d"));
}
