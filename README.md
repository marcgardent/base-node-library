# Base Node Library (`.bn`)

> **Nodes as Text** — Format de texte déclaratif universel et bibliothèque de graphes de nœuds pour le graphisme procédural 2D/3D (Blender Geometry Nodes, Blade, Graphite).

`base-node-library` fournit la spécification du langage `.bn`, un corpus de conformité multi-implémentation, des profils de compatibilité hiérarchiques, ainsi que des implémentations de référence en Python et en Rust.

---

## Architecture du dépôt

Le dépôt est organisé en plusieurs sous-projets indépendants et interopérables :

- **`spec/`** : Spécification formelle du langage `.bn` (grammaire, règles sémantiques, types, zones, panneaux).
- **`conformance/`** : Corpus de conformité et suites de tests multi-implémentation avec manifeste JSON (`manifest.json`) partagé entre `pytest` et `cargo test`.
- **`profiles/`** : Profils de compatibilité déclaratifs hiérarchiques (`core`, `sdf2d`, `vector2d`, `raster2d`, `blender-geometry`).
- **`stdlib/`** : Bibliothèque standard sous double licence MIT / Apache-2.0 :
  - `maths.bn` : fonctions scalaires, vectorielles, bruit et SDF analytiques universelles.
  - `sdf2d.bn` : primitives et opérations 2D pour champs de distance signée.
  - `courbes2d.bn` : primitives, profils, échantillonnage et déformation de courbes.
  - `motifs2d.bn` : pavages, grilles, distributions régulières et semis de points.
  - `gp_outils2d.bn` : outils de stylisation et habillage vectoriel.
- **`python/`** : Package Python pur zéro-dépendance (`base_node`) incluant le lexer, parser, formateur, vérificateur de type, validateur de profil et la CLI `base-node`.
- **`rust/`** : Bibliothèque Rust haute performance pour l'analyse lexicale, syntaxique et la validation de profils dans les moteurs natifs (Blade, Graphite).
- **`base-node-for-blender/`** : Extension Blender 5.2+ / 5.3+ (`base_node`, alias `bnodes`) synchronisée avec le cœur `base_node` et offrant l'éditeur bidirectionnel texte ⇄ graphe.

---

## Profils de compatibilité

Les profils hiérarchiques permettent de restreindre et valider le sous-ensemble de fonctionnalités utilisable selon la cible d'exécution :

1. **`core`** (`profiles/core.json`) :
   - Socle mathématique et logique pur (`Float`, `Int`, `Bool`, `Vector`, `Color`, `Rotation`, `Matrix`, `String`, `Menu`).
   - Opérateurs arithmétiques, comparaisons, bruit, switches, zone `repeat`.
   - Universellement portable (Blender Geometry/Shader/Compositor, Blade, Graphite, shaders). 100 % compatible avec `stdlib/maths.bn`.
2. **`sdf2d`** (`profiles/sdf2d.json`, étend `core`) :
   - Ajoute les entrées contextuelles et nœuds spatiaux 2D (`Position`, `Normal`, `Index`, `ID`).
   - Cible les shaders 2D et les graphes de pixels/vecteurs. 100 % compatible avec `stdlib/sdf2d.bn`.
3. **`vector2d`** (`profiles/vector2d.json`, étend `sdf2d`) :
   - Ajoute les types `Geometry`, `Material` et tous les opérateurs 2D courbes, maillages, points, instances et attributs.
   - Zone `foreach`.
   - Cible `bf-vector` de Blade, Graphite et Blender. 100 % compatible avec `stdlib/courbes2d.bn`, `stdlib/motifs2d.bn` et `stdlib/gp_outils2d.bn`.
4. **`raster2d`** (`profiles/raster2d.json`, étend `sdf2d`) :
   - Ajoute le type `Image` et les opérateurs raster (modes de fusion, flous, classification, vectorisation, pixellisation).
   - Cible `bf-raster` de Blade et Blender Compositor.
5. **`blender-geometry`** (`profiles/blender-geometry.json`, étend `vector2d`) :
   - Profil hôte complet Geometry Nodes Blender 5.2+ / 5.3+ (`allow_all_blender_nodes: true`).
   - Supporte la 3D, les volumes, les zones `simulate`, `closure` et les `Bundle`.

---

## Utilisation rapide en Python

```bash
cd python
pip install -e .

# Formater un fichier .bn
base-node fmt file.bn

# Vérifier le formatage canonique
base-node fmt --check file.bn

# Vérifier la syntaxe et un profil de compatibilité
base-node check --profile vector2d stdlib/courbes2d.bn

# Inspecter l'AST en JSON
base-node ast file.bn
```

En code Python :
```python
import base_node as bn

# Analyse syntaxique
ast = bn.parse("geometry graph f(x: Float) -> Float { return x * 2.0 }")

# Formatage
code = bn.format_source(text)

# Vérification de profil
profile = bn.load_profile("vector2d")
errors = bn.check_profile(graphs, profile="vector2d")
```

---

## Extension Blender

L'extension Blender se trouve dans `base-node-for-blender/` (identifiant `base_node`, alias `bnodes`). Elle offre :
- Rétrocompatibilité complète avec `import bnodes` et `NodeTree.bnodes`.
- Intégration dans le volet latéral de l'éditeur de texte et de l'éditeur de nœuds.
- Aller-retour bidirectionnel immédiat `Tree → Text` et `Text → Tree`.
- Raccourcis clavier (`Ctrl+Entrée` pour synchroniser, `Ctrl+Espace` pour la complétion).

---

## Licences

- Cœur de la bibliothèque (`spec/`, `conformance/`, `profiles/`, `stdlib/`, `python/`, `rust/`) :  
  Double licence **MIT** (`LICENSE-MIT`) ou **Apache-2.0** (`LICENSE-APACHE`), au choix de l'utilisateur (`SPDX-License-Identifier: MIT OR Apache-2.0`).
- Connecteur d'extension Blender (`base-node-for-blender/host/`, `ui/`) :  
  Licence **GPL-3.0-or-later** conformément aux exigences de l'API Python de Blender.
