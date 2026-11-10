use std::fs;
use std::path::Path;

use base_node::{check_profile, format_source, parse, ProfileKind};

#[test]
fn test_stdlib_conformance() {
    let files = [
        ("maths.bn", 47),
        ("sdf2d.bn", 17),
        ("courbes2d.bn", 7),
        ("motifs2d.bn", 5),
        ("gp_outils2d.bn", 4),
    ];

    for (filename, expected_graphs) in files {
        let path = format!("../stdlib/{}", filename);
        let src = fs::read_to_string(&path)
            .or_else(|_| fs::read_to_string(format!("/home/marcgardent/base-node-library/stdlib/{}", filename)))
            .unwrap_or_else(|e| panic!("Impossible de lire {} : {}", path, e));

        let file = parse(&src, filename).unwrap_or_else(|e| panic!("Erreur de parse sur {} : {}", filename, e));
        assert_eq!(
            file.graphs.len(),
            expected_graphs,
            "Nombre de graphes inattendu pour {}",
            filename
        );

        let formatted = format_source(&src, filename)
            .unwrap_or_else(|e| panic!("Erreur de formatage sur {} : {}", filename, e));

        assert_eq!(formatted, src, "Formateur non identique sur {}", filename);
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
                .unwrap_or_else(|e| panic!("Erreur de parse sur compat {} : {}", filename, e));
            assert!(!file.graphs.is_empty());

            let formatted = format_source(&src, filename)
                .unwrap_or_else(|e| panic!("Erreur de formatage sur compat {} : {}", filename, e));

            if filename == "formes.bn" {
                // formes.bn contient des variantes 1.0 (dot, cross, ·) que le formateur canonise
                let idempotent = format_source(&formatted, filename).unwrap();
                assert_eq!(idempotent, formatted, "Formatage non idempotent sur formes.bn");
            } else {
                assert_eq!(
                    formatted, src,
                    "Formatage non identique caractère pour caractère sur compat {}",
                    filename
                );
            }
        }
    }
}

#[test]
fn test_examples_and_fixtures() {
    let examples = [
        "/home/marcgardent/marcs-blender-library/docs/exemples/rochers.bn",
        "/home/marcgardent/marcs-blender-library/docs/exemples/serpent.bn",
        "/home/marcgardent/marcs-blender-library/docs/exemples/herbe.bn",
    ];

    for path_str in examples {
        let path = Path::new(path_str);
        if !path.exists() {
            continue;
        }
        let filename = path.file_name().unwrap().to_str().unwrap();
        let src = fs::read_to_string(path).unwrap();
        let file = parse(&src, filename).unwrap_or_else(|e| panic!("Erreur de parse sur {} : {}", filename, e));
        assert!(!file.graphs.is_empty());

        let formatted = format_source(&src, filename).unwrap();
        assert_eq!(
            formatted, src,
            "Formatage non identique caractère pour caractère sur {}",
            filename
        );
    }

    let fixtures_dir = Path::new("../python/tests/fixtures");
    if fixtures_dir.exists() {
        for entry in fs::read_dir(fixtures_dir).unwrap() {
            let entry = entry.unwrap();
            let path = entry.path();
            if path.extension().and_then(|s| s.to_str()) == Some("bn") {
                let filename = path.file_name().unwrap().to_str().unwrap();
                let src = fs::read_to_string(&path).unwrap();
                let file = parse(&src, filename)
                    .unwrap_or_else(|e| panic!("Erreur de parse sur fixture {} : {}", filename, e));
                assert!(!file.graphs.is_empty());

                let formatted = format_source(&src, filename).unwrap();
                assert_eq!(
                    formatted, src,
                    "Formatage non identique caractère pour caractère sur fixture {}",
                    filename
                );
            }
        }
    }
}

#[test]
fn test_profiles_validation() {
    let load_stdlib = |name: &str| {
        let path = format!("../stdlib/{}", name);
        let src = fs::read_to_string(&path)
            .or_else(|_| fs::read_to_string(format!("/home/marcgardent/base-node-library/stdlib/{}", name)))
            .unwrap();
        parse(&src, name).unwrap()
    };

    // 1. maths.bn passe Core avec 0 erreur
    let maths = load_stdlib("maths.bn");
    let maths_core_errors = check_profile(&maths, ProfileKind::Core);
    assert!(
        maths_core_errors.is_empty(),
        "maths.bn devrait passer Core avec 0 erreur, mais a : {:?}",
        maths_core_errors
    );

    // 2. sdf2d.bn passe Sdf2d avec 0 erreur
    let sdf2d = load_stdlib("sdf2d.bn");
    let sdf2d_sdf_errors = check_profile(&sdf2d, ProfileKind::Sdf2d);
    assert!(
        sdf2d_sdf_errors.is_empty(),
        "sdf2d.bn devrait passer Sdf2d avec 0 erreur, mais a : {:?}",
        sdf2d_sdf_errors
    );

    // Un graphe qui utilise Position() dans son body échoue sur Core car Position n'est pas dans les nœuds de Core
    let src_call_position = r#"
geometry graph "test_spatial"(facteur: Float = 0.5) -> Vector {
  p = Position() * facteur
  return p
}
"#;
    let file_spatial = parse(src_call_position, "test_spatial.bn").unwrap();
    let spatial_core_errors = check_profile(&file_spatial, ProfileKind::Core);
    assert!(
        !spatial_core_errors.is_empty(),
        "Un graphe appelant Position() dans son body doit échouer sur Core"
    );
    assert!(
        spatial_core_errors.iter().any(|e| e.contains("Position")),
        "L'erreur doit mentionner Position"
    );

    let spatial_sdf_errors = check_profile(&file_spatial, ProfileKind::Sdf2d);
    assert!(
        spatial_sdf_errors.is_empty(),
        "Un graphe appelant Position() dans son body doit passer sur Sdf2d avec 0 erreur : {:?}",
        spatial_sdf_errors
    );

    // 3. courbes2d.bn, motifs2d.bn et gp_outils2d.bn passent Vector2d avec 0 erreur
    let courbes = load_stdlib("courbes2d.bn");
    let motifs = load_stdlib("motifs2d.bn");
    let gp_outils = load_stdlib("gp_outils2d.bn");

    let courbes_errors = check_profile(&courbes, ProfileKind::Vector2d);
    assert!(
        courbes_errors.is_empty(),
        "courbes2d.bn devrait passer Vector2d avec 0 erreur, mais a : {:?}",
        courbes_errors
    );

    let motifs_errors = check_profile(&motifs, ProfileKind::Vector2d);
    assert!(
        motifs_errors.is_empty(),
        "motifs2d.bn devrait passer Vector2d avec 0 erreur, mais a : {:?}",
        motifs_errors
    );

    let gp_errors = check_profile(&gp_outils, ProfileKind::Vector2d);
    assert!(
        gp_errors.is_empty(),
        "gp_outils2d.bn devrait passer Vector2d avec 0 erreur, mais a : {:?}",
        gp_errors
    );

    // Ils échouent sur Core car ils utilisent Geometry ou des nœuds vectoriels
    assert!(!check_profile(&courbes, ProfileKind::Core).is_empty());
    assert!(!check_profile(&motifs, ProfileKind::Core).is_empty());
    assert!(!check_profile(&gp_outils, ProfileKind::Core).is_empty());
}
