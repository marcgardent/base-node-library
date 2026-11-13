use base_node::{format_source, parse};

const SIMULATE: &str = r#"geometry graph g(geometry: Geometry) -> Geometry {
  s = simulate(mesh: geometry, "Delta Time" as delta_time_2: 0.0) {
    return (mesh: mesh, delta_time_2: delta_time_2 + delta_time)
  }
  return s.mesh
}
"#;

#[test]
fn a_state_takes_a_key_of_its_own() {
    // A state named like the zone's own name, as Blender lets one call it, goes by a key
    parse(SIMULATE, "t.bn").expect("simulate state with a key");
    assert_eq!(format_source(SIMULATE, "t.bn").expect("formats"), SIMULATE);
    let repeat = "geometry graph g(geometry: Geometry) -> Geometry {\n  r = repeat(2, Iteration as it: 0.0) {\n    return it\n  }\n  return geometry\n}\n";
    parse(repeat, "t.bn").expect("repeat state with a key");
}

#[test]
fn a_foreach_item_takes_no_key_yet() {
    let src = "geometry graph g(geometry: Geometry) -> Geometry {\n  e = foreach(geometry, a as b: 0.0) {\n    return ()\n  }\n  return e\n}\n";
    assert!(parse(src, "t.bn").is_err());
}
