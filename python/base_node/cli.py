"""Interface en ligne de commande (CLI) pour base-node.

Commandes supportées :
  base-node fmt [--check] <fichiers.bn>
  base-node parse <fichiers.bn>
  base-node check [--profile <nom>] <fichiers.bn>
  base-node ast <fichier.bn>
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from .errors import BnError
from .format import format_source
from .parser import parse
from .profiles import check_profile, load_profile


def _serialize_ast(obj: Any) -> Any:
    """Convertit l'AST de dataclasses en structures JSON sérialisables."""
    if is_dataclass(obj):
        d = asdict(obj)
        d["__class__"] = obj.__class__.__name__
        return d
    if isinstance(obj, (list, tuple)):
        return [_serialize_ast(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _serialize_ast(v) for k, v in obj.items()}
    return obj


def cmd_fmt(args: argparse.Namespace) -> int:
    """Formate les fichiers .bn ou vérifie leur formatage canonique."""
    exit_code = 0
    for path_str in args.files:
        p = Path(path_str)
        if not p.is_file():
            print(f"Erreur : fichier introuvable '{path_str}'", file=sys.stderr)
            exit_code = 1
            continue
        try:
            content = p.read_text(encoding="utf-8")
            formatted = format_source(content)
            if args.check:
                if content != formatted:
                    print(f"Non formaté : {path_str}", file=sys.stderr)
                    exit_code = 1
                else:
                    print(f"OK (formaté) : {path_str}")
            else:
                if content != formatted:
                    p.write_text(formatted, encoding="utf-8")
                    print(f"Formaté : {path_str}")
                else:
                    print(f"Inchangé : {path_str}")
        except BnError as err:
            print(f"Erreur de syntaxe dans '{path_str}' :\n{err}", file=sys.stderr)
            exit_code = 1
        except Exception as ex:
            print(f"Erreur lors du traitement de '{path_str}' : {ex}", file=sys.stderr)
            exit_code = 1
    return exit_code


def cmd_parse(args: argparse.Namespace) -> int:
    """Analyse syntaxiquement les fichiers .bn."""
    exit_code = 0
    for path_str in args.files:
        p = Path(path_str)
        if not p.is_file():
            print(f"Erreur : fichier introuvable '{path_str}'", file=sys.stderr)
            exit_code = 1
            continue
        try:
            content = p.read_text(encoding="utf-8")
            file_ast = parse(content, p.name)
            count = len(file_ast.graphs)
            print(f"Syntaxe valide : {path_str} ({count} graphe{'s' if count > 1 else ''})")
        except BnError as err:
            print(f"Erreur de syntaxe dans '{path_str}' :\n{err}", file=sys.stderr)
            exit_code = 1
        except Exception as ex:
            print(f"Erreur inattendue dans '{path_str}' : {ex}", file=sys.stderr)
            exit_code = 1
    return exit_code


def cmd_check(args: argparse.Namespace) -> int:
    """Vérifie la syntaxe et la compatibilité du profil pour chaque fichier .bn."""
    exit_code = 0
    try:
        prof = load_profile(args.profile)
    except Exception as ex:
        print(f"Erreur lors du chargement du profil '{args.profile}' : {ex}", file=sys.stderr)
        return 1

    for path_str in args.files:
        p = Path(path_str)
        if not p.is_file():
            print(f"Erreur : fichier introuvable '{path_str}'", file=sys.stderr)
            exit_code = 1
            continue
        try:
            content = p.read_text(encoding="utf-8")
            file_ast = parse(content, p.name)
            errors = check_profile(file_ast.graphs, profile=prof)
            if errors:
                print(f"Erreurs de profil dans '{path_str}' (profil '{args.profile}') :", file=sys.stderr)
                for e in errors:
                    print(f"  - {e}", file=sys.stderr)
                exit_code = 1
            else:
                print(f"OK (profil {args.profile}) : {path_str}")
        except BnError as err:
            print(f"Erreur de syntaxe dans '{path_str}' :\n{err}", file=sys.stderr)
            exit_code = 1
        except Exception as ex:
            print(f"Erreur inattendue dans '{path_str}' : {ex}", file=sys.stderr)
            exit_code = 1
    return exit_code


def cmd_ast(args: argparse.Namespace) -> int:
    """Exporte l'AST d'un fichier .bn sous forme de document JSON."""
    p = Path(args.file)
    if not p.is_file():
        print(f"Erreur : fichier introuvable '{args.file}'", file=sys.stderr)
        return 1
    try:
        content = p.read_text(encoding="utf-8")
        file_ast = parse(content, p.name)
        data = _serialize_ast(file_ast)
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0
    except BnError as err:
        print(f"Erreur de syntaxe dans '{args.file}' :\n{err}", file=sys.stderr)
        return 1
    except Exception as ex:
        print(f"Erreur inattendue dans '{args.file}' : {ex}", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="base-node",
        description="Base Node (.bn) — Outil CLI pour la manipulation de graphes de nœuds",
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # fmt
    parser_fmt = subparsers.add_parser("fmt", help="Formate des fichiers .bn")
    parser_fmt.add_argument("--check", action="store_true", help="Vérifie le formatage sans modifier les fichiers")
    parser_fmt.add_argument("files", nargs="+", help="Fichiers .bn à formater")
    parser_fmt.set_defaults(func=cmd_fmt)

    # parse
    parser_parse = subparsers.add_parser("parse", help="Vérifie la syntaxe de fichiers .bn")
    parser_parse.add_argument("files", nargs="+", help="Fichiers .bn à analyser")
    parser_parse.set_defaults(func=cmd_parse)

    # check
    parser_check = subparsers.add_parser("check", help="Vérifie la syntaxe et un profil de compatibilité")
    parser_check.add_argument(
        "--profile", default="vector2d", help="Nom du profil de compatibilité (défaut : vector2d)"
    )
    parser_check.add_argument("files", nargs="+", help="Fichiers .bn à vérifier")
    parser_check.set_defaults(func=cmd_check)

    # ast
    parser_ast = subparsers.add_parser("ast", help="Exporte l'AST en JSON")
    parser_ast.add_argument("file", help="Fichier .bn à exporter")
    parser_ast.set_defaults(func=cmd_ast)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
