# Base Node (`.bn`) : Spécification et référence du langage

La référence formelle du langage `.bn` (**Base Node / Nodes as Text**), version 1.0.  
Elle décrit la grammaire, la syntaxe, la sémantique de chaque construction, ainsi que la promesse de compatibilité multi-hôtes (Blender, Blade, Graphite).

---

## 1. Structure d'un fichier `.bn`

Un document `.bn` est une suite d'instructions déclaratives encodées en UTF-8 :

1. Des déclarations de modules `use`, facultatives, en tête de fichier ;
2. Une suite d'un ou plusieurs graphes (`graph`), chacun définissant un groupe de nœuds réutilisable.

`//` introduit un commentaire unitaire jusqu'à la fin de la ligne courante (hors chaînes de caractères).  
Les espaces, tabulations et sauts de ligne ne sont pas significatifs en dehors des littéraux : une instruction se termine dès lors que le lexème suivant ne peut syntaxiquement pas la poursuivre.

```
use maths (bosse)

// Un relief en bosse au centre d'une grille
geometry graph relief(geometry: Geometry, hauteur: Float = 0.4) -> Geometry {
  "Soulève le centre"
  h = bosse(length(Position()) / 3.0, 0.5, 0.2) * hauteur
  return SetPosition(geometry, offset: CombineXYZ(z: h))
}
```

---

## 2. Identifiants et lexique

- **Identifiant standard** : séquence de lettres (y compris caractères accentués UTF-8), chiffres et `_`, ne commençant pas par un chiffre (`hauteur`, `fréquence_2`, `p`).
- **Identifiant libre (entre guillemets)** : toute chaîne de caractères entre guillemets doubles `"Point Count"`. Dans le corps d'un graphe, un tel nom est référencé par sa clé canonique en `snake_case` (`point_count`).
- **Mots réservés** : `graph`, `return`, `true`, `false`, `and`, `or`, `xor`, `not`, `repeat`, `dot`, `cross`. Un socket ou identifiant hôte portant un nom réservé prend un suffixe `_` (`not_`).
- **Mots contextuels** :
  - `use` et `from` ne sont des mots-clés qu'en tête de fichier ;
  - `simulate` et `foreach` ne sont reconnus comme mots-clés que devant `(…) {` ;
  - `closure` n'ouvre une zone Closure que sous la forme `nom = closure(…) -> … {` ;
  - `_` (tiret bas seul) désigne l'absence explicite de valeur pour un item neutre.
- **Valeurs scalaires et symboliques** : tout nom qui n'est ni une variable ni une entrée définie est résolu comme une valeur d'énumération ou de menu (`domain: FACE`, `operation: POWER`, `mode: Lisse`).

---

## 3. Déclaration de graphe (`graph`)

```
[genre] [(options)] graph nom(entrées…) -> sorties {
    corps…
}
```

- **`genre`** : type de graphe (`geometry`, `shader`, `compositor`, `vector`, `pixel`).
- **`options`** : attributs du graphe sous forme de paires clé-valeur :
  `geometry(is_tool: true, is_mode_edit: true) graph nom(…)`.
- **`nom`** : identifiant du groupe.
- **`sorties`** :
  - Sortie unique typée : `-> Type` (nommée implicitement selon son type) ;
  - Sorties multiples ou nommées : `-> (nom: Type, …)`.
- **Description** : une chaîne littérale en première instruction du corps documente le graphe (infobulle / métadonnées d'asset).

### 3.1 Système de types

| Type canonique | Description | Valeur par défaut type |
|---|---|---|
| `Float` | Flottant scalaire 32/64 bits | `0.5` |
| `Int` | Entier relatif 32/64 bits | `3` |
| `Bool` | Booléen logique | `true`, `false` |
| `Vector` | Vecteur spatial 2D, 3D ou 4D | `(1.0, 0.0, 0.0)` |
| `Color` | Couleur RGBA | `(1.0, 0.5, 0.0)` ou avec alpha `(1.0, 0.5, 0.0, 1.0)` |
| `Rotation` | Rotation eulérienne / quaternion | `(0.0, 0.0, 1.57)` |
| `Matrix` | Matrice de transformation affine | Identité |
| `String` | Chaîne de caractères UTF-8 | `""` |
| `Menu` | Sélecteur énumératif d'interface | Entrée textuelle ou item d'énumération |
| `Geometry` | Données géométriques (maillages, courbes, points, instances) | — |
| `Image` | Données matricielles / pixels 2D | — |
| `Material` | Référence de matériau hôte | — |
| `Bundle` | Conteneur composite de sockets dynamiques | — |
| `Closure` | Fonction ou sous-graphe différé capturé | — |

### 3.2 Entrées et sorties

```
nom: Type(options…) = valeur_defaut in min..max
```

- **`= valeur_defaut`** : valeur par défaut en cas de socket non connecté.  
  Supporte les appels implicites contextuels : `p: Vector = Position()`, `Normal()`, `Index()`, `ID()`.
- **`in min..max`** : bornes numériques (inclusives). Une borne peut être infinie : `in 0.0..`, `in ..1.0`.
- **`(options…)`** : métadonnées et sous-types hôte :  
  `subtype: FACTOR`, `subtype: DISTANCE`, `subtype: ANGLE`, `structure_type: SINGLE`, `hide_in_modifier: true`, `description: "..."`.

### 3.3 Panneaux d'interface (`panel`)

Les paramètres peuvent être hiérarchisés en panneaux arborescents :

```
geometry graph semis(
    geometry: Geometry,
    densité: Float = 10.0,
    "Taille"(description: "Contrôle d'échelle") {
        échelle: Float = 1.0,
        "Aléa"(default_closed: true) {
            Aléa: Bool(is_panel_toggle: true),
            échelle as aléa_échelle: Float = 0.2 in 0.0..1.0,
            graine: Int
        }
    }
) -> (
    Geometry: Geometry,
    "Sorties secondaires" {
        Hauteur: Float
    }
) { … }
```

- **`"Titre" { … }`** : regroupe les entrées/sorties au sein d'un panneau. Les panneaux peuvent être imbriqués sans limitation de profondeur.
- **`is_panel_toggle: true`** : associe une entrée booléenne au commutateur actif du panneau.
- **Clé d'item `as`** : permet de désambiguïser deux sockets portant le même libellé d'affichage : `échelle as aléa_échelle: Float`.

---

## 4. Instructions et corps du graphe

Le corps d'un graphe est une séquence d'assignations, de blocs structurels et d'une instruction finale de retour :

| Syntaxe | Rôle |
|---|---|
| `nom = expression` | Calcule et nomme une expression. |
| `return expression` | Sortie unique du graphe. |
| `return (Sortie1: e1, Sortie2: e2, …)` | Sorties multiples nommées. |
| `"Titre" #couleur { … }` | Bloc structurel visuel (Frame). Couleur hexadécimale `#e73` ou CSS `#teal`. |
| `"Note" #couleur {}` | Note documentaire autonome sans instructions. |
| `"Titre" .. { … }` | Continuation `..` d'un cadre visuel déjà ouvert plus haut dans le bloc. |
| `nom = repeat(…) { … }` | Boucle itérative à état persistant. |
| `nom = simulate(…) { … }` | Zone temporelle physique par pas de temps. |
| `nom = foreach(…) { … }` | Zone d'évaluation vectorielle par élément géométrique. |
| `nom = closure(…) -> … { … }` | Zone de capture de calcul différé (Closure). |

### 4.1 Présentation d'un nœud (`@`)

Une instruction peut annoter la représentation visuelle du nœud généré à l'aide de `@` :

```
p = Position() @ hide
h = sin(p.x) @ "Altitude" #e07030
out = SetPosition(g, offset: o) @ #orange hide mute
return out @ "SortieFinale"
```

Attributs supportés :
- `"Libellé"` : libellé visuel personnalisé ;
- `#hex` / `#css` : couleur d'accentuation du nœud ;
- `hide` : nœud rétracté/replié ;
- `mute` : nœud désactivé (laisse transiter sa première entrée).

---

## 5. Expressions et opérateurs

### 5.1 Nœuds et appels

```
Sortie = NomDuNœud(arg1, arg2, nom: arg3, propriété: VALEUR)
```

- Les arguments positionnels alimentent les entrées dans l'ordre naturel.
- Les arguments nommés ciblent un socket précis ou une propriété interne (`operation: ADD`, `data_type: FLOAT`).
- L'accès aux sorties multiples s'écrit `nom.sortie` (ex: `sample.value`, `pt.rotation`).
- L'accès aux composantes vectorielles s'écrit `v.x`, `v.y`, `v.z`.

### 5.2 Opérateur de chaînage (`|>`)

L'opérateur pipe `|>` injecte le résultat de gauche comme premier argument de l'appel de droite :

```
maillage |> SubdivideCurve(3)
         |> SetCurveRadius(rayon: 0.1)
         |> CurveToMesh()
```

### 5.3 Formules arithmétiques et logiques

Les expressions algébriques sont automatiquement abaissées vers les nœuds d'opérations correspondants :

- **Arithmétique** : `+`, `-`, `*`, `/`, `-a` (`Math` ou `VectorMath`)
- **Produits vectoriels** : `u ⋅ v` (ou `u dot v`), `u × v` (ou `u cross v`)
- **Comparaisons** : `<`, `<=`, `>`, `>=`, `==`, `!=` (`Compare`)
- **Logique booléenne** : `and`, `or`, `xor`, `not`, `nand`, `nor`, `xnor` (`BooleanMath`)
- **Fonctions mathématiques** : `sin`, `cos`, `tan`, `asin`, `acos`, `atan`, `atan2`, `sqrt`, `pow`, `exp`, `log`, `abs`, `min`, `max`, `clamp`, `floor`, `ceil`, `fract`, `mod`, `length`, `normalize`, `distance`.

---

## 6. Zones et structures de contrôle

### 6.1 Zone `repeat`

```
r = repeat(tours, état: valeur_initiale, …) {
    suivant = état * 1.5
    return (état: suivant, …)
}
final = r.état
```

### 6.2 Zone `foreach`

```
res = foreach(géométrie, domain: FACE, p: Position()) {
    centre = p * 0.5
    return (points: Points(position: centre))
}
```

### 6.3 Bundles et closures

```
f = closure(x: Float) -> (res: Float) {
    return x * 2.0
}
b = CombineBundle(facteur: 3.14, func: f)
sep = SeparateBundle(b) -> (facteur: Float, func: Closure)
val = EvaluateClosure(sep.func, x: 10.0) -> (res: Float)
```

---

## 7. Profils de compatibilité formels

Pour garantir la portabilité des bibliothèques `.bn` entre différents moteurs d'exécution, le langage définit 5 profils hiérarchiques déclaratifs dans `profiles/` :

1. **`core`** : Algèbre, trigonométrie, logique pure et zone `repeat`. Indépendant de toute géométrie 3D ou moteur particulier.
2. **`sdf2d`** : Élargit `core` aux entrées spatiales 2D (`Position`, `Normal`, `Index`, `ID`).
3. **`vector2d`** : Élargit `sdf2d` aux types `Geometry`, `Material`, aux générateurs et transformateurs de courbes et surfaces 2D, et à la zone `foreach`.
4. **`raster2d`** : Élargit `sdf2d` au traitement matriciel d'images et composition de pixels (`Image`, filtres, convolutions).
5. **`blender-geometry`** : Profil complet couvrant l'ensemble des 120+ nœuds Blender Geometry Nodes, volumes, champs 3D et closures.
