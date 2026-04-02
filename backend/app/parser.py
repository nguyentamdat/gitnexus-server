"""Tree-sitter based code parser."""

from dataclasses import dataclass
from typing import List, Dict, Optional, Any
from pathlib import Path
import tree_sitter_python as tspython
import tree_sitter_javascript as tsjavascript
import tree_sitter_typescript as tstypescript
import tree_sitter_go as tsgo
import tree_sitter_rust as tsrust
import tree_sitter_java as tsjava
from tree_sitter import Language, Parser, Tree, Node
import structlog

logger = structlog.get_logger()


@dataclass
class Symbol:
    """Extracted code symbol."""
    name: str
    symbol_type: str  # function, class, method, interface, variable, etc.
    qualified_name: Optional[str] = None
    start_line: int = 0
    end_line: int = 0
    start_column: int = 0
    end_column: int = 0
    docstring: Optional[str] = None
    is_entry_point: bool = False
    is_async: bool = False
    is_exported: bool = False
    parameters: List[str] = None
    return_type: Optional[str] = None
    decorators: List[str] = None
    
    def __post_init__(self):
        if self.parameters is None:
            self.parameters = []
        if self.decorators is None:
            self.decorators = []


@dataclass
class Import:
    """Extracted import statement."""
    source: str
    symbols: List[str]
    is_relative: bool = False
    line: int = 0


@dataclass
class FileParseResult:
    """Result of parsing a source file."""
    language: str
    symbols: List[Symbol]
    imports: List[Import]
    references: List[Dict[str, Any]]  # Symbol references (calls, etc.)
    
    # Metadata
    total_lines: int = 0
    complexity_score: float = 0.0


class TreeSitterParser:
    """Multi-language code parser using Tree-sitter."""
    
    # Language to file extension mapping
    LANGUAGE_EXTENSIONS = {
        "python": [".py"],
        "javascript": [".js", ".mjs"],
        "typescript": [".ts", ".tsx"],
        "go": [".go"],
        "rust": [".rs"],
        "java": [".java"],
        "c": [".c", ".h"],
        "cpp": [".cpp", ".hpp", ".cc", ".hh"],
        "ruby": [".rb"],
        "php": [".php"],
    }
    
    def __init__(self):
        self.parsers: Dict[str, Parser] = {}
        self._init_parsers()
    
    def _init_parsers(self):
        """Initialize Tree-sitter parsers for supported languages."""
        language_modules = {
            "python": tspython,
            "javascript": tsjavascript,
            "typescript": tstypescript,
            "go": tsgo,
            "rust": tsrust,
            "java": tsjava,
        }
        
        for lang_name, module in language_modules.items():
            try:
                language = Language(module.language())
                parser = Parser()
                parser.set_language(language)
                self.parsers[lang_name] = parser
                logger.info(f"parser_initialized", language=lang_name)
            except Exception as e:
                logger.warning(f"parser_init_failed", language=lang_name, error=str(e))
    
    def detect_language(self, file_path: str) -> Optional[str]:
        """Detect programming language from file extension."""
        path = Path(file_path)
        ext = path.suffix.lower()
        
        for lang, extensions in self.LANGUAGE_EXTENSIONS.items():
            if ext in extensions:
                return lang
        
        return None
    
    def parse_file(self, file_path: str, content: str) -> Optional[FileParseResult]:
        """
        Parse a source file and extract symbols, imports, and references.
        
        Args:
            file_path: Path to the file (for language detection)
            content: File content as string
        
        Returns:
            FileParseResult or None if parsing failed
        """
        language = self.detect_language(file_path)
        if not language:
            logger.debug("unknown_language", path=file_path)
            return None
        
        if language not in self.parsers:
            logger.debug("parser_not_available", language=language, path=file_path)
            return None
        
        try:
            parser = self.parsers[language]
            tree = parser.parse(bytes(content, "utf8"))
            
            # Extract based on language
            if language == "python":
                return self._parse_python(file_path, content, tree)
            elif language in ("javascript", "typescript"):
                return self._parse_js_ts(file_path, content, tree, language)
            elif language == "go":
                return self._parse_go(file_path, content, tree)
            elif language == "rust":
                return self._parse_rust(file_path, content, tree)
            elif language == "java":
                return self._parse_java(file_path, content, tree)
            else:
                return FileParseResult(
                    language=language,
                    symbols=[],
                    imports=[],
                    references=[],
                    total_lines=len(content.splitlines())
                )
                
        except Exception as e:
            logger.error("parse_failed", path=file_path, language=language, error=str(e))
            return None
    
    def _parse_python(self, file_path: str, content: str, tree: Tree) -> FileParseResult:
        """Parse Python source file."""
        symbols = []
        imports = []
        references = []
        
        root = tree.root_node
        lines = content.splitlines()
        
        def traverse(node: Node, depth=0):
            # Function definitions
            if node.type == "function_definition":
                name_node = node.child_by_field_name("name")
                if name_node:
                    symbol = Symbol(
                        name=name_node.text.decode('utf8'),
                        symbol_type="function",
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        start_column=node.start_point[1],
                        end_column=node.end_point[1],
                        is_entry_point=depth == 0
                    )
                    
                    # Extract docstring
                    body = node.child_by_field_name("body")
                    if body and body.named_child_count > 0:
                        first_stmt = body.named_child(0)
                        if first_stmt and first_stmt.type == "expression_statement":
                            expr = first_stmt.child(0)
                            if expr and expr.type == "string":
                                symbol.docstring = expr.text.decode('utf8')
                    
                    symbols.append(symbol)
            
            # Class definitions
            elif node.type == "class_definition":
                name_node = node.child_by_field_name("name")
                if name_node:
                    symbol = Symbol(
                        name=name_node.text.decode('utf8'),
                        symbol_type="class",
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        is_entry_point=False
                    )
                    symbols.append(symbol)
            
            # Import statements
            elif node.type in ("import_statement", "import_from_statement"):
                if node.type == "import_statement":
                    module = node.named_children[0] if node.named_children else None
                    if module:
                        imports.append(Import(
                            source=module.text.decode('utf8'),
                            symbols=[],
                            is_relative=False,
                            line=node.start_point[0] + 1
                        ))
                else:  # from_import
                    module = node.child_by_field_name("module")
                    if module:
                        import_source = module.text.decode('utf8')
                        # Find imported names
                        imported_names = []
                        for child in node.named_children:
                            if child.type in ("dotted_name", "identifier"):
                                imported_names.append(child.text.decode('utf8'))
                        
                        imports.append(Import(
                            source=import_source,
                            symbols=imported_names,
                            is_relative=import_source.startswith("."),
                            line=node.start_point[0] + 1
                        ))
            
            # Recurse
            for child in node.children:
                traverse(child, depth + 1)
        
        traverse(root)
        
        return FileParseResult(
            language="python",
            symbols=symbols,
            imports=imports,
            references=references,
            total_lines=len(lines),
            complexity_score=len(symbols) / max(len(lines), 1) * 100
        )
    
    def _parse_js_ts(self, file_path: str, content: str, tree: Tree, language: str) -> FileParseResult:
        """Parse JavaScript/TypeScript source file."""
        symbols = []
        imports = []
        references = []
        
        root = tree.root_node
        lines = content.splitlines()
        
        def traverse(node: Node, in_export=False):
            # Function declarations
            if node.type in ("function_declaration", "function"):
                name_node = node.child_by_field_name("name")
                if name_node:
                    symbols.append(Symbol(
                        name=name_node.text.decode('utf8'),
                        symbol_type="function",
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        is_exported=in_export,
                        is_entry_point=False
                    ))
            
            # Class declarations
            elif node.type == "class_declaration":
                name_node = node.child_by_field_name("name")
                if name_node:
                    symbols.append(Symbol(
                        name=name_node.text.decode('utf8'),
                        symbol_type="class",
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        is_exported=in_export
                    ))
            
            # Method definitions
            elif node.type == "method_definition":
                name_node = node.child_by_field_name("name")
                if name_node:
                    symbols.append(Symbol(
                        name=name_node.text.decode('utf8'),
                        symbol_type="method",
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1
                    ))
            
            # Import statements
            elif node.type in ("import_statement", "import"):
                source = None
                imported_names = []
                
                for child in node.named_children:
                    if child.type == "string":
                        source = child.text.decode('utf8').strip('"\'')
                    elif child.type in ("import_clause", "named_imports"):
                        for name in child.named_children:
                            if name.type == "identifier":
                                imported_names.append(name.text.decode('utf8'))
                
                if source:
                    imports.append(Import(
                        source=source,
                        symbols=imported_names,
                        is_relative=source.startswith("."),
                        line=node.start_point[0] + 1
                    ))
            
            # Export declarations
            elif node.type in ("export_statement", "export_declaration"):
                for child in node.named_children:
                    traverse(child, in_export=True)
            
            # Recurse
            else:
                for child in node.children:
                    traverse(child, in_export)
        
        traverse(root)
        
        return FileParseResult(
            language=language,
            symbols=symbols,
            imports=imports,
            references=references,
            total_lines=len(lines)
        )
    
    def _parse_go(self, file_path: str, content: str, tree: Tree) -> FileParseResult:
        """Parse Go source file."""
        symbols = []
        imports = []
        
        root = tree.root_node
        lines = content.splitlines()
        
        def traverse(node: Node):
            # Function declarations
            if node.type == "function_declaration":
                name_node = node.child_by_field_name("name")
                if name_node:
                    name = name_node.text.decode('utf8')
                    symbols.append(Symbol(
                        name=name,
                        symbol_type="function",
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        is_entry_point=name == "main"
                    ))
            
            # Method declarations
            elif node.type == "method_declaration":
                name_node = node.child_by_field_name("name")
                if name_node:
                    symbols.append(Symbol(
                        name=name_node.text.decode('utf8'),
                        symbol_type="method",
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1
                    ))
            
            # Type declarations (structs, interfaces)
            elif node.type == "type_declaration":
                for spec in node.named_children:
                    if spec.type == "type_spec":
                        name_node = spec.child_by_field_name("name")
                        if name_node:
                            type_node = spec.child_by_field_name("type")
                            type_kind = "type"
                            if type_node:
                                if type_node.type == "struct_type":
                                    type_kind = "struct"
                                elif type_node.type == "interface_type":
                                    type_kind = "interface"
                            
                            symbols.append(Symbol(
                                name=name_node.text.decode('utf8'),
                                symbol_type=type_kind,
                                start_line=node.start_point[0] + 1,
                                end_line=node.end_point[0] + 1
                            ))
            
            # Import declarations
            elif node.type == "import_declaration":
                for spec in node.named_children:
                    if spec.type in ("import_spec", "import_spec_list"):
                        path_node = spec.child_by_field_name("path")
                        if path_node:
                            path_text = path_node.text.decode('utf8').strip('"')
                            imports.append(Import(
                                source=path_text,
                                symbols=[],
                                is_relative=path_text.startswith("."),
                                line=node.start_point[0] + 1
                            ))
            
            # Recurse
            for child in node.children:
                traverse(child)
        
        traverse(root)
        
        return FileParseResult(
            language="go",
            symbols=symbols,
            imports=imports,
            references=[],
            total_lines=len(lines)
        )
    
    def _parse_rust(self, file_path: str, content: str, tree: Tree) -> FileParseResult:
        """Parse Rust source file."""
        symbols = []
        imports = []
        
        root = tree.root_node
        lines = content.splitlines()
        
        def traverse(node: Node):
            # Function declarations
            if node.type == "function_item":
                name_node = node.child_by_field_name("name")
                if name_node:
                    symbols.append(Symbol(
                        name=name_node.text.decode('utf8'),
                        symbol_type="function",
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        is_entry_point=False  # Could check for #[test] or main
                    ))
            
            # Struct declarations
            elif node.type == "struct_item":
                name_node = node.child_by_field_name("name")
                if name_node:
                    symbols.append(Symbol(
                        name=name_node.text.decode('utf8'),
                        symbol_type="struct",
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1
                    ))
            
            # Enum declarations
            elif node.type == "enum_item":
                name_node = node.child_by_field_name("name")
                if name_node:
                    symbols.append(Symbol(
                        name=name_node.text.decode('utf8'),
                        symbol_type="enum",
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1
                    ))
            
            # Trait declarations
            elif node.type == "trait_item":
                name_node = node.child_by_field_name("name")
                if name_node:
                    symbols.append(Symbol(
                        name=name_node.text.decode('utf8'),
                        symbol_type="trait",
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1
                    ))
            
            # impl blocks
            elif node.type == "impl_item":
                type_node = node.child_by_field_name("type")
                if type_node:
                    symbols.append(Symbol(
                        name=f"impl {type_node.text.decode('utf8')}",
                        symbol_type="impl",
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1
                    ))
            
            # Use statements (imports)
            elif node.type == "use_declaration":
                path_node = node.child_by_field_name("argument")
                if path_node:
                    imports.append(Import(
                        source=path_node.text.decode('utf8'),
                        symbols=[],
                        is_relative=False,
                        line=node.start_point[0] + 1
                    ))
            
            # Recurse
            for child in node.children:
                traverse(child)
        
        traverse(root)
        
        return FileParseResult(
            language="rust",
            symbols=symbols,
            imports=imports,
            references=[],
            total_lines=len(lines)
        )
    
    def _parse_java(self, file_path: str, content: str, tree: Tree) -> FileParseResult:
        """Parse Java source file."""
        symbols = []
        imports = []
        
        root = tree.root_node
        lines = content.splitlines()
        
        def traverse(node: Node):
            # Class declarations
            if node.type == "class_declaration":
                name_node = node.child_by_field_name("name")
                if name_node:
                    symbols.append(Symbol(
                        name=name_node.text.decode('utf8'),
                        symbol_type="class",
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1
                    ))
            
            # Interface declarations
            elif node.type == "interface_declaration":
                name_node = node.child_by_field_name("name")
                if name_node:
                    symbols.append(Symbol(
                        name=name_node.text.decode('utf8'),
                        symbol_type="interface",
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1
                    ))
            
            # Method declarations
            elif node.type == "method_declaration":
                name_node = node.child_by_field_name("name")
                if name_node:
                    symbols.append(Symbol(
                        name=name_node.text.decode('utf8'),
                        symbol_type="method",
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1
                    ))
            
            # Import declarations
            elif node.type == "import_declaration":
                path = "".join(child.text.decode('utf8') for child in node.named_children if child.type in ("identifier", "."))
                if path:
                    imports.append(Import(
                        source=path,
                        symbols=[],
                        is_relative=False,
                        line=node.start_point[0] + 1
                    ))
            
            # Recurse
            for child in node.children:
                traverse(child)
        
        traverse(root)
        
        return FileParseResult(
            language="java",
            symbols=symbols,
            imports=imports,
            references=[],
            total_lines=len(lines)
        )


# Singleton instance
_parser_instance: Optional[TreeSitterParser] = None


def get_parser() -> TreeSitterParser:
    """Get Tree-sitter parser instance."""
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = TreeSitterParser()
    return _parser_instance
