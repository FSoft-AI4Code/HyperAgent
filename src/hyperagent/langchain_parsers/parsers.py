from typing import Any, Dict, Iterator, Optional

from langchain.docstore.document import Document
from langchain.document_loaders.base import BaseBlobParser
from langchain.document_loaders.blob_loaders import Blob
from hyperagent.langchain_parsers.language.csharp import CSharpSegmenter
from hyperagent.langchain_parsers.language.java import JavaSegmenter
from hyperagent.langchain_parsers.language.python import PythonSegmenter
from hyperagent.langchain_parsers.language.rust import RustSegmenter
from langchain.text_splitter import Language

LANGUAGE_EXTENSIONS: Dict[str, str] = {
    "py": Language.PYTHON,
    "cs": Language.CSHARP,
    "rs": Language.RUST,
    "java": Language.JAVA,
}

LANGUAGE_SEGMENTERS: Dict[str, Any] = {
    Language.PYTHON: PythonSegmenter,
    Language.CSHARP: CSharpSegmenter,
    Language.RUST: RustSegmenter,
    Language.JAVA: JavaSegmenter,
}


class LanguageParser(BaseBlobParser):
    """Parse using the respective programming language syntax.

    Each top-level function and class in the code is loaded into separate documents.
    Furthermore, an extra document is generated, containing the remaining top-level code
    that excludes the already segmented functions and classes.

    This approach can potentially improve the accuracy of QA models over source code.

    The supported languages for code parsing are:

    - C# (*)
    - Java (*)
    - Python
    - Rust (*)

    Items marked with (*) require the packages `tree_sitter` and
    `tree_sitter_languages`. It is straightforward to add support for additional
    languages using `tree_sitter`, although this currently requires modifying LangChain.

    The language used for parsing can be configured, along with the minimum number of
    lines required to activate the splitting based on syntax.

    If a language is not explicitly specified, `LanguageParser` will infer one from
    filename extensions, if present.

    Examples:

       .. code-block:: python

            from langchain.text_splitter.Language
            from langchain.document_loaders.generic import GenericLoader
            from langchain.document_loaders.parsers import LanguageParser

            loader = GenericLoader.from_filesystem(
                "./code",
                glob="**/*",
                suffixes=[".py", ".js"],
                parser=LanguageParser()
            )
            docs = loader.load()

        Example instantiations to manually select the language:

        .. code-block:: python

            from langchain.text_splitter import Language

            loader = GenericLoader.from_filesystem(
                "./code",
                glob="**/*",
                suffixes=[".py"],
                parser=LanguageParser(language=Language.PYTHON)
            )

        Example instantiations to set number of lines threshold:

        .. code-block:: python

            loader = GenericLoader.from_filesystem(
                "./code",
                glob="**/*",
                suffixes=[".py"],
                parser=LanguageParser(parser_threshold=200)
            )
    """

    def __init__(self, language: Optional[Language] = None, parser_threshold: int = 0):
        """
        Language parser that split code using the respective language syntax.

        Args:
            language: If None (default), it will try to infer language from source.
            parser_threshold: Minimum lines needed to activate parsing (0 by default).
        """
        self.language = language
        self.parser_threshold = parser_threshold

    def lazy_parse(self, blob: Blob) -> Iterator[Document]:
        code = blob.as_string()

        language = self.language or (
            LANGUAGE_EXTENSIONS.get(blob.source.rsplit(".", 1)[-1])
            if isinstance(blob.source, str)
            else None
        )

        if language is None:
            yield Document(
                page_content=code,
                metadata={
                    "source": blob.source,
                },
            )
            return

        if self.parser_threshold >= len(code.splitlines()):
            yield Document(
                page_content=code,
                metadata={
                    "source": blob.source,
                    "language": language,
                },
            )
            return

        self.Segmenter = LANGUAGE_SEGMENTERS[language]
        segmenter = self.Segmenter(blob.as_string())
        if not segmenter.is_valid():
            yield Document(
                page_content=code,
                metadata={
                    "source": blob.source,
                },
            )
            return

        for functions_classes in segmenter.extract_functions_classes():
            yield Document(
                page_content=functions_classes,
                metadata={
                    "source": blob.source,
                    "content_type": "functions_classes",
                    "language": language,
                },
            )
        yield Document(
            page_content=segmenter.simplify_code(),
            metadata={
                "source": blob.source,
                "content_type": "simplified_code",
                "language": language,
            },
        )